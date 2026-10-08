"""The two study exports must derive from one stable geometry revision."""
from __future__ import annotations

import gzip
import json
import struct

from world_builder.samples.street_house import export_study


def test_street_house_exports_share_geometry_and_are_repeatable(tmp_path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    manifest = export_study(first)
    assert manifest == export_study(second)
    for name in ("design.json", "manifest.json", "street_house.glb", "street_house.schem"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    design = json.loads((first / "design.json").read_text(encoding="utf-8"))
    assert design["geometry_sha256"] == manifest["geometry_sha256"]
    assert all(design["static_checks"].values())

    glb = (first / "street_house.glb").read_bytes()
    magic, version, length = struct.unpack_from("<4sII", glb)
    assert (magic, version, length) == (b"glTF", 2, len(glb))
    json_length, chunk_type = struct.unpack_from("<I4s", glb, 12)
    assert chunk_type == b"JSON"
    gltf = json.loads(glb[20:20 + json_length])
    assert len(gltf["nodes"]) == manifest["piece_count"]

    nbt = gzip.decompress((first / "street_house.schem").read_bytes())
    assert b"Schematic" in nbt and b"DataVersion" in nbt
    assert b"minecraft:oak_stairs[facing=north" in nbt
    assert b"minecraft:glass" in nbt
