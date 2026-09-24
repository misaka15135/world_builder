"""Check source-derived city geometry, identity and declared omissions."""
from __future__ import annotations

import copy
import json
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
