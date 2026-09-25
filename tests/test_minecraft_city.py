"""Check the 512 m city block export: identity, coordinates and block types."""
from __future__ import annotations

import copy
import gzip
import hashlib
import io
import json
import struct
from pathlib import Path

import pytest

from world_builder.adapters.minecraft.city import CityExportError, export_city
from world_builder.storage.worldpkg import read_worldpkg

SOURCE = Path(__file__).resolve().parents[1] / "artifacts/benchmark-city-v1/city-first.worldpkg"
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
        assert (width, height, length) == (128, 36, 128)
        assert len(values) == width * height * length
        assert sum(1 for value in values if value) == chunk["non_air_blocks"] > 0


def test_block_types_land_at_the_source_coordinates(city) -> None:
    schematics = city["schematics"]
    lookup = {tuple(c["world_min"]): tuple(c["world_min"]) for c in city["manifest"]["chunks"]}

    def at(x: int, y: int, z: int) -> str:
        key = ((x // 128) * 128, -4, (z // 128) * 128)
        assert key in lookup, f"no chunk for {(x, y, z)}"
        return _block(schematics, list(key), x, y, z)

    assert at(*BRIDGE_DECK) == "minecraft:oak_planks"
    assert at(*WEST_ROAD) == "minecraft:stone_bricks"
    assert at(*RIVER_BED) == "minecraft:water"
    assert at(*EAST_BANK) == "minecraft:grass_block"
    # building_000 is one of the five generated interiors: shell, plank floor and a stair
    assert at(20, 3, -15) == "minecraft:smooth_stone"
    assert at(20, 2, -20) == "minecraft:oak_planks"
    assert at(28, 5, -22) == "minecraft:air"
    # building_005 has no generated interior, but is still a hollow shell with a usable east door
    assert at(308, 3, -15) == "minecraft:smooth_stone"
    assert at(308, 2, -20) == "minecraft:oak_planks"
    assert at(312, 5, -22) == "minecraft:air"           # inside the declared upper-floor void
    assert at(315, 2, -18) == "minecraft:oak_planks"   # ground slab runs under the doorway
    assert at(315, 3, -18) == "minecraft:air"          # east doorway, declared entry north 16..18
    assert at(315, 4, -18) == "minecraft:air"          # doorway is two blocks tall
    assert at(315, 5, -18) == "minecraft:oak_planks"   # upper floor slab forms the door head
    assert at(315, 3, -25) == "minecraft:smooth_stone"  # east wall away from the door
    # air above the road deck stays air, so the deck is one block thick
    assert at(42, 2, -200) == "minecraft:air"


def test_report_accounts_for_every_source_entity(city) -> None:
    report = json.loads((Path(city["result"]["output"]) / "export_report.json").read_text(encoding="utf-8"))
    entities = {r["id"] for r in city["package"]["records"] if r["record_type"] == "entity"}
    assert {item["source_id"] for item in report["items"]} == entities
    assert sum(report["summary"].values()) == len(entities)
    assert report["summary"]["failed"] == report["summary"]["unsupported"] == 0
    assert report["extensions"]["walkthrough"] == "not_run"


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
