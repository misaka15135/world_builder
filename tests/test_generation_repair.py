from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from world_builder.generation import pipeline
from world_builder.generation.pipeline import generate, semantic_hash
from world_builder.generation.repair import propose_repair
from world_builder.generation.spec import Budget, PilotSpec
from world_builder.generation.validation import check_geometry
from world_builder.storage.repository import Repository


def events(result):
    return [json.loads(line) for line in Path(result.journal_path).read_text(encoding="utf-8").splitlines()]


def test_compact_repair_propagates_to_parent_without_rewriting_history(tmp_path):
    spec = PilotSpec(layout_profile="compact", seed=303, interior_count=4)
    repo = Repository(tmp_path)
    result = generate(spec, repo)
    assert result.termination_reason == "completed", result.to_dict()
    stage = result.stages[-1]
    assert stage["attempts"] == 3
    assert [e["status"] for e in stage["attempt_history"]] == ["rejected", "rejected", "validated"]
    assert {f["rule"] for f in stage["attempt_history"][0]["failures"]} == {"pilot.stair_dimensions"}
    assert {f["rule"] for f in stage["attempt_history"][1]["failures"]} == {"pilot.stair_envelope"}
    package = repo.load(spec.world_id)
    by_id = {r["id"]: r for r in package["records"]}
    assert by_id["stair_000"]["geometry"]["run_m"] == 6
    assert by_id["building_000"]["geometry"]["stair_void_local_m"]["max"][1] == 11
    assert len(by_id["stair_002"]["chunk_ids"]) == 2  # Repaired stair crosses the 64 m boundary.
    assert by_id["recipe_interiors"]["extensions"]["attempt_history"] == stage["attempt_history"]
    assert all(c["state"] == "pass" for c in check_geometry(package["records"]) if c["severity"] == "hard")
    revisions = [e["revision_id"] for e in events(result) if e["event"] == "stage_committed"]
    old = repo.load(spec.world_id, revisions[-2])
    assert next(r for r in old["records"] if r["id"] == "building_000")["geometry"]["stair_void_local_m"]["max"][1] == 9
    assert next(r for r in old["records"] if r["id"] == "building_000")["attributes"]["interior_state"] == "deferred"
    assert any(a["scope"] == "parent" for a in stage["attempt_history"][1]["repair"]["actions"])
    with repo.connect() as db:
        assert db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 5


@pytest.mark.parametrize("limit", [1, 2])
def test_candidate_budget_preserves_last_commit_and_resume_is_a_new_run(tmp_path, limit):
    spec, repo = PilotSpec(layout_profile="compact"), Repository(tmp_path)
    first = generate(spec, repo, Budget(max_candidates=limit))
    assert (first.termination_reason, first.feasibility) == ("budget_exhausted", "unknown")
    assert first.stages[-1]["attempts"] == limit
    assert first.stages[-1]["committed"] is False
    assert len([e for e in events(first) if e["event"] == "candidate_checked" and e["stage"] == "interiors"]) == limit
    head = repo.head(spec.world_id)
    assert head == first.revision_id
    before = Path(first.journal_path).read_bytes()
    result = generate(spec, repo)
    assert result.termination_reason == "completed"
    assert [s["stage"] for s in result.stages] == ["interiors"]
    assert first.run_id != result.run_id
    assert Path(first.journal_path).read_bytes() == before
    assert repo.head(spec.world_id) != head


def test_locked_parent_returns_unknown_and_preserves_reservation(tmp_path):
    spec, repo = PilotSpec(layout_profile="compact", lock_stair_void=True), Repository(tmp_path)
    result = generate(spec, repo)
    assert (result.termination_reason, result.feasibility, result.code) == ("search_exhausted", "unknown", "conflict.locked_field")
    assert result.stages[-1]["attempts"] == 2
    proposal = result.stages[-1]["attempt_history"][-1]["repair"]
    assert proposal["applied_to_candidate"] is False
    assert any(a["scope"] == "parent" for a in proposal["actions"])
    package = repo.load(spec.world_id)
    building = next(r for r in package["records"] if r["id"] == "building_000")
    assert building["geometry"]["stair_void_local_m"]["max"][1] == 9
    assert building["locks"]
    with repo.connect() as db:
        assert db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 4
    assert events(result)[-1]["result"]["feasibility"] == "unknown"


@pytest.mark.parametrize("halt", ["timeout", "cancelled"])
def test_interrupt_after_repair_does_not_commit_candidate(tmp_path, monkeypatch, halt):
    spec, repo = PilotSpec(layout_profile="compact"), Repository(tmp_path)
    state = {"halt": False}
    original = pipeline.propose_repair

    def interrupt(*args):
        proposal = original(*args)
        state["halt"] = True
        return proposal

    monkeypatch.setattr(pipeline, "propose_repair", interrupt)
    result = generate(spec, repo, cancelled=lambda: state["halt"] and halt == "cancelled",
                      clock=lambda: 31 if state["halt"] and halt == "timeout" else 0)
    assert (result.termination_reason, result.feasibility) == (halt, "unknown")
    assert result.stages[-1]["attempts"] == 1
    with repo.connect() as db:
        assert db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 4
    assert events(result)[-1]["event"] == "finished"


def test_repair_audit_is_deterministic(tmp_path):
    spec = PilotSpec(layout_profile="compact", building_count=1, interior_count=1)
    packages = []
    for name in ("one", "two"):
        repo = Repository(tmp_path / name)
        assert generate(spec, repo).termination_reason == "completed"
        packages.append(repo.load(spec.world_id))
    assert semantic_hash(packages[0]) == semantic_hash(packages[1])


def test_unsupported_failure_is_not_retried_or_declared_infeasible(tmp_path, monkeypatch):
    spec, repo = PilotSpec(), Repository(tmp_path)
    original = pipeline.plan_stage

    def disconnect(spec, stage, records):
        additions, resources = original(spec, stage, records)
        if stage == "network":
            road = next(r for r in additions if r["id"] == "road_cross_west")
            road["bounds"]["max"][0] = 55
            road["geometry"]["size_m"][0] = 11
        return additions, resources

    monkeypatch.setattr(pipeline, "plan_stage", disconnect)
    result = generate(spec, repo)
    assert (result.termination_reason, result.feasibility) == ("search_exhausted", "unknown")
    assert result.code == "constraint.repair_unsupported"
    assert result.stages[-1]["attempts"] == 1
    with repo.connect() as db:
        assert db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 1


def test_parent_capacity_failure_is_not_a_global_infeasibility_proof():
    records = [{"id": "stair_000", "kind": "stair", "parent_id": "building_000", "locks": [],
                "transform": {"translation": [11, 3, 0.2]}, "geometry": {"run_m": 20, "landing_length_m": 2}},
               {"id": "building_000", "geometry": {"size_m": [16, 16, 6.4]}, "locks": []}]
    before = copy.deepcopy(records)
    result = propose_repair(records, [{"rule": "pilot.stair_envelope", "scope_ids": ["stair_000"]}], records)
    assert result.records is None
    assert result.code == "constraint.parent_capacity"
    assert records == before
