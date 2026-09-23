from __future__ import annotations

import copy

import pytest

from world_builder.generation.pipeline import generate, make_snapshot, semantic_hash
from world_builder.generation.spec import Budget, PilotSpec
from world_builder.generation.validation import check_geometry
from world_builder.storage.repository import Repository, StoreError
from world_builder.wir.validator import load_and_validate
from world_builder.generation.cli import atomic_json


@pytest.fixture
def completed(tmp_path):
    spec = PilotSpec(seed=17)
    repository = Repository(tmp_path / "world")
    result = generate(spec, repository)
    assert result.termination_reason == "completed", result.to_dict()
    return spec, repository, repository.load(spec.world_id)


def changed_snapshot(package, spec, mutate):
    records = copy.deepcopy(package["records"])
    records = [r for r in records if not (r["record_type"] == "recipe" and r["id"] == "recipe_interiors")]
    mutate(records)
    return make_snapshot(spec, records, "interiors", package["manifest"]["revision_id"], Budget(), "2026-09-23T00:00:00Z")[0]


def test_generated_world_is_real_schema_valid_and_saved(completed):
    spec, repository, package = completed
    buildings = [r for r in package["records"] if r.get("kind") == "building"]
    assert len(buildings) == 6
    assert sum(b["attributes"]["interior_state"] == "generated" for b in buildings) == 2
    assert sum(b["attributes"]["interior_state"] == "deferred" for b in buildings) == 4
    assert all(c["state"] == "pass" for c in check_geometry(package["records"]) if c["severity"] == "hard")
    with repository.connect() as db:
        assert db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 5
        assert db.execute("SELECT count(*) FROM revision_resources").fetchone()[0] == 5
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute("SELECT count(*) FROM record_bounds").fetchone()[0] > 0
    path = repository.root / "snapshot.world.json"
    atomic_json(path, package)
    assert load_and_validate(path) == package
    assert Repository(repository.root).load(spec.world_id) == package


def test_seeded_semantics_and_idempotent_resume(completed, tmp_path):
    spec, repository, first = completed
    second_repository = Repository(tmp_path / "second")
    second_result = generate(spec, second_repository)
    assert second_result.termination_reason == "completed"
    assert semantic_hash(first) == semantic_hash(second_repository.load(spec.world_id))
    result = generate(spec, repository)
    assert result.stages == []
    assert result.revision_id == first["manifest"]["revision_id"]
    with repository.connect() as db:
        assert db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 5


@pytest.mark.parametrize("scenario", ["riverside", "hillside", "dense"])
def test_three_pilot_scenarios(tmp_path, scenario):
    spec = PilotSpec(seed=5, scenario=scenario)
    repository = Repository(tmp_path / scenario)
    result = generate(spec, repository)
    assert result.termination_reason == "completed", result.to_dict()


def test_transaction_fault_preserves_previous_stage_and_resumes(tmp_path):
    spec, repository = PilotSpec(seed=9), Repository(tmp_path)

    def fault(stage, phase):
        if stage == "buildings":
            raise OSError("injected interrupted commit")

    result = generate(spec, repository, fault=fault)
    assert (result.termination_reason, result.feasibility) == ("error", "unknown")
    previous = Repository(tmp_path).load(spec.world_id)
    assert next(r for r in previous["records"] if r["record_type"] == "world_spec")["extensions"]["stage"] == "parcels"
    with repository.connect() as db:
        assert db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 3
        assert db.execute("SELECT head_revision_id FROM branches").fetchone()[0] == result.revision_id
        assert db.execute("SELECT count(*) FROM record_bounds").fetchone()[0] == 3+8+17
    resumed = generate(spec, Repository(tmp_path))
    assert resumed.termination_reason == "completed"
    assert [s["stage"] for s in resumed.stages] == ["buildings", "interiors"]


@pytest.mark.parametrize("reason", ["cancelled", "timeout"])
def test_cancellation_and_timeout_inside_transaction_roll_back(tmp_path, reason):
    repository, spec = Repository(tmp_path), PilotSpec()
    state = {"cancelled": False, "now": 0.0}

    def fault(stage, phase):
        if stage == "network":
            if reason == "cancelled":
                state["cancelled"] = True
            else:
                state["now"] = 31.0

    result = generate(spec, repository, clock=lambda: state["now"], cancelled=lambda: state["cancelled"], fault=fault)
    assert (result.termination_reason, result.feasibility) == (reason, "unknown")
    with repository.connect() as db:
        assert db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 1
    assert repository.head(spec.world_id) == result.revision_id
    assert generate(spec, repository).termination_reason == "completed"


def test_cancel_before_first_commit_creates_no_world(tmp_path):
    spec, repository = PilotSpec(), Repository(tmp_path)
    result = generate(spec, repository, cancelled=lambda: True)
    assert result.termination_reason == "cancelled"
    assert repository.head(spec.world_id) is None


def test_corrupt_resource_cannot_resume(completed):
    spec, repository, package = completed
    resource = next(r for r in package["records"] if r["record_type"] == "asset")
    (repository.root / resource["uri"]).write_bytes(b"corrupt")
    with pytest.raises(StoreError, match="resource.hash_mismatch"):
        repository.load(spec.world_id)
    result = generate(spec, repository)
    assert result.code == "resource.hash_mismatch"
    assert result.feasibility == "unknown"
    assert repository.head(spec.world_id) == package["manifest"]["revision_id"]


def test_stale_revision_is_not_overwritten(completed):
    spec, repository, package = completed
    candidate = changed_snapshot(package, spec, lambda records: None)
    repository.commit(candidate, package["manifest"]["revision_id"])
    with pytest.raises(StoreError, match="conflict.base_revision"):
        Repository(repository.root).commit(candidate, package["manifest"]["revision_id"])
    assert repository.head(spec.world_id) == candidate["manifest"]["revision_id"]


def test_locked_field_cannot_change_or_disappear(completed):
    spec, repository, package = completed

    def lock(records):
        building = next(r for r in records if r["id"] == "building_000")
        building["locks"] = [{"json_pointer": "/attributes/roof_style", "mode": "value", "reason": "approved"}]

    locked = changed_snapshot(package, spec, lock)
    repository.commit(locked, package["manifest"]["revision_id"])

    def alter(records):
        next(r for r in records if r["id"] == "building_000")["attributes"]["roof_style"] = "edited"

    with pytest.raises(StoreError, match="conflict.locked_field"):
        repository.commit(changed_snapshot(locked, spec, alter), locked["manifest"]["revision_id"])
    assert repository.head(spec.world_id) == locked["manifest"]["revision_id"]


@pytest.mark.parametrize("entity_id, mutate, expected_rule", [
    ("road_cross_west", lambda e: e["bounds"]["max"].__setitem__(0, 55), "pilot.network_connected"),
    ("stair_000", lambda e: e["geometry"].__setitem__("clear_width_m", 0.5), "pilot.stair_dimensions"),
    ("building_000", lambda e: e["geometry"]["stair_void_local_m"]["max"].__setitem__(1, 5), "pilot.stair_void"),
    ("furniture_000_0", lambda e: e["bounds"]["min"].__setitem__(2, 2.5), "pilot.furniture_floor"),
])
def test_independent_rules_reject_bad_geometry(completed, entity_id, mutate, expected_rule):
    _, _, package = completed
    records = copy.deepcopy(package["records"])
    mutate(next(r for r in records if r["id"] == entity_id))
    assert expected_rule in {c["rule"] for c in check_geometry(records) if c["state"] == "fail"}


def test_full_city_is_not_silently_enabled():
    with pytest.raises(ValueError, match="008/009"):
        PilotSpec(building_count=80)
