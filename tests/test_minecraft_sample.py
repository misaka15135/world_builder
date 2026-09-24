"""Independent format and geometry checks for the bounded Minecraft sample."""
from __future__ import annotations

import copy
import gzip
import json
import struct
from pathlib import Path

import pytest

from world_builder.adapters.minecraft.sample import SampleExportError, export_sample


SOURCE = Path(__file__).resolve().parents[1] / "examples/two_storey_building.world.json"


def _read_nbt(payload: bytes) -> dict:
    data = memoryview(payload)
    cursor = 0

    def take(count: int) -> bytes:
        nonlocal cursor
        result = bytes(data[cursor:cursor + count])
        assert len(result) == count
        cursor += count
        return result

    def number(fmt: str) -> int:
        return struct.unpack(fmt, take(struct.calcsize(fmt)))[0]

    def string() -> str:
        return take(number(">H")).decode("utf-8")

    def value(tag: int):
        if tag == 2:
            return number(">h")
        if tag == 3:
            return number(">i")
        if tag == 7:
            return take(number(">i"))
        if tag == 8:
            return string()
        if tag == 9:
            child_type, count = number(">B"), number(">i")
            return [value(child_type) for _ in range(count)]
        if tag == 10:
            result = {}
            while child_type := number(">B"):
                name = string()
                assert name not in result
                result[name] = value(child_type)
            return result
        if tag == 11:
            return [number(">i") for _ in range(number(">i"))]
        raise AssertionError(f"unexpected NBT tag {tag}")

    assert number(">B") == 10
    assert string() == ""
    root = value(10)
    assert cursor == len(data)
    return root


def _indices(payload: bytes) -> list[int]:
    result = []
    cursor = 0
    while cursor < len(payload):
        value = 0
        shift = 0
        while True:
            byte = payload[cursor]
            cursor += 1
            value |= (byte & 0x7f) << shift
            if not byte & 0x80:
                break
            shift += 7
            assert shift < 35
        result.append(value)
    return result


def test_sponge_v3_sample_round_trip_and_target_geometry(tmp_path: Path) -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    original = copy.deepcopy(source)
    out = tmp_path / "minecraft-sample"
    manifest = export_sample(source, out, data_version=4671)
    assert source == original
    assert manifest["offline_checks"]["game_load"] == "not_run"
    raw = (out / "library.schem").read_bytes()
    nbt = _read_nbt(gzip.decompress(raw))["Schematic"]
    assert (nbt["Version"], nbt["DataVersion"]) == (3, 4671)
    assert (nbt["Width"], nbt["Height"], nbt["Length"]) == (20, 9, 16)
    assert nbt["Offset"] == [0, 0, 0]
    assert nbt["Blocks"]["BlockEntities"] == []
    palette = nbt["Blocks"]["Palette"]
    indices = _indices(nbt["Blocks"]["Data"])
    assert len(indices) == 20 * 9 * 16

    def block(x: int, y: int, z: int) -> str:
        index = indices[(x - 4) + (z + 18) * 20 + y * 20 * 16]
        return next(name for name, palette_index in palette.items() if palette_index == index)

    assert block(13, 1, -3) == block(14, 2, -3) == "minecraft:air"
    assert block(23, 5, -13) == "minecraft:glass"
    assert block(23, 5, -10) == "minecraft:stone_bricks"
    for step, z in enumerate((-8, -9, -10, -11)):
        assert block(17, step, z).startswith("minecraft:oak_stairs[facing=north")
    assert block(17, 3, -8) == block(18, 3, -8) == "minecraft:air"
    assert block(17, 3, -12) == "minecraft:oak_planks"
    assert block(17, 3, -10) == "minecraft:air" or block(17, 3, -10).startswith("minecraft:oak_stairs")
    assert block(10, 1, -9).startswith("minecraft:oak_stairs[facing=west")
    assert block(10, 8, -12) == "minecraft:oak_planks"
    report = json.loads((out / "export_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "succeeded_with_warnings"
    assert report["summary"] == {"preserved": 1, "approximated": 5, "omitted": 0, "unsupported": 0, "failed": 0}
    assert report["extensions"]["unresolved_asset_ids"] == ["asset_chair_oak"]


def test_sample_is_deterministic_and_fails_closed(tmp_path: Path) -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    export_sample(source, tmp_path / "first", data_version=4671)
    export_sample(source, tmp_path / "second", data_version=4671)
    assert (tmp_path / "first/library.schem").read_bytes() == (tmp_path / "second/library.schem").read_bytes()
    changed = copy.deepcopy(source)
    building = next(r for r in changed["records"] if r["id"] == "building_arcane_library")
    building["bounds"]["max"][0] = 25
    with pytest.raises(SampleExportError, match="target.sample_geometry"):
        export_sample(changed, tmp_path / "changed", data_version=4671)
    assert not (tmp_path / "changed").exists()
    with pytest.raises(SampleExportError, match="target.data_version"):
        export_sample(source, tmp_path / "bad_version", data_version=0)
    assert not (tmp_path / "bad_version").exists()
