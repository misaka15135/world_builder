"""Check the 512 m city block export: identity, coordinates and block types."""
from __future__ import annotations

import copy
import gzip
import hashlib
import io
import json
import math
import struct
from pathlib import Path

import pytest

from world_builder.adapters.minecraft.city import (CityExportError, _partition_boxes, _roof_boxes,
                                                   _shell_materials, export_city)
from world_builder.storage.worldpkg import read_worldpkg

SOURCE = Path(__file__).resolve().parents[1] / "artifacts/benchmark-city-v1/city-first.worldpkg"
MULTI_STOREY = Path(__file__).resolve().parents[1] / "artifacts/benchmark-city-v2/city-first.worldpkg"
BRIDGE_DECK = (256, 1, -271)      # bridge_main spans WIR x 252..260, north 268..274, up 1.6..2.0
WEST_ROAD = (42, 1, -200)         # road_west_0 spine spans WIR x 40..44
RIVER_BED = (256, 0, -100)        # river_main channel centre
EAST_BANK = (400, 0, -100)        # sand-free terrain proxy east of the channel


def _read_schem(path: Path) -> tuple[dict, bytes, int, int, int]:
    raw = gzip.decompress(path.read_bytes())
    assert raw[0] == 10  # root TAG_Compound
    cursor = 3

    def read_payload(tag: int):
        nonlocal cursor
        if tag == 10:
            out = {}
            while raw[cursor] != 0:
                inner = raw[cursor]
                cursor += 1
                name_len = struct.unpack_from(">H", raw, cursor)[0]
                cursor += 2
                name = raw[cursor:cursor + name_len].decode("utf-8")
                cursor += name_len
                out[name] = read_payload(inner)
            cursor += 1
            return out
        if tag == 3:
            value = struct.unpack_from(">i", raw, cursor)[0]
            cursor += 4
            return value
        if tag == 2:
            value = struct.unpack_from(">h", raw, cursor)[0]
            cursor += 2
            return value
        if tag == 8:
            length = struct.unpack_from(">H", raw, cursor)[0]
            cursor += 2
            value = raw[cursor:cursor + length].decode("utf-8")
            cursor += length
            return value
        if tag == 7:
            length = struct.unpack_from(">i", raw, cursor)[0]
            cursor += 4
            value = raw[cursor:cursor + length]
            cursor += length
            return value
        if tag == 11:
            length = struct.unpack_from(">i", raw, cursor)[0]
            cursor += 4
            value = list(struct.unpack_from(">" + "i" * length, raw, cursor))
            cursor += 4 * length
            return value
        if tag == 9:
            element = raw[cursor]
            cursor += 1
            length = struct.unpack_from(">i", raw, cursor)[0]
            cursor += 4
            return [read_payload(element) for _ in range(length)]
        raise AssertionError(f"unsupported tag {tag}")

    root_name_len = struct.unpack_from(">H", raw, 1)[0]
    cursor = 3 + root_name_len
    root = read_payload(10)
    schematic = root["Schematic"]
    palette = {index: block for block, index in schematic["Blocks"]["Palette"].items()}
    packed = schematic["Blocks"]["Data"]
    values = []
    position = 0
    while position < len(packed):
        value = shift = 0
        while True:
            part = packed[position]
            position += 1
            value |= (part & 0x7F) << shift
            if not part & 0x80:
                break
            shift += 7
        values.append(value)
    return palette, bytes(values), schematic["Width"], schematic["Height"], schematic["Length"]


def _block(schematics: dict, world_min: list[int], x: int, y: int, z: int) -> str:
    palette, values, width, height, length = schematics[tuple(world_min)]
    ix, iy, iz = x - world_min[0], y - world_min[1], z - world_min[2]
    return palette[values[ix + iz * width + iy * width * length]]


@pytest.fixture(scope="module")
def city(tmp_path_factory) -> dict:
    package, _ = read_worldpkg(SOURCE)
    output = tmp_path_factory.mktemp("minecraft-city") / "out"
    result = export_city(package, output, include_interiors=True)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    schematics = {}
    for chunk in manifest["chunks"]:
        schematics[tuple(chunk["world_min"])] = _read_schem(output / chunk["path"])
    return {"package": package, "result": result, "manifest": manifest, "schematics": schematics}


def test_city_export_covers_the_revision_with_blocks(city) -> None:
    manifest, result = city["manifest"], city["result"]
    assert result["chunk_count"] == len(manifest["chunks"]) == 16
    assert manifest["source_revision_id"] == city["package"]["manifest"]["revision_id"]
    assert manifest["data_version"] == 4671
    assert manifest["source_to_minecraft_row_major"] == [1, 0, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1]
    for chunk in manifest["chunks"]:
        data = (Path(result["output"]) / chunk["path"]).read_bytes()
        assert "sha256:" + hashlib.sha256(data).hexdigest() == chunk["schem_sha256"]
        palette, values, width, height, length = city["schematics"][tuple(chunk["world_min"])]
        assert (width, height, length) == (128, 33, 128)
        assert len(values) == width * height * length
        assert sum(1 for value in values if value) == chunk["non_air_blocks"] > 0


def test_block_types_land_at_the_source_coordinates(city) -> None:
    schematics = city["schematics"]
    lookup = {tuple(c["world_min"]): tuple(c["world_min"]) for c in city["manifest"]["chunks"]}

    def at(x: int, y: int, z: int) -> str:
        key = ((x // 128) * 128, city["manifest"]["region_y_m"][0], (z // 128) * 128)
        assert key in lookup, f"no chunk for {(x, y, z)}"
        return _block(schematics, list(key), x, y, z)

    assert at(*BRIDGE_DECK) == "minecraft:oak_planks"
    assert at(*WEST_ROAD) == "minecraft:stone_bricks"
    assert at(*RIVER_BED) == "minecraft:water"
    assert at(*EAST_BANK) == "minecraft:grass_block"
    # Buildings vary by seed, so every probe point is derived from the source entity.
    for source_id in ("building_000", "building_005"):
        entity = next(r for r in city["package"]["records"]
                      if r.get("id") == source_id and r["record_type"] == "entity")
        (bx0, bn0, bz0), (bx1, bn1, _) = entity["bounds"]["min"], entity["bounds"]["max"]
        slab = math.floor(bz0)
        inner_x, inner_z = int(bx0) + 2, -(int(bn0) + 2)
        assert at(inner_x, slab, inner_z) == "minecraft:oak_planks"      # ground floor slab
        assert at(inner_x, slab + 1, inner_z) == "minecraft:air"         # hollow interior
        assert at(int(bx0), slab + 1, inner_z) == "minecraft:smooth_stone"  # west wall
        door_z = -(int(bn0) + 3)                                         # declared east entry, north n0+2..n0+4
        assert at(int(bx1) - 1, slab, door_z) == "minecraft:oak_planks"  # slab runs under the doorway
        assert at(int(bx1) - 1, slab + 1, door_z) == "minecraft:air"     # doorway
        assert at(int(bx1) - 1, slab + 2, door_z) == "minecraft:air"     # doorway is two blocks tall
        if entity["attributes"]["storeys"] >= 2:
            upper = slab + int(entity["geometry"]["storey_height_m"])
            assert at(int(bx0) + 6, upper, inner_z) == "minecraft:oak_planks"  # upper slab over the rooms
    # air above the road deck stays air, so the deck is one block thick
    assert at(42, 2, -200) == "minecraft:air"


def test_report_accounts_for_every_source_entity(city) -> None:
    report = json.loads((Path(city["result"]["output"]) / "export_report.json").read_text(encoding="utf-8"))
    entities = {r["id"] for r in city["package"]["records"] if r["record_type"] == "entity"}
    assert {item["source_id"] for item in report["items"]} == entities
    assert sum(report["summary"].values()) == len(entities)
    assert report["summary"]["failed"] == report["summary"]["unsupported"] == 0
    assert report["extensions"]["walkthrough"] == "not_run"


def test_furnished_buildings_place_furniture_blocks(city) -> None:
    boxes = city["manifest"]["boxes"]
    placed = [box for box in boxes if box["source_id"].startswith("furniture_")]
    assert placed, "furniture should reach the blocks, not stay a sidecar record"
    # The city.1 hand interiors only hold reading tables.
    assert {box["block"] for box in placed} == {"minecraft:oak_slab"}
    report = json.loads((Path(city["result"]["output"]) / "export_report.json").read_text(encoding="utf-8"))
    items = {item["source_id"]: item["classification"] for item in report["items"]}
    assert items[placed[0]["source_id"]] == "approximated"


def test_non_city_snapshot_fails_closed(tmp_path: Path) -> None:
    package, _ = read_worldpkg(SOURCE)
    broken = copy.deepcopy(package)
    next(r for r in broken["records"] if r.get("kind") == "bridge")["geometry"]["representation"] = "sphere"
    with pytest.raises(CityExportError):
        export_city(broken, tmp_path / "broken")


def test_export_does_not_modify_the_source_package(city, tmp_path: Path) -> None:
    package, _ = read_worldpkg(SOURCE)
    before = copy.deepcopy(package)
    export_city(package, tmp_path / "again")
    assert package == before


def test_multi_storey_city_places_slabs_and_no_invented_partitions(tmp_path: Path) -> None:
    package, _ = read_worldpkg(MULTI_STOREY)
    output = tmp_path / "v2"
    export_city(package, output, include_interiors=True)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    boxes = manifest["boxes"]
    buildings = [r for r in package["records"] if r.get("kind") == "building"]
    assert len(buildings) == 80
    assert len({r["attributes"]["storeys"] for r in buildings}) >= 2, "storey counts should vary"
    assert any("_floor" in box["source_id"] for box in boxes), "multi-storey slabs should reach the blocks"
    # This revision predates declared partitions, so the adapter must not invent
    # walls the source never described.
    assert not any("partition" in box["source_id"] for box in boxes)
    for building in buildings:
        (bx0, bn0, _), (bx1, bn1, _) = building["bounds"]["min"], building["bounds"]["max"]
        own = [box for box in boxes if box["source_id"].startswith(building["id"] + "_")]
        assert own, building["id"]
        for box in own:
            assert bx0 - 1e-6 <= box["x0"] and box["x1"] <= bx1 + 1e-6, (building["id"], box["source_id"])
            assert -bn1 - 1e-6 <= box["z0"] and box["z1"] <= -bn0 + 1e-6, (building["id"], box["source_id"])


def test_partitions_follow_the_source_declaration() -> None:
    storey = {"id": "storey_x", "kind": "storey", "parent_id": "b",
              "bounds": {"min": [0, 0, 0], "max": [16, 16, 3]}}
    wall = {"id": "partition_x", "kind": "partition", "parent_id": "storey_x",
            "bounds": {"min": [1, 7, 2.2], "max": [11, 8, 4.8]},
            "attributes": {"opening": {"side": "west", "width_m": 2.0, "height_m": 2.0}}}
    entities = {storey["id"]: storey, wall["id"]: wall}
    parts = _partition_boxes({"id": "b"}, entities, [storey])
    assert parts, "a declared partition must reach the blocks"
    main = next(part for part in parts if part["source_id"] == "partition_x")
    assert main["x0"] == 3.0, "the declared two-metre opening stays clear on the west end"
    assert main["x1"] == 11.0 and main["z0"] == -8.0 and main["z1"] == -7.0
    broken = copy.deepcopy(entities)
    broken["partition_x"]["attributes"]["opening"]["side"] = "north"
    with pytest.raises(CityExportError):
        _partition_boxes({"id": "b"}, broken, [storey])


def test_style_profiles_pick_different_shell_materials() -> None:
    assert _shell_materials("arcane_medieval") == ("minecraft:smooth_stone", "minecraft:oak_planks")
    assert _shell_materials("modern_grid") == ("minecraft:light_gray_concrete", "minecraft:smooth_stone")


def test_roof_style_drives_the_silhouette() -> None:
    flat = _roof_boxes("b", 0, 10, 0, 12, 20, 0.4, "flat", "minecraft:oak_planks")
    assert len(flat) == 1
    gable = _roof_boxes("b", 0, 10, 0, 12, 20, 1.2, "gable", "minecraft:oak_planks")
    assert len(gable) == 2
    assert gable[-1]["z0"] > gable[0]["z0"] and gable[-1]["z1"] < gable[0]["z1"], "a gable narrows along the north axis"
    assert gable[-1]["x0"] == gable[0]["x0"], "a gable keeps its east-west span"
    spire = _roof_boxes("b", 0, 10, 0, 12, 20, 3.0, "spire", "minecraft:oak_planks")
    assert len(spire) == 3
    assert spire[-1]["x0"] > spire[0]["x0"] and spire[-1]["z0"] > spire[0]["z0"], "a spire narrows on both axes"
    assert spire[-1]["y1"] == 20 and spire[0]["y0"] == 17, "steps stack from the eaves to the ridge"
    assert spire[0]["x0"] == 0 and spire[0]["z1"] == 0, "the lowest step still covers the footprint"
