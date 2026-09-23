"""Fail-closed Sponge v3 export for the WIR 0.1 hand-authored library sample.

This is a deliberately narrow target experiment, not a general building mesher.
The WIR sample describes volumes and a stair relation but no wall, door or tread
geometry. The shell below is an explicit adapter policy and is reported as loss.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import io
import json
import os
import struct
import tempfile
from pathlib import Path

from world_builder.wir.validator import validate_package

ADAPTER_VERSION = "0.1.0-sample.1"
SOURCE_HASH = "sha256:07afdf589fc3ddb045d27af0dadabafa58f8b6cea010405bec24b2db62e4f8bb"
WIDTH, HEIGHT, LENGTH = 20, 9, 16
ORIGIN = (4, 0, -18)
PALETTE = {
    "minecraft:air": 0,
    "minecraft:stone_bricks": 1,
    "minecraft:oak_planks": 2,
    "minecraft:glass": 3,
    "minecraft:oak_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]": 4,
    "minecraft:oak_stairs[facing=west,half=bottom,shape=straight,waterlogged=false]": 5,
}
ROUTE = [(13, 1, -3), (13, 1, -4), (17, 1, -4), (17, 1, -8),
         (17, 2, -9), (17, 3, -10), (17, 4, -11), (17, 4, -12),
         (15, 4, -12), (10, 4, -12)]


class SampleExportError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def _source_records(package: dict) -> dict:
    validate_package(package)
    if package["manifest"]["world_id"] != "world_two_storey" or package["manifest"]["revision_id"] != "revision_two_storey_001":
        raise SampleExportError("target.sample_scope", "only the frozen hand-authored two-storey revision is supported")
    records = {r["id"]: r for r in package["records"]}
    expected = {
        "building_arcane_library": ([4, 3, 0], [24, 19, 9], "building"),
        "room_reading_lower": ([6, 5, 0], [16, 16, 4], "room"),
        "room_archive_upper": ([6, 5, 4], [16, 16, 8], "room"),
        "stair_library_main": ([16, 8, 0], [20, 12, 8], "stair"),
        "chair_reading_001": ([9.7, 8.7, 0], [10.3, 9.3, 1.1], "furniture"),
    }
    for record_id, (minimum, maximum, kind) in expected.items():
        record = records.get(record_id)
        if record is None or record.get("kind") != kind or record.get("bounds") != {"min": minimum, "max": maximum}:
            raise SampleExportError("target.sample_geometry", f"unsupported geometry for {record_id}")
    if records["building_arcane_library"]["transform"]["rotation_xyzw"] != [0, 0, 0, 1]:
        raise SampleExportError("target.sample_rotation", "building rotation requires a new mapping")
    if records["profile_minecraft_12111"]["target_version"] != "1.21.11+worldedit-7.3.19+schem-v3":
        raise SampleExportError("target.profile_mismatch", "source target profile changed")
    if "sha256:" + hashlib.sha256(json.dumps(package, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest() != SOURCE_HASH:
        raise SampleExportError("target.sample_changed", "the hand sample changed; review and version its mapping")
    return records


def _block_grid() -> list[int]:
    grid = [PALETTE["minecraft:air"]] * (WIDTH * HEIGHT * LENGTH)

    def put(x: int, y: int, z: int, block: str) -> None:
        ix, iz = x - ORIGIN[0], z - ORIGIN[2]
        if not 0 <= ix < WIDTH or not 0 <= y < HEIGHT or not 0 <= iz < LENGTH:
            raise SampleExportError("target.sample_bounds", f"block outside sample: {(x, y, z)}")
        grid[ix + iz * WIDTH + y * WIDTH * LENGTH] = PALETTE[block]

    stone = "minecraft:stone_bricks"
    oak = "minecraft:oak_planks"
    for x in range(4, 24):
        for z in range(-18, -2):
            put(x, 0, z, stone)
            put(x, 3, z, oak)
            put(x, 8, z, oak)
            if x in (4, 23) or z in (-18, -3):
                for y in range(1, 8):
                    put(x, y, z, stone)
    for x in (13, 14):
        for y in (1, 2):
            put(x, y, -3, "minecraft:air")
    for z in (-13, -12):
        for y in (5, 6):
            put(23, y, z, "minecraft:glass")
    for x in (17, 18):
        for z in (-9, -10, -11):
            put(x, 3, z, "minecraft:air")
        for index, z in enumerate((-8, -9, -10, -11)):
            put(x, index, z, "minecraft:oak_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]")
    put(10, 1, -9, "minecraft:oak_stairs[facing=west,half=bottom,shape=straight,waterlogged=false]")
    _check_route(grid)
    return grid


def _at(grid: list[int], x: int, y: int, z: int) -> int:
    ix, iz = x - ORIGIN[0], z - ORIGIN[2]
    if not 0 <= ix < WIDTH or not 0 <= y < HEIGHT or not 0 <= iz < LENGTH:
        return -1
    return grid[ix + iz * WIDTH + y * WIDTH * LENGTH]


def _check_route(grid: list[int]) -> None:
    points = [ROUTE[0]]
    for (ax, ay, az), (bx, by, bz) in zip(ROUTE, ROUTE[1:]):
        horizontal = abs(ax - bx) + abs(az - bz)
        if (ax != bx and az != bz) or (ay != by and horizontal != 1) or abs(ay - by) > 1 or horizontal == 0:
            raise SampleExportError("target.route_gap", f"unsupported route segment: {(ax, ay, az)} -> {(bx, by, bz)}")
        for step in range(1, horizontal + 1):
            points.append((ax + (bx - ax) * step // horizontal, by, az + (bz - az) * step // horizontal))
    for x, feet, z in points:
        if _at(grid, x, feet - 1, z) == 0 or _at(grid, x, feet, z) != 0 or _at(grid, x, feet + 1, z) != 0:
            raise SampleExportError("target.route_blocked", f"two-block clearance failed at {(x, feet, z)}")


def _utf8(value: str) -> bytes:
    raw = value.encode("utf-8")
    if len(raw) > 65535:
        raise SampleExportError("target.nbt_string", "NBT string exceeds unsigned short length")
    return struct.pack(">H", len(raw)) + raw


def _tag(tag_type: int, name: str, payload: bytes) -> bytes:
    return bytes((tag_type,)) + _utf8(name) + payload


def _compound(*tags: bytes) -> bytes:
    return b"".join(tags) + b"\x00"


def _varint(value: int) -> bytes:
    result = bytearray()
    while True:
        part = value & 0x7f
        value >>= 7
        result.append(part | (0x80 if value else 0))
        if not value:
            return bytes(result)


def _schematic_bytes(grid: list[int], data_version: int) -> bytes:
    if type(data_version) is not int or not 1 <= data_version <= 2**31 - 1:
        raise SampleExportError("target.data_version", "positive Java DataVersion is required")
    palette = _compound(*(_tag(3, block, struct.pack(">i", index)) for block, index in PALETTE.items()))
    packed = b"".join(_varint(index) for index in grid)
    blocks = _compound(_tag(10, "Palette", palette),
                       _tag(7, "Data", struct.pack(">i", len(packed)) + packed),
                       _tag(9, "BlockEntities", b"\x0a" + struct.pack(">i", 0)))
    schematic = _compound(
        _tag(3, "Version", struct.pack(">i", 3)),
        _tag(3, "DataVersion", struct.pack(">i", data_version)),
        _tag(2, "Width", struct.pack(">h", WIDTH)),
        _tag(2, "Height", struct.pack(">h", HEIGHT)),
        _tag(2, "Length", struct.pack(">h", LENGTH)),
        _tag(11, "Offset", struct.pack(">i", 3) + struct.pack(">iii", 0, 0, 0)),
        _tag(10, "Metadata", _compound(_tag(8, "Name", _utf8("WIR two-storey library sample")),
                                      _tag(8, "Author", _utf8("world_builder")))),
        _tag(10, "Blocks", blocks),
    )
    root = _tag(10, "", _compound(_tag(10, "Schematic", schematic)))
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0, compresslevel=9) as target:
        target.write(root)
    return buffer.getvalue()


def _report(package: dict, data_version: int) -> dict:
    original = next(r for r in package["records"] if r["id"] == "report_minecraft_library")
    report = copy.deepcopy(original)
    report["status"] = "succeeded_with_warnings"
    report["items"] = [
        {"source_id": "world_two_storey", "target_id": "manifest:world_two_storey", "classification": "preserved", "message": "world identity retained in sidecar"},
        {"source_id": "building_arcane_library", "target_id": "blocks:building_shell", "classification": "approximated", "message": "walls, doorway, floor and roof are adapter policy; source has only a volume"},
        {"source_id": "room_reading_lower", "target_id": "blocks:lower_space", "classification": "approximated", "message": "open space represented by air; room identity remains in sidecar"},
        {"source_id": "room_archive_upper", "target_id": "blocks:upper_space", "classification": "approximated", "message": "upper floor at block y=3 approximates source elevation 4 m"},
        {"source_id": "stair_library_main", "target_id": "blocks:stair_main", "classification": "approximated", "message": "1.4 m clear width becomes two blocks; four north-facing treads and floor opening are adapter policy"},
        {"source_id": "chair_reading_001", "target_id": "blocks:chair_001", "classification": "approximated", "message": "linked chair asset is unavailable and replaced by one west-facing oak stair"},
    ]
    report["summary"] = {key: sum(item["classification"] == key for item in report["items"])
                         for key in ("preserved", "approximated", "omitted", "unsupported", "failed")}
    report["extensions"] = {"adapter_version": ADAPTER_VERSION, "data_version": data_version,
                            "target_load": "not_run", "passability": "offline_block_clearance_only",
                            "unresolved_asset_ids": ["asset_chair_oak"]}
    check = copy.deepcopy(package)
    check["records"] = [report if r["id"] == report["id"] else r for r in check["records"]]
    validate_package(check)
    return report


def _canonical(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def export_sample(package: dict, output_dir: str | Path, *, data_version: int) -> dict:
    """Export only the frozen sample; preserve source and refuse an existing destination."""
    _source_records(package)
    grid = _block_grid()
    payload = _schematic_bytes(grid, data_version)
    report = _report(package, data_version)
    manifest = {
        "format": "sponge-schematic-v3-sample",
        "adapter_version": ADAPTER_VERSION,
        "source_world_id": package["manifest"]["world_id"],
        "source_revision_id": package["manifest"]["revision_id"],
        "source_snapshot_hash": SOURCE_HASH,
        "target_profile_id": "profile_minecraft_12111",
        "minecraft_version": "1.21.11",
        "worldedit_version": "7.3.19",
        "data_version": data_version,
        "data_version_verified_on_target": False,
        "meters_per_block": 1,
        "source_to_target_row_major": report["coordinate_transform_row_major"],
        "target_origin_world_blocks": list(ORIGIN),
        "dimensions_blocks": [WIDTH, HEIGHT, LENGTH],
        "placement": "paste clipboard origin at target world block [4,0,-18]",
        "schematic_sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
        "block_count": sum(index != 0 for index in grid),
        "route_world_blocks": [list(point) for point in ROUTE],
        "offline_checks": {"two_block_headroom": "pass", "stair_steps": "pass", "game_load": "not_run", "in_game_walk": "not_run"},
        "source_limitations": ["source lacks explicit wall, door and stair tread geometry", "linked chair GLB is unavailable"],
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    files = {"library.schem": payload, "manifest.json": _canonical(manifest), "export_report.json": _canonical(report)}
    for name, content in files.items():
        fd, temporary = tempfile.mkstemp(prefix=".sample-", dir=output)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, output / name)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return manifest
