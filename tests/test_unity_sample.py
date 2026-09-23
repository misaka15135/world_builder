"""Check the actual GLB container, geometry and target coordinate contract."""
from __future__ import annotations

import copy
import json
import struct
from pathlib import Path

import pytest

from world_builder.adapters.unity.sample import SampleExportError, export_sample


SOURCE = Path(__file__).resolve().parents[1] / "examples/two_storey_building.world.json"


def _glb(payload: bytes) -> tuple[dict, bytes]:
    magic, version, length = struct.unpack_from("<4sII", payload)
    assert (magic, version, length) == (b"glTF", 2, len(payload))
    json_size, json_tag = struct.unpack_from("<I4s", payload, 12)
    assert json_tag == b"JSON" and json_size % 4 == 0
    doc = json.loads(payload[20:20 + json_size])
    bin_size, bin_tag = struct.unpack_from("<I4s", payload, 20 + json_size)
    assert bin_tag == b"BIN\x00" and bin_size % 4 == 0
    binary = payload[28 + json_size:]
    assert len(binary) == bin_size == doc["buffers"][0]["byteLength"]
    return doc, binary


def test_glb_geometry_and_identity(tmp_path: Path) -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    original = copy.deepcopy(source)
    export_sample(source, tmp_path / "sample")
    assert source == original
    output = tmp_path / "sample"
    doc, binary = _glb((output / "library.glb").read_bytes())
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_to_glb_row_major"] == [-1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1]
    assert manifest["source_to_unity_row_major"] == [1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1]
    assert len(doc["nodes"]) == len(doc["meshes"]) == len(manifest["pieces"]) == 26
    assert [node["name"] for node in doc["nodes"]] == [piece["name"] for piece in manifest["pieces"]]
    assert all(node["extras"]["source_id"] == piece["source_id"]
               for node, piece in zip(doc["nodes"], manifest["pieces"]))
    window = next(node for node in doc["nodes"] if node["name"] == "east_bay_glass")
    primitive = doc["meshes"][window["mesh"]]["primitives"][0]
    accessor = doc["accessors"][primitive["attributes"]["POSITION"]]
    assert accessor["min"] == [-24, 5, 12] and accessor["max"] == [-23.75, 7, 14]
    for view in doc["bufferViews"]:
        assert view["byteOffset"] % 4 == 0
        assert view["byteOffset"] + view["byteLength"] <= len(binary)
    assert len([name for name in ("south_wall_left", "south_wall_right", "south_door_lintel")
                if name in {node["name"] for node in doc["nodes"]}]) == 3


def test_changed_source_fails_closed(tmp_path: Path) -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    next(record for record in source["records"] if record["id"] == "building_arcane_library")["attributes"]["storeys"] = 3
    with pytest.raises(SampleExportError, match="source sample changed"):
        export_sample(source, tmp_path / "changed")
    assert not (tmp_path / "changed").exists()
