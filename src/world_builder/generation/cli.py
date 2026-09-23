from __future__ import annotations

import argparse
import json
import os
import signal
import tempfile
import time
from pathlib import Path

from world_builder.storage.repository import Repository
from .model import FixtureProvider, HttpJSONProvider, ModelContractError, compile_spec, publish_accepted, replay_spec
from .pipeline import generate, semantic_hash
from .spec import Budget, PilotSpec, canonical


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".snapshot-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate/resume a bounded WIR pilot; not the full 006 city acceptance")
    parser.add_argument("--output", type=Path, required=True, help="SQLite repository and resources directory")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--scenario", choices=["riverside", "hillside", "dense"], default="riverside")
    parser.add_argument("--buildings", type=int, default=6)
    parser.add_argument("--interiors", type=int, default=2)
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--max-candidates", type=int, default=3, help="per-stage candidate cap, including the initial candidate")
    parser.add_argument("--layout-profile", choices=["standard", "compact"], default="standard")
    parser.add_argument("--lock-stair-void", action="store_true", help="protect the initial building stair reservation")
    parser.add_argument("--prompt", help="compile this prompt using a fixture or configured JSON service")
    parser.add_argument("--model-fixture", type=Path, help="local response JSON, used without a network call")
    parser.add_argument("--model-endpoint", help="HTTPS endpoint implementing the project JSON contract")
    parser.add_argument("--model-id", help="model identifier for the HTTPS request")
    parser.add_argument("--api-key-env", help="name of the environment variable holding the endpoint token")
    parser.add_argument("--model-token-budget", type=int, default=4000)
    parser.add_argument("--replay-world-id", help="resume an accepted model world without a service or fixture")
    args = parser.parse_args(argv)
    if args.prompt and args.replay_world_id:
        parser.error("--prompt and --replay-world-id are mutually exclusive")
    if args.prompt and bool(args.model_fixture) == bool(args.model_endpoint):
        parser.error("--prompt requires exactly one of --model-fixture or --model-endpoint")
    if not args.prompt and (args.model_fixture or args.model_endpoint):
        parser.error("a model source requires --prompt")
    if args.model_endpoint and not args.model_id:
        parser.error("--model-endpoint requires --model-id")
    try:
        budget = Budget(wall_time_ms=args.timeout_ms, max_candidates=args.max_candidates)
    except ValueError as exc:
        parser.error(str(exc))
    repository = Repository(args.output)
    model_calls = 0
    try:
        if args.replay_world_id:
            spec = replay_spec(repository, args.replay_world_id)
        elif args.prompt:
            provider = FixtureProvider(args.model_fixture) if args.model_fixture else HttpJSONProvider(
                args.model_endpoint, args.model_id, args.api_key_env, timeout_s=min(20, args.timeout_ms / 1000))
            started = time.monotonic()
            prepared = compile_spec(args.prompt, args.seed, provider, max_total_tokens=args.model_token_budget)
            model_calls = 1
            elapsed = round((time.monotonic() - started) * 1000)
            if elapsed >= budget.wall_time_ms:
                raise ModelContractError("execution.timeout", "model response consumed the world budget")
            spec = publish_accepted(repository, prepared)
            budget = Budget(wall_time_ms=budget.wall_time_ms - elapsed, max_candidates=budget.max_candidates)
        else:
            spec = PilotSpec(seed=args.seed, scenario=args.scenario, building_count=args.buildings, interior_count=args.interiors,
                             layout_profile=args.layout_profile, lock_stair_void=args.lock_stair_void)
    except (ValueError, OSError) as exc:
        print(json.dumps({"code": getattr(exc, "code", "contract.model_error"), "message": str(exc)}, ensure_ascii=False))
        return 2
    interrupted = False

    def cancel(signum, frame):
        nonlocal interrupted
        interrupted = True

    previous_handler = signal.signal(signal.SIGINT, cancel)
    try:
        result = generate(spec, repository, budget, cancelled=lambda: interrupted)
    finally:
        signal.signal(signal.SIGINT, previous_handler)
    report = result.to_dict()
    report["model_calls_this_run"] = model_calls
    if result.revision_id:
        package = repository.load(spec.world_id, result.revision_id)
        snapshot = repository.root / (spec.world_id + ".world.json")
        atomic_json(snapshot, package)
        report["snapshot"] = str(snapshot)
        report["semantic_hash"] = semantic_hash(package)
    atomic_json(repository.root / (spec.world_id + ".run.json"), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if result.termination_reason == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
