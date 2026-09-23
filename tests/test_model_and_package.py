from __future__ import annotations

import copy
import json
import stat
import zipfile
from pathlib import Path

import pytest

from world_builder.generation.model import (
    FixtureBytes, FixtureProvider, HttpJSONProvider, ModelContractError,
    compile_spec, publish_accepted, replay_spec,
)
from world_builder.generation.pipeline import generate
from world_builder.generation.spec import canonical
from world_builder.storage.repository import Repository, StoreError
from world_builder.storage.worldpkg import _safe_name, export_worldpkg, import_worldpkg, read_worldpkg

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/pilot_model_response.json"


@pytest.fixture
def source_world(tmp_path):
    repository = Repository(tmp_path / "source")
    prepared = compile_spec("一座河畔魔法小镇", 17, FixtureProvider(FIXTURE))
    spec = publish_accepted(repository, prepared)
    result = generate(spec, repository)
    assert result.termination_reason == "completed", result.to_dict()
    return spec, repository


def test_accepted_response_is_replayable_without_provider(source_world):
    spec, repository = source_world
    package = repository.load(spec.world_id)
    asset = next(r for r in package["records"] if r["id"] == "asset_model_response")
    assert asset["content_hash"] == spec.accepted_response_hash
    assert (repository.root / asset["uri"]).read_bytes() == FIXTURE.read_bytes()
    assert next(r for r in package["records"] if r["id"] == "recipe_terrain")["accepted_model_response_hash"] == asset["content_hash"]
    assert next(r for r in package["records"] if r["record_type"] == "world_spec")["extensions"]["model_provenance"]["model_id"] == "fixture-pilot-v1"
    assert replay_spec(Repository(repository.root), spec.world_id) == spec
    assert generate(replay_spec(repository, spec.world_id), repository).stages == []


@pytest.mark.parametrize("change, code", [
    (lambda r: r["candidate"].__setitem__("building_count", 80), "contract.candidate_invalid"),
    (lambda r: r["candidate"].__setitem__("execute", "erase"), "contract.candidate_shape"),
    (lambda r: r["usage"].__setitem__("output_tokens", -1), "contract.usage"),
    (lambda r: r.__setitem__("contract_version", "9.0.0"), "contract.version"),
])
def test_bad_model_response_rejected_before_publication(change, code, tmp_path):
    response = json.loads(FIXTURE.read_bytes())
    change(response)
    repository = Repository(tmp_path)
    with pytest.raises(ModelContractError) as captured:
        publish_accepted(repository, compile_spec("River city", 1, FixtureBytes(canonical(response))))
    assert captured.value.code == code
    assert not (repository.root / "assets").exists()


def test_model_token_budget_and_endpoint_validation():
    response = json.loads(FIXTURE.read_bytes())
    response["usage"] = {"input_tokens": 70, "output_tokens": 31}
    with pytest.raises(ModelContractError, match="token_budget"):
        compile_spec("River city", 1, FixtureBytes(canonical(response)), max_total_tokens=100)
    with pytest.raises(ModelContractError, match="HTTPS"):
        HttpJSONProvider("http://example.com/model", "model")


def test_generic_http_provider_sends_bounded_contract(monkeypatch):
    response = FIXTURE.read_bytes()
    observed = {}

    class Reply:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self, n):
            observed["read_limit"] = n
            return response

    def open_request(request, timeout):
        observed["url"] = request.full_url
        observed["body"] = json.loads(request.data)
        observed["timeout"] = timeout
        return Reply()

    class Opener:
        open = staticmethod(open_request)

    monkeypatch.setattr("urllib.request.build_opener", lambda *handlers: Opener())
    provider = HttpJSONProvider("https://model.example/spec", "trial-v1", timeout_s=3)
    spec = compile_spec("Arcane river city", 4, provider).spec
    assert spec.scenario == "riverside"
    assert observed == {"url": "https://model.example/spec", "body": {
        "contract_version": "0.1.0", "model_id": "trial-v1", "prompt": "Arcane river city", "seed": 4,
        "response_fields": ["building_count", "interior_count", "layout_profile", "lock_stair_void", "scenario"],
        "response_format": "json_object"}, "timeout": 3, "read_limit": 65537}


def test_worldpkg_round_trip_creates_import_revision_and_preserves_source(source_world, tmp_path):
    spec, repository = source_world
    source = repository.load(spec.world_id)
    destination = tmp_path / "world.worldpkg"
    checksum = export_worldpkg(repository, spec.world_id, destination)
    assert checksum.startswith("sha256:")
    with zipfile.ZipFile(destination) as archive:
        assert all(info.extract_version >= 45 for info in archive.infolist())
    parsed, blobs = read_worldpkg(destination)
    assert parsed == source
    assert len(blobs) == 2
    second = tmp_path / "same.worldpkg"
    assert export_worldpkg(repository, spec.world_id, second) == checksum
    target = Repository(tmp_path / "target")
    world_id, imported_revision = import_worldpkg(target, destination)
    assert world_id == spec.world_id
    imported = target.load(world_id)
    assert imported["manifest"]["revision_id"] == imported_revision
    assert imported_revision != source["manifest"]["revision_id"]
    assert imported["manifest"]["extensions"]["import_source"]["revision_id"] == source["manifest"]["revision_id"]
    assert {r["id"]: r for r in imported["records"] if r["record_type"] == "entity"} == {
        r["id"]: r for r in source["records"] if r["record_type"] == "entity"}
    assert replay_spec(target, world_id) == spec
    assert repository.head(world_id) == source["manifest"]["revision_id"]
    with target.connect() as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_repeat_import_preserves_old_revision(source_world, tmp_path):
    spec, repository = source_world
    destination = tmp_path / "world.worldpkg"
    export_worldpkg(repository, spec.world_id, destination)
    target = Repository(tmp_path / "target")
    _, first = import_worldpkg(target, destination)
    _, second = import_worldpkg(target, destination)
    assert first != second
    assert target.load(spec.world_id, first)["manifest"]["revision_id"] == first
    assert target.load(spec.world_id)["manifest"]["revision_id"] == second


def rewrite_archive(source: Path, destination: Path, mutate):
    with zipfile.ZipFile(source) as reader, zipfile.ZipFile(destination, "w", allowZip64=True) as writer:
        for info in reader.infolist():
            data = reader.read(info)
            name, data, info = mutate(info.filename, data, info)
            writer.writestr(info, data)


def test_corrupt_resource_does_not_move_import_head(source_world, tmp_path):
    spec, repository = source_world
    good = tmp_path / "good.worldpkg"
    export_worldpkg(repository, spec.world_id, good)
    bad = tmp_path / "bad.worldpkg"
    def corrupt(name, data, info):
        return name, data + b"corrupt" if name.startswith("assets/") else data, info
    rewrite_archive(good, bad, corrupt)
    target = Repository(tmp_path / "target")
    _, old = import_worldpkg(target, good)
    with pytest.raises(StoreError, match="resource.package_invalid"):
        import_worldpkg(target, bad)
    assert target.head(spec.world_id) == old
    with target.connect() as db:
        assert db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 1


@pytest.mark.parametrize("bad_name", ["../escape", "/absolute", "assets//bad", "C:/drive"])
def test_archive_path_escape_is_rejected(tmp_path, bad_name):
    path = tmp_path / "bad.worldpkg"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", b"{}")
        archive.writestr("snapshot/records.jsonl", b"{}\n")
        archive.writestr(bad_name, b"x")
    with pytest.raises(StoreError, match="resource.package_path"):
        read_worldpkg(path)


def test_duplicate_and_symlink_archive_members_are_rejected(tmp_path):
    assert not _safe_name("assets\\bad")
    duplicate = tmp_path / "duplicate.worldpkg"
    with zipfile.ZipFile(duplicate, "w") as archive:
        archive.writestr("manifest.json", b"{}")
        archive.writestr("snapshot/records.jsonl", b"{}\n")
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr("snapshot/records.jsonl", b"{}\n")
    with pytest.raises(StoreError, match="resource.package_members"):
        read_worldpkg(duplicate)
    symlink = tmp_path / "symlink.worldpkg"
    with zipfile.ZipFile(symlink, "w") as archive:
        archive.writestr("manifest.json", b"{}")
        archive.writestr("snapshot/records.jsonl", b"{}\n")
        info = zipfile.ZipInfo("assets/sha256/" + "0" * 64)
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, b"../../outside")
    with pytest.raises(StoreError, match="resource.package_path"):
        read_worldpkg(symlink)
