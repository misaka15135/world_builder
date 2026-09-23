from __future__ import annotations

import copy
import hashlib
import json
import os
import sqlite3
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from world_builder.wir.transforms import (
    WIR_TO_GLTF,
    WIR_TO_IFC,
    WIR_TO_MINECRAFT,
    WIR_TO_UNITY,
    determinant,
    requires_reflection_handling,
    round_trip,
)
from world_builder.wir.validator import PackageValidationError, load_and_validate, validate_package

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "wir-package-0.1.0.schema.json"
EXAMPLES = sorted((ROOT / "examples").glob("*.world.json"))


def load_example(name: str) -> dict:
    return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))


def issue_codes(exc: PackageValidationError) -> set[str]:
    return {issue.code for issue in exc.issues}


def test_schema_is_valid_draft_2020_12() -> None:
    Draft202012Validator.check_schema(json.loads(SCHEMA.read_text(encoding="utf-8")))


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda path: path.stem)
def test_hand_written_examples_validate_and_round_trip(path: Path, tmp_path: Path) -> None:
    package = load_and_validate(path)
    copy_path = tmp_path / path.name
    copy_path.write_text(json.dumps(package, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    reloaded = load_and_validate(copy_path)
    assert [record["id"] for record in reloaded["records"]] == [record["id"] for record in package["records"]]
    assert [record for record in reloaded["records"] if record["record_type"] == "relation"] == [record for record in package["records"] if record["record_type"] == "relation"]


def test_missing_units_fails_schema() -> None:
    package = load_example("river_bridge_cross_chunk.world.json")
    del package["manifest"]["units"]
    with pytest.raises(PackageValidationError) as captured:
        validate_package(package)
    assert "schema.invalid" in issue_codes(captured.value)


def test_unknown_required_capability_fails_schema() -> None:
    package = load_example("river_bridge_cross_chunk.world.json")
    package["manifest"]["required_capabilities"].append("wir.telepathy/9.9")
    with pytest.raises(PackageValidationError) as captured:
        validate_package(package)
    assert "schema.invalid" in issue_codes(captured.value)


def test_dangling_relation_reference_fails_semantics() -> None:
    package = load_example("river_bridge_cross_chunk.world.json")
    relation = next(record for record in package["records"] if record["record_type"] == "relation")
    relation["target_ids"] = ["entity_missing"]
    with pytest.raises(PackageValidationError) as captured:
        validate_package(package)
    assert "reference.relation_entity_missing" in issue_codes(captured.value)


def test_containment_cycle_fails_semantics() -> None:
    package = load_example("river_bridge_cross_chunk.world.json")
    entities = {record["id"]: record for record in package["records"] if record["record_type"] == "entity"}
    entities["world_river_bridge"]["parent_id"] = "bridge_moonspan"
    with pytest.raises(PackageValidationError) as captured:
        validate_package(package)
    assert "graph.containment_cycle" in issue_codes(captured.value)


def test_timeout_cannot_claim_infeasible() -> None:
    package = load_example("two_storey_building.world.json")
    recipe = next(record for record in package["records"] if record["record_type"] == "recipe")
    recipe["outcome"] = {"termination_reason": "timeout", "feasibility": "infeasible", "proof_ref": "fake"}
    with pytest.raises(PackageValidationError) as captured:
        validate_package(package)
    assert {"outcome.infeasible_without_proof", "outcome.uncertain_termination"} & issue_codes(captured.value)


def test_missing_and_corrupt_local_resources_fail(tmp_path: Path) -> None:
    package = load_example("two_storey_building.world.json")
    asset = next(record for record in package["records"] if record["record_type"] == "asset")
    package["manifest"]["package_mode"] = "self_contained"
    asset["uri"] = "assets/chair.glb"
    package_path = tmp_path / "resource_test.world.json"
    package_path.write_text(json.dumps(package), encoding="utf-8")
    with pytest.raises(PackageValidationError) as captured:
        load_and_validate(package_path)
    assert "resource.missing" in issue_codes(captured.value)

    resource = tmp_path / "assets" / "chair.glb"
    resource.parent.mkdir()
    resource.write_bytes(b"not the expected chair")
    with pytest.raises(PackageValidationError) as captured:
        load_and_validate(package_path)
    assert "resource.hash_mismatch" in issue_codes(captured.value)

    asset["content_hash"] = "sha256:" + hashlib.sha256(resource.read_bytes()).hexdigest()
    package_path.write_text(json.dumps(package), encoding="utf-8")
    load_and_validate(package_path)


@pytest.mark.parametrize("matrix", [WIR_TO_GLTF, WIR_TO_MINECRAFT, WIR_TO_UNITY, WIR_TO_IFC])
def test_coordinate_round_trip(matrix) -> None:
    point = (2.25, -7.5, 11.125)
    assert round_trip(matrix, point) == pytest.approx(point, abs=1e-12)


def test_only_unity_matrix_requires_reflection_handling() -> None:
    assert determinant(WIR_TO_UNITY) == pytest.approx(-1.0)
    assert requires_reflection_handling(WIR_TO_UNITY)
    assert determinant(WIR_TO_GLTF) == pytest.approx(1.0)
    assert not requires_reflection_handling(WIR_TO_GLTF)


def test_sqlite_initial_migration_is_transaction_ready(tmp_path: Path) -> None:
    database = tmp_path / "wir.sqlite3"
    migration = (ROOT / "storage" / "migrations" / "0001_initial.sql").read_text(encoding="utf-8")
    with sqlite3.connect(database) as connection:
        connection.executescript(migration)
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")}
        assert {"worlds", "revisions", "records", "resource_blobs", "revision_resources", "branches", "import_events"} <= tables
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_failed_revision_transaction_does_not_move_branch_head(tmp_path: Path) -> None:
    database = tmp_path / "rollback.sqlite3"
    migration = (ROOT / "storage" / "migrations" / "0001_initial.sql").read_text(encoding="utf-8")
    with sqlite3.connect(database) as connection:
        connection.executescript(migration)
        connection.execute("INSERT INTO worlds VALUES (?, ?, ?, ?)", ("world_test", "0.1.0", "2026-09-22T00:00:00Z", None))
        connection.commit()
        connection.execute("BEGIN")
        connection.execute(
            "INSERT INTO revisions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("revision_staged", "world_test", "[]", "test", "2026-09-22T00:00:00Z", "sha256:" + "0" * 64, "{}", 0),
        )
        connection.rollback()
        assert connection.execute("SELECT count(*) FROM revisions").fetchone()[0] == 0
        assert connection.execute("SELECT head_revision_id FROM worlds WHERE world_id='world_test'").fetchone()[0] is None


def test_same_filesystem_atomic_replace_mechanism(tmp_path: Path) -> None:
    staged = tmp_path / "package.staged"
    published = tmp_path / "package.worldpkg"
    with staged.open("wb") as handle:
        handle.write(b"complete package")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(staged, published)
    assert not staged.exists()
    assert published.read_bytes() == b"complete package"
