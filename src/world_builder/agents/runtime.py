"""Bounded dependency supervisor: A → (B,C) → D → E[site] → F.

Only accepted, immutable JSON snapshots cross agent boundaries. A model may
request scoped revision but cannot commit, change budgets or run code.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
from pathlib import Path
from threading import Lock
import time

from .contracts import AgentError, CONFIG_SCHEMA, REQUEST_SCHEMA, ROOT, STAGES, VERSION, canonical, digest, response_schema, strict_json
from .contracts import validate_schema
from .validation import check_plan, require

SKILLS = {stage: f"world-agent-{stage.lower()}" for stage in STAGES}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(canonical(value))
    temporary.replace(path)


class Supervisor:
    def __init__(self, provider, config, output, *, region_m=128, seed=1, clock=time.monotonic,
                 cancelled=lambda: False):
        validate_schema(config, CONFIG_SCHEMA, "config.schema")
        require(type(region_m) is int and 32 <= region_m <= 512 and region_m % 16 == 0,
                "input.region", "region_m must be a multiple of 16 in 32..512")
        require(type(seed) is int and 0 <= seed < 2**64, "input.seed", "Seed must be uint64")
        self.provider, self.config = provider, deepcopy(config)
        self.limits = self.config["limits"]
        self.root = Path(output)
        self.root.mkdir(parents=True, exist_ok=False)
        self.region_m, self.seed = region_m, seed
        self.clock, self.cancelled = clock, cancelled
        self.started = clock()
        self.lock = Lock()
        self.calls = self.network_calls = self.token_usage = self.reserved = 0
        self.skills = {s: (ROOT / "skills" / SKILLS[s] / "SKILL.md").read_text("utf-8") for s in STAGES}
        self.skills["E"] += "\n\n" + (ROOT / "skills" / SKILLS["E"] / "references" / "design-principles.md").read_text("utf-8")
        self.accepted = {}

    def event(self, event, **data):
        with self.lock:
            with (self.root / "events.jsonl").open("ab") as stream:
                stream.write(canonical({"event": event, **data}) + b"\n")

    def checkpoint(self):
        if self.cancelled():
            raise AgentError("execution.cancelled", "Generation cancelled; recorded proposals retained")
        remaining = self.limits["wall_time_s"] - (self.clock() - self.started)
        if remaining <= 0:
            raise AgentError("budget.time", "Run wall-time limit reached")
        return min(remaining, self.limits["timeout_s"])

    def ask(self, stage, plans, *, scope_id="scene", feedback=None, revision=0):
        feedback = deepcopy(feedback or [])
        dependencies = [{"stage": key, "sha256": digest(value), "data": value}
                        for key, value in sorted(plans.items())]
        last_error = None
        for attempt in range(1, self.limits["attempts"] + 1):
            timeout = self.checkpoint()
            body = {"contract_version": VERSION, "stage": stage, "scope_id": scope_id,
                    "prompt": self.prompt, "seed": self.seed, "region_m": self.region_m,
                    "units": "m", "axes": "RH_X_east_Y_north_Z_up", "geometry": "integer_cuboids_v1",
                    "limits": self.limits, "attempt": attempt, "revision_round": revision,
                    "dependencies": dependencies, "feedback": feedback,
                    "instructions": self.skills[stage], "response_schema": response_schema(stage)}
            request_id = digest(body)
            request = {**body, "request_id": request_id,
                       "response_schema": response_schema(stage, request_id, scope_id)}
            validate_schema(request, REQUEST_SCHEMA, "request.schema")
            # Conservative byte-based preflight reservation. Actual provider
            # usage is still checked, including hidden completion tokens.
            reservation = len(canonical(request)) + self.limits["max_output_tokens"] + 1024
            with self.lock:
                require(self.calls < self.limits["max_calls"], "budget.calls", "Run call limit reached")
                require(self.token_usage + self.reserved + reservation <= self.limits["max_total_tokens"],
                        "budget.tokens", "Insufficient budget to reserve this request")
                self.calls += 1
                self.network_calls += int(self.provider.network)
                self.reserved += reservation
            call_dir = self.root / "calls" / request_id[7:]
            write_json(call_dir / "request.json", request)
            self.event("request", stage=stage, scope_id=scope_id, request_id=request_id, attempt=attempt)
            charged = reservation
            raw = None
            try:
                completion = self.provider.complete(request, timeout_s=timeout)
                raw = completion.raw
                require(isinstance(raw, bytes) and len(raw) <= self.limits["max_response_bytes"],
                        "api.response_size", "Provider returned invalid or oversized bytes")
                require(all(type(v) is int and v >= 0 for v in (completion.input_tokens, completion.output_tokens)),
                        "api.usage", "Provider usage must be nonnegative integers")
                charged = completion.input_tokens + completion.output_tokens
                (call_dir / "response.json").write_bytes(raw)
                meta = {"model": completion.model, "source": completion.source,
                        "input_tokens": completion.input_tokens, "output_tokens": completion.output_tokens,
                        "response_sha256": "sha256:" + hashlib.sha256(raw).hexdigest()}
                write_json(call_dir / "completion.json", meta)
                self.checkpoint()
                require(charged <= reservation and completion.output_tokens <= self.limits["max_output_tokens"],
                        "budget.provider_usage", "Provider exceeded reserved/requested token allowance")
                response = strict_json(raw)
                validate_schema(response, request["response_schema"])
                payload = response["payload"]
                check_plan(stage, payload, plans, region_m=self.region_m, limits=self.limits, scope_id=scope_id)
                with self.lock:
                    self.accepted[f"{stage}:{scope_id}"] = {"request_id": request_id,
                                                           "response_sha256": meta["response_sha256"]}
                self.event("accepted", stage=stage, scope_id=scope_id, request_id=request_id,
                           payload_sha256=digest(payload))
                return deepcopy(payload)
            except AgentError as exc:
                last_error = exc
                write_json(call_dir / "error.json", {"code": exc.code, "message": str(exc)})
                self.event("rejected", stage=stage, scope_id=scope_id, request_id=request_id, code=exc.code)
                if exc.code.startswith(("budget.", "execution.", "replay.", "fixture.")):
                    raise
                # Bad data is quoted as user-context data on the next attempt.
                feedback = [*(feedback[-2:]), {"code": exc.code, "message": str(exc),
                            "rejected_response": raw.decode("utf-8", errors="replace")[:12000] if raw else None}]
            finally:
                with self.lock:
                    self.reserved -= reservation
                    self.token_usage += charged
        raise AgentError("stage.exhausted", f"{stage}:{scope_id} exhausted attempts; {last_error.code}: {last_error}")

    def parallel(self, tasks):
        # Ordered collection makes compilation/replay deterministic despite
        # completion order. Workers share a locked budget and append-only log.
        with ThreadPoolExecutor(max_workers=self.limits["workers"]) as pool:
            futures = [pool.submit(fn) for fn in tasks]
            try:
                return [future.result() for future in futures]
            except BaseException:
                for future in futures:
                    future.cancel()
                raise

    def run(self, prompt):
        require(isinstance(prompt, str) and 1 <= len(prompt.strip()) <= 20000,
                "input.prompt", "Prompt must contain 1..20000 characters")
        self.prompt = prompt
        plans = {}
        fixes = []
        self.event("started", prompt=prompt, seed=self.seed, region_m=self.region_m,
                   provider_mode="api" if self.provider.network else type(self.provider).__name__)
        try:
            plans["A"] = self.ask("A", {})
            for revision in range(self.limits["review_rounds"] + 1):
                upstream = {fix["stage"] for fix in fixes}
                missing = [s for s in ("B", "C") if s not in plans or s in upstream]
                if missing:
                    self.invalidate(plans, {"D", "E", "F"})
                    values = self.parallel([lambda s=s: self.ask(s, {"A": plans["A"]},
                                                feedback=[f for f in fixes if f["stage"] == s], revision=revision)
                                            for s in missing])
                    plans.update(zip(missing, values))
                if "D" not in plans or "D" in upstream:
                    self.invalidate(plans, {"E", "F"})
                    plans["D"] = self.ask("D", {s: plans[s] for s in ("A", "B", "C")},
                                           feedback=[f for f in fixes if f["stage"] == "D"], revision=revision)
                designs = plans.setdefault("E", {})
                site_ids = sorted(s["id"] for s in plans["D"]["sites"])
                redo = {f["scope_id"] for f in fixes if f["stage"] == "E"}
                todo = [s for s in site_ids if s not in designs or s in redo]
                # Do not pass sibling designs from this concurrent batch as mutable context.
                context = {s: plans[s] for s in ("A", "B", "C", "D")}
                values = self.parallel([lambda site=site: self.ask("E", context, scope_id=site,
                                           feedback=[f for f in fixes if f["stage"] == "E" and f["scope_id"] == site],
                                           revision=revision) for site in todo])
                designs.update(zip(todo, values))
                require(set(designs) == set(site_ids), "scene.coverage", "Missing or stale building designs")
                require(sum(len(d["parts"]) for d in designs.values()) <= self.limits["max_parts"],
                        "budget.parts", "Scene exceeds component budget")
                plans["F"] = self.ask("F", {s: plans[s] for s in ("A", "B", "C", "D", "E")}, revision=revision)
                write_json(self.root / f"plans-round-{revision}.json", plans)
                if plans["F"]["verdict"] == "accept":
                    self.checkpoint()
                    result = {"contract_version": VERSION, "prompt": prompt, "seed": self.seed,
                              "region_m": self.region_m, "plans": plans,
                              "accepted_responses": dict(sorted(self.accepted.items())),
                              "skill_hashes": {s: digest(self.skills[s]) for s in STAGES}}
                    write_json(self.root / "accepted.json", result)
                    self.event("planning_completed", plans_sha256=digest(plans))
                    return result
                fixes = plans["F"]["fixes"]
                self.event("revision_requested", revision=revision, fixes=fixes)
            raise AgentError("review.exhausted", "F still requests changes after the review-round budget")
        except BaseException as exc:
            self.event("failed", code=getattr(exc, "code", "execution.error"), message=str(exc))
            write_json(self.root / "failure.json", {"code": getattr(exc, "code", "execution.error"),
                                                   "message": str(exc), "plans": plans})
            raise

    def invalidate(self, plans, stages):
        for stage in sorted(stages):
            if stage in plans:
                self.event("invalidated", stage=stage, previous_sha256=digest(plans[stage]))
                del plans[stage]
            with self.lock:
                self.accepted = {k: v for k, v in self.accepted.items() if k.split(":")[0] != stage}

    def usage(self):
        return {"provider_calls": self.calls, "network_calls": self.network_calls,
                "accounted_tokens": self.token_usage, "elapsed_s": round(self.clock() - self.started, 3)}
