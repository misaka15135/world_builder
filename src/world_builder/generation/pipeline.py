from __future__ import annotations

import copy
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Callable

from world_builder.storage.repository import Repository, StoreError
from world_builder.wir.validator import validate_package

from . import GENERATOR_VERSION
from .journal import RunJournal
from .planner import STAGES, initial_records, plan_stage
from .repair import propose_repair
from .spec import Budget, PilotSpec, digest
from .validation import check_geometry


@dataclass
class RunResult:
    world_id: str
    revision_id: str | None
    termination_reason: str
    feasibility: str
    code: str
    message: str
    stages: list[dict] = field(default_factory=list)
    contract_version: str = "0.1.0"
    run_id: str | None = None
    journal_path: str | None = None

    def to_dict(self) -> dict:
        result = asdict(self)
        result["proof_ref"] = None
        result["retryable"] = self.code in {"execution.timeout", "execution.cancelled", "execution.error", "conflict.base_revision"}
        result["scope_ids"] = [self.world_id]
        return result


class Halt(Exception):
    def __init__(self, reason: str):
        self.reason = reason


def semantic_hash(package: dict) -> str:
    """Stable generated semantics, excluding clock timestamps and revision metadata."""
    return digest([r for r in package["records"] if r["record_type"] != "revision"])


def make_snapshot(spec: PilotSpec, records: list[dict], stage: str, parent: str | None,
                  budget: Budget, created_at: str, attempt_history: list[dict] | None = None) -> tuple[dict, list[dict]]:
    records = copy.deepcopy([r for r in records if r["record_type"] not in {"constraint", "revision"}
                            and r["id"] != "recipe_" + stage])
    world_spec = next(r for r in records if r["record_type"] == "world_spec")
    world_spec["extensions"]["stage"] = stage
    checks = check_geometry(records)
    failures = sum(c["state"] == "fail" and c["severity"] == "hard" for c in checks)
    recipe_id = "recipe_" + stage
    index = STAGES.index(stage)
    records.append({"record_type": "recipe", "id": recipe_id, "generator_id": "pilot." + stage,
        "generator_version": GENERATOR_VERSION, "input_hash": digest([spec.to_dict(), stage, parent]),
        "seed": f"0x{spec.seed:016x}", "dependency_recipe_ids": ["recipe_" + STAGES[index-1]] if index else [],
        "budget": {"wall_time_ms": budget.wall_time_ms, "max_candidates": budget.max_candidates, "max_model_calls": 0},
        "outcome": {"termination_reason": "completed", "feasibility": "unknown" if failures else "feasible", "proof_ref": None},
        "accepted_model_response_hash": None, "extensions": {"validation_scope": "pilot_axis_aligned_templates",
            "attempt_history": copy.deepcopy(attempt_history or [])}})
    revision_id = "revision_" + digest(records)[7:31]
    for check in checks:
        records.append({"record_type": "constraint", "id": "constraint_" + digest([check["rule"], check["scope_ids"]])[7:31],
            "rule_id": check["rule"], "rule_version": GENERATOR_VERSION, "scope_entity_ids": check["scope_ids"],
            "severity": check["severity"], "priority": 100 if check["severity"] == "hard" else 10,
            "parameters": {}, "tolerance": {"value": 1e-6, "unit": "m"}, "source": "system",
            "validation": {"state": check["state"], "checked_revision_id": revision_id, "message": check["message"]}, "extensions": {}})
    manifest = {
        "package_format": "worldpkg-json-snapshot", "schema_version": "0.1.0", "package_id": "package_" + revision_id[9:],
        "world_id": spec.world_id, "revision_id": revision_id,
        "required_capabilities": ["wir.core/0.1", "wir.constraints/0.1", "wir.revisions/0.1"],
        "units": {"length": "m", "angle": "rad"},
        "coordinate_system": {"handedness": "right", "x_axis": "east", "y_axis": "north", "z_axis": "up",
            "transform_convention": "column_vector_parent_times_local", "quaternion_order": "xyzw", "storage_precision": "float64"},
        "tolerances": {"regional_m": 0.1, "building_m": 0.01, "interior_m": 0.005, "angle_rad": 0.0001},
        "package_mode": "self_contained", "created_at": created_at,
        "extensions": {"generator_version": GENERATOR_VERSION, "pilot": True},
    }
    failures = sum(c["state"] == "fail" and c["severity"] == "hard" for c in checks)
    records.append({"record_type": "revision", "id": revision_id, "world_id": spec.world_id,
        "parent_revision_ids": [parent] if parent else [], "created_at": created_at, "author": GENERATOR_VERSION,
        "change_set_hash": digest(records), "validation_summary": {"hard_failures": failures, "unknown_checks": 0},
        "committed": failures == 0, "extensions": {"snapshot_manifest": copy.deepcopy(manifest)}})
    return {"manifest": manifest, "records": records}, checks


def generate(spec: PilotSpec, repository: Repository, budget: Budget | None = None,
             cancelled: Callable[[], bool] = lambda: False,
             clock: Callable[[], float] = time.monotonic,
             fault: Callable[[str, str], None] | None = None) -> RunResult:
    """Resume a fixed specification at the last committed stage.

    `fault` is an explicit test seam. No external code or model output is executed.
    Validation failure is an invalid candidate, never a proof of infeasibility.
    """
    budget = budget or Budget()
    start = clock()
    head = repository.head(spec.world_id)
    metrics: list[dict] = []
    journal = RunJournal(repository.root)
    journal.append({"event": "started", "contract_version": "0.1.0", "generator_version": GENERATOR_VERSION,
                    "world_id": spec.world_id, "spec": spec.to_dict(), "budget": asdict(budget), "base_revision_id": head})

    def finish(reason: str, feasibility: str, code: str, message: str) -> RunResult:
        result = RunResult(spec.world_id, head, reason, feasibility, code, message, metrics,
                           run_id=journal.run_id, journal_path=str(journal.path))
        journal.append({"event": "finished", "result": result.to_dict()})
        return result

    def checkpoint() -> None:
        if cancelled():
            raise Halt("cancelled")
        if (clock() - start) * 1000 >= budget.wall_time_ms:
            raise Halt("timeout")

    try:
        checkpoint()
        if head:
            package = repository.load(spec.world_id)
            saved = next(r for r in package["records"] if r["record_type"] == "world_spec")
            if saved["extensions"]["pilot_spec"] != spec.to_dict() or saved["extensions"]["generator_version"] != GENERATOR_VERSION:
                raise StoreError("contract.generator_version", "resume requires the same spec and generator version")
            if any(c["severity"] == "hard" and c["state"] != "pass" for c in check_geometry(package["records"])):
                raise StoreError("constraint.resume_invalid", "saved geometry failed revalidation")
            records = package["records"]
            first = STAGES.index(saved["extensions"]["stage"]) + 1
        else:
            records, first = initial_records(spec), 0
        for stage in STAGES[first:]:
            checkpoint()
            stage_start = clock()
            candidate = copy.deepcopy(records)
            additions, resources = plan_stage(spec, stage, candidate)
            candidate.extend(additions)
            for item in additions:
                if item["record_type"] == "entity":
                    item["recipe_id"] = "recipe_" + stage
            trace: list[dict] = []
            metric = {"stage": stage, "attempts": 0, "attempt_history": trace, "committed": False}
            metrics.append(metric)
            for attempt in range(1, budget.max_candidates + 1):
                checkpoint()
                metric["attempts"] = attempt
                journal.append({"event": "attempt_started", "stage": stage, "attempt": attempt})
                package, checks = make_snapshot(spec, candidate, stage, head, budget,
                                                datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), trace)
                validate_package(package)
                Repository._check_locks({"records": records}, package)
                failures = [c for c in checks if c["severity"] == "hard" and c["state"] != "pass"]
                entry = {"attempt": attempt, "candidate_hash": digest([r for r in candidate if r["record_type"] not in {"revision", "constraint"}]), "failures": failures,
                         "status": "rejected" if failures else "validated"}
                trace.append(entry)
                journal.append({"event": "candidate_checked", "stage": stage, **entry})
                checkpoint()
                if not failures:
                    # Persist the accepted and rejected attempts with the recipe.
                    package, checks = make_snapshot(spec, candidate, stage, head, budget,
                                                    package["manifest"]["created_at"], trace)
                    validate_package(package)
                    break
                if attempt == budget.max_candidates:
                    return finish("budget_exhausted", "unknown", "execution.budget_exhausted", "candidate limit reached; last committed revision preserved")
                proposal = propose_repair(candidate, failures, records)
                entry["repair"] = {"code": proposal.code, "message": proposal.message, "actions": proposal.actions,
                                   "applied_to_candidate": proposal.records is not None}
                journal.append({"event": "repair_proposed", "stage": stage, "attempt": attempt, **entry["repair"]})
                checkpoint()
                if proposal.records is None:
                    return finish("search_exhausted", "unknown", proposal.code, proposal.message)
                candidate = proposal.records
            checkpoint()
            for asset_id, payload in resources.items():
                checksum, uri = repository.publish(payload)
                asset = next(r for r in package["records"] if r["id"] == asset_id)
                if (checksum, uri) != (asset["content_hash"], asset["uri"]):
                    raise StoreError("resource.hash_mismatch", asset_id)

            def before_commit():
                if fault:
                    fault(stage, "before_commit")
                checkpoint()

            repository.commit(package, head, before_commit=before_commit)
            head = package["manifest"]["revision_id"]
            records = package["records"]
            metric.update({"committed": True, "wall_time_ms": round((clock()-stage_start)*1000, 3),
                            "entities": sum(r["record_type"] == "entity" for r in records), "checks": len(checks),
                            "soft_failures": sum(c["severity"] == "soft" and c["state"] == "fail" for c in checks),
                            "resource_bytes": sum(len(v) for v in resources.values()), "model_calls": 0})
            journal.append({"event": "stage_committed", "stage": stage, "revision_id": head})
        return finish("completed", "feasible", "generation.completed", "pilot completed within the declared template rules")
    except Halt as exc:
        return finish(exc.reason, "unknown", "execution." + exc.reason, "last committed revision preserved")
    except Exception as exc:
        return finish("error", "unknown", getattr(exc, "code", "execution.error"), str(exc))
