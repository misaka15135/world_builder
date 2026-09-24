"""Check source-derived city geometry, identity and declared omissions."""
from __future__ import annotations

import copy
import json
import hashlib
import math
import struct
from pathlib import Path

import pytest

from world_builder.adapters.unity.city import CityExportError, export_city
from world_builder.storage.worldpkg import read_worldpkg


SOURCE = Path(__file__).resolve().parents[1] / "artifacts/benchmark-city-v1/city-first.worldpkg"


def test_city_export_from_verified_package(tmp_path: Path) -> None:
    package, _ = read_worldpkg(SOURCE)
    original = copy.deepcopy(package)
    result = export_city(package, tmp_path / "city")
    assert package == original
    assert result["piece_count"] == 176
    output = tmp_path / "city"
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((output / "export_report.json").read_text(encoding="utf-8"))
    assert manifest["source_revision_id"] == package["manifest"]["revision_id"]
    assert sum(report["summary"].values()) == 294
    assert report["summary"] == {"preserved": 94, "approximated": 82,
                                  "omitted": 118, "unsupported": 0, "failed": 0}
    assert {item["source_id"] for item in report["items"]} == {
        r["id"] for r in package["records"] if r["record_type"] == "entity"}
    pieces = manifest["pieces"]
    assert len(pieces) == len({p["name"] for p in pieces}) == 176
    bridge = next(p for p in pieces if p["source_id"] == "bridge_main")
    assert bridge["bounds_wir_m"] == [[252, 268, 1.6], [260, 274, 2.0]]
    glb = (output / "city.glb").read_bytes()
    assert struct.unpack_from("<4sII", glb) == (b"glTF", 2, len(glb))
    json_size, tag = struct.unpack_from("<I4s", glb, 12)
    assert tag == b"JSON"
    doc = json.loads(glb[20:20 + json_size])
    assert len(doc["nodes"]) == len(doc["meshes"]) == len(pieces)
    assert [n["extras"]["source_id"] for n in doc["nodes"]] == [p["source_id"] for p in pieces]


def test_unsupported_city_geometry_fails_closed(tmp_path: Path) -> None:
    package, _ = read_worldpkg(SOURCE)
    next(r for r in package["records"] if r.get("kind") == "road")["geometry"]["representation"] = "sphere"
    with pytest.raises((CityExportError, ValueError)):
        export_city(package, tmp_path / "changed")
    assert not (tmp_path / "changed").exists()


def test_generated_interiors_have_traceable_openings_and_stairs(tmp_path: Path) -> None:
    package, _ = read_worldpkg(SOURCE)
    result = export_city(package, tmp_path / "interiors", include_interiors=True)
    assert result["piece_count"] == 346
    output = tmp_path / "interiors"
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((output / "export_report.json").read_text(encoding="utf-8"))
    assert manifest["source_revision_id"] == package["manifest"]["revision_id"]
    assert manifest["adapter_version"] == "0.1.0-city.2"
    assert report["summary"] == {"preserved": 94, "approximated": 107,
                                  "omitted": 93, "unsupported": 0, "failed": 0}
    pieces = manifest["pieces"]
    assert len(pieces) == len({p["name"] for p in pieces}) == 346
    assert sum("_tread_" in p["name"] for p in pieces) == 100
    assert {p["source_id"] for p in pieces if "_tread_" in p["name"]} == {
        f"stair_{i:03}" for i in range(5)}
    ground = next(p for p in pieces if p["name"] == "building_000_ground_floor")
    lintel = next(p for p in pieces if p["name"] == "building_000_east_door_lintel")
    assert ground["source_id"] == "storey_000_0"
    assert lintel["bounds_wir_m"] == [[31.8, 16, 4.6], [32, 18, 8.0]]
    upper = [p for p in pieces if p["name"].startswith("building_000_upper_floor_")]
    assert len(upper) == 4 and {p["source_id"] for p in upper} == {"storey_000_1"}
    assert all(not (p["bounds_wir_m"][0][0] < 28 < p["bounds_wir_m"][1][0]
                        and p["bounds_wir_m"][0][1] < 22 < p["bounds_wir_m"][1][1])
               for p in upper)
    assert {p["source_id"] for p in pieces if "furniture_" in p["name"]} == {
        f"furniture_{i:03}_{floor}" for i in range(5) for floor in range(2)}


def test_chunked_city_covers_original_boxes_with_bounded_glbs(tmp_path: Path) -> None:
    package, _ = read_worldpkg(SOURCE)
    export_city(package, tmp_path / "whole", include_interiors=True)
    result = export_city(package, tmp_path / "chunked", include_interiors=True, chunked=True)
    whole = json.loads((tmp_path / "whole/manifest.json").read_text(encoding="utf-8"))
    manifest = json.loads((tmp_path / "chunked/manifest.json").read_text(encoding="utf-8"))
    report = json.loads((tmp_path / "chunked/export_report.json").read_text(encoding="utf-8"))
    assert result["chunk_count"] == 16
    assert result["piece_count"] == 420
    assert manifest["format"] == "unity-glb-city-0.3"
    assert report["summary"] == {"preserved": 94, "approximated": 107,
                                  "omitted": 93, "unsupported": 0, "failed": 0}
    assert len({p["name"] for p in manifest["pieces"]}) == 420
    originals = {p["name"]: p for p in whole["pieces"]}
    volumes: dict[str, float] = {}
    for chunk in manifest["chunks"]:
        data = (tmp_path / "chunked" / chunk["path"]).read_bytes()
        assert "sha256:" + hashlib.sha256(data).hexdigest() == chunk["glb_sha256"]
        json_size, tag = struct.unpack_from("<I4s", data, 12)
        assert tag == b"JSON"
        doc = json.loads(data[20:20 + json_size])
        members = [p for p in manifest["pieces"] if p["chunk_id"] == chunk["id"]]
        assert len(members) == chunk["piece_count"] == len(doc["nodes"])
        assert [n["name"] for n in doc["nodes"]] == [p["name"] for p in members]
        assert [n["extras"]["source_id"] for n in doc["nodes"]] == [p["source_id"] for p in members]
        for piece in members:
            name = piece["name"].rsplit("__c", 1)[0]
            original = originals[name]
            low, high = piece["bounds_wir_m"]
            olo, ohi = original["bounds_wir_m"]
            assert piece["source_id"] == original["source_id"]
            assert all(olo[i] <= low[i] < high[i] <= ohi[i] for i in range(3))
            assert high[0] - low[0] <= 128 and high[1] - low[1] <= 128
            assert math.dist(low, high) < 182
            volumes[name] = volumes.get(name, 0) + math.prod(high[i] - low[i] for i in range(3))
    assert set(volumes) == set(originals)
    for name, original in originals.items():
        low, high = original["bounds_wir_m"]
        assert volumes[name] == pytest.approx(math.prod(high[i] - low[i] for i in range(3)))
