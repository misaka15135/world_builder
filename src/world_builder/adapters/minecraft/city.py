"""Bounded Sponge v3 city export for a verified WIR 512 m city snapshot.

The source only specifies axis-aligned volumes. Every block below is explicit
adapter policy: buildings are solid or shell proxies, terrain is a flat bank
and there is no fluid simulation. Quantisation losses are reported per entity.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import io
import json
import math
import struct
from pathlib import Path

from world_builder.wir.validator import validate_package

ADAPTER_VERSION = "0.1.0-city.1"
PROFILE_ID = "profile_minecraft_city_12111"
TARGET_VERSION = "1.21.11+worldedit-7.3.19+schem-v3"
CHUNK_SIZE_M = 128
DEFAULT_DATA_VERSION = 4671

PALETTE = {
    "minecraft:air": 0,
    "minecraft:stone_bricks": 1,
    "minecraft:bricks": 2,
    "minecraft:oak_planks": 3,
    "minecraft:water": 4,
    "minecraft:grass_block": 5,
    "minecraft:smooth_stone": 6,
}


class CityExportError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def _canonical(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _utf8(value: str) -> bytes:
    raw = value.encode("utf-8")
    return struct.pack(">H", len(raw)) + raw


def _tag(tag_type: int, name: str, payload: bytes) -> bytes:
    return bytes((tag_type,)) + _utf8(name) + payload


def _compound(*tags: bytes) -> bytes:
    return b"".join(tags) + b"\x00"


def _varint(value: int) -> bytes:
    result = bytearray()
    while True:
        part = value & 0x7F
        value >>= 7
        result.append(part | (0x80 if value else 0))
        if not value:
            return bytes(result)


def _box(source_id: str, x0: float, x1: float, n0: float, n1: float, u0: float, u1: float, block: str) -> dict:
    """A WIR-metre box converted to Minecraft axes: (x, z, -y)."""
    if not (x0 < x1 and n0 < n1 and u0 < u1):
        raise CityExportError("target.box_degenerate", source_id)
    return {"source_id": source_id, "x0": x0, "x1": x1, "y0": u0, "y1": u1,
            "z0": -n1, "z1": -n0, "block": block}


def _building_shell(building: dict, entities: dict, *, with_stair: bool) -> list[dict]:
    """Hollow two-storey shell from declared source parameters.

    Every building in the source declares its envelope, storey height, wall and
    floor thickness, stair void and east entrance, so the shell is derived from
    source fields. Only the five buildings whose interior_state is `generated`
    carry a stair and furniture; the rest stay a shell with an open upper floor
    and no way up, which the report states explicitly.
    """
    g = building["geometry"]
    if g["representation"] != "parametric_building" or g["entry"]["side"] != "east":
        raise CityExportError("target.building_geometry", building["id"])
    (x0, n0, z0), (x1, n1, z1) = building["bounds"]["min"], building["bounds"]["max"]
    wall, floor, roof = g["wall_thickness_m"], g["floor_thickness_m"], g["roof_height_m"]
    upper_z = z0 + g["storey_height_m"]
    upper_top = upper_z + floor
    void = g["stair_void_local_m"]
    vx0, vn0 = x0 + void["min"][0], n0 + void["min"][1]
    vx1, vn1 = x0 + void["max"][0], n0 + void["max"][1]
    if not (x0 < vx0 < vx1 < x1 and n0 < vn0 < vn1 < n1):
        raise CityExportError("target.building_void", building["id"])
    entry = g["entry"]
    door_n0, door_n1 = n0 + entry["offset_m"], n0 + entry["offset_m"] + entry["width_m"]
    door_top = z0 + floor + entry["height_m"]
    # A door opening has to clear whole blocks: the declared height is snapped
    # up to at least two blocks and the lintel starts on that cell boundary,
    # otherwise the quantised gap collapses to a single block and is not
    # walkable. Carving with air afterwards would not work either, because
    # `//paste -a` skips air cells.
    door_clear_low = math.ceil(z0 + floor)
    door_blocks_tall = max(2, int(entry["height_m"]))
    lintel_low = max(door_top, door_clear_low + door_blocks_tall)
    if not (n0 + wall < door_n0 < door_n1 < n1 - wall and lintel_low < z1 - roof):
        raise CityExportError("target.building_entry", building["id"])
    name = building["id"]
    shell, plank = "minecraft:smooth_stone", "minecraft:oak_planks"
    parts = [
        _box(name, x0, x1, n0, n1, z0, z0 + floor, plank),
        _box(name + "_west_wall", x0, x0 + wall, n0, n1, z0 + floor, z1 - roof, shell),
        _box(name + "_south_wall", x0 + wall, x1 - wall, n0, n0 + wall, z0 + floor, z1 - roof, shell),
        _box(name + "_north_wall", x0 + wall, x1 - wall, n1 - wall, n1, z0 + floor, z1 - roof, shell),
        _box(name + "_east_wall_south", x1 - wall, x1, n0 + wall, door_n0, z0 + floor, z1 - roof, shell),
        _box(name + "_east_wall_north", x1 - wall, x1, door_n1, n1 - wall, z0 + floor, z1 - roof, shell),
        _box(name + "_east_door_lintel", x1 - wall, x1, door_n0, door_n1, lintel_low, z1 - roof, shell),
        _box(name + "_upper_floor_west", x0, vx0, n0, n1, upper_z, upper_top, plank),
        _box(name + "_upper_floor_east", vx1, x1, n0, n1, upper_z, upper_top, plank),
        _box(name + "_upper_floor_south", vx0, vx1, n0, vn0, upper_z, upper_top, plank),
        _box(name + "_upper_floor_north", vx0, vx1, vn1, n1, upper_z, upper_top, plank),
        _box(name + "_flat_roof_proxy", x0, x1, n0, n1, z1 - roof, z1, plank),
    ]
    if not with_stair:
        return parts
    children = [r for r in entities.values() if r["parent_id"] == building["id"]]
    storeys = sorted((r for r in children if r["kind"] == "storey"), key=lambda r: r["bounds"]["min"][2])
    stairs = [r for r in children if r["kind"] == "stair"]
    if len(storeys) != 2 or len(stairs) != 1:
        raise CityExportError("target.interior_plan", building["id"])
    stair = stairs[0]
    sg = stair["geometry"]
    if sg["representation"] != "straight_stair" or sg["steps"] < 1:
        raise CityExportError("target.interior_geometry", building["id"])
    (sx0, sn0, _), (sx1, sn1, _) = stair["bounds"]["min"], stair["bounds"]["max"]
    if not (vx0 <= sx0 < sx1 <= vx1 and vn0 <= sn0 < sn1 <= vn1
            and abs(sg["floor_levels_m"][0] - (z0 + floor)) < 0.01
            and abs(sg["floor_levels_m"][1] - upper_top) < 0.01):
        raise CityExportError("target.interior_void", building["id"])
    step_run, step_rise = sg["run_m"] / sg["steps"], sg["rise_m"] / sg["steps"]
    clear_x0 = sx0 + (sx1 - sx0 - sg["clear_width_m"]) / 2
    for index in range(sg["steps"]):
        parts.append(_box(f"{stair['id']}_tread_{index + 1:02}", clear_x0, clear_x0 + sg["clear_width_m"],
                          sn0 + index * step_run, sn0 + (index + 1) * step_run,
                          z0 + floor, z0 + floor + (index + 1) * step_rise, plank))
    parts.append(_box(stair["id"] + "_landing", clear_x0, clear_x0 + sg["clear_width_m"],
                      sn0 + sg["run_m"], sn1, upper_z, upper_top, plank))
    return parts


def city_boxes(package: dict, *, include_interiors: bool) -> list[dict]:
    validate_package(package)
    specs = [r for r in package["records"] if r["record_type"] == "world_spec"]
    if len(specs) != 1 or "city_spec" not in specs[0].get("extensions", {}):
        raise CityExportError("target.city_scope", "a WIR city_spec snapshot is required")
    coordinate = package["manifest"]["coordinate_system"]
    if coordinate["x_axis"] != "east" or coordinate["y_axis"] != "north":
        raise CityExportError("target.city_axes", "unsupported source axes")
    entities = sorted((r for r in package["records"] if r["record_type"] == "entity"), key=lambda r: r["id"])
    by_id = {r["id"]: r for r in entities}
    kinds = {r["kind"] for r in entities}
    if not {"terrain", "river", "road", "bridge", "building"} <= kinds:
        raise CityExportError("target.city_layers", "city is missing required spatial layers")
    boxes: list[dict] = []
    for record in entities:
        if record["kind"] not in {"road", "bridge", "building"}:
            continue
        if record["geometry"]["representation"] not in {"box", "parametric_building"}:
            raise CityExportError("target.city_geometry", record["id"])
        if record["kind"] == "building":
            with_stair = include_interiors and record["attributes"]["interior_state"] == "generated"
            boxes.extend(_building_shell(record, by_id, with_stair=with_stair))
            continue
        low, high = record["bounds"]["min"], record["bounds"]["max"]
        block = {"road": "minecraft:stone_bricks", "bridge": "minecraft:oak_planks"}[record["kind"]]
        boxes.append(_box(record["id"], low[0], high[0], low[1], high[1], low[2], high[2], block))
    terrain = next(r for r in entities if r["kind"] == "terrain")
    river = next(r for r in entities if r["kind"] == "river")
    tlo, thi = terrain["bounds"]["min"], terrain["bounds"]["max"]
    rlo, rhi = river["bounds"]["min"], river["bounds"]["max"]
    if not (tlo[0] < rlo[0] < rhi[0] < thi[0] and tlo[1] == rlo[1] and thi[1] == rhi[1]):
        raise CityExportError("target.city_river", "flat bank policy requires a straight north-south river")
    boxes.append(_box("terrain_west_proxy", tlo[0], rlo[0], tlo[1], thi[1], -0.2, 0.25, "minecraft:grass_block"))
    boxes.append(_box("terrain_east_proxy", rhi[0], thi[0], tlo[1], thi[1], -0.2, 0.25, "minecraft:grass_block"))
    boxes.append(_box("river_water_proxy", rlo[0], rhi[0], rlo[1], rhi[1], -0.05, 0.05, "minecraft:water"))
    return boxes


def _cell_range(lo: float, hi: float) -> range:
    first = math.floor(lo)
    last = math.ceil(hi) - 1
    return range(first, last + 1)


def voxelize(boxes: list[dict], y0: int, y1: int) -> dict[tuple[int, int], bytearray]:
    """Fill every cell overlapping a box; later boxes win over earlier ones."""
    chunks: dict[tuple[int, int], bytearray] = {}
    for box in boxes:
        block = PALETTE[box["block"]]
        height = y1 - y0
        for x in _cell_range(box["x0"], box["x1"]):
            cx = x // CHUNK_SIZE_M
            for z in _cell_range(box["z0"], box["z1"]):
                cz = z // CHUNK_SIZE_M
                grid = chunks.get((cx, cz))
                if grid is None:
                    grid = bytearray(CHUNK_SIZE_M * CHUNK_SIZE_M * height)
                    chunks[(cx, cz)] = grid
                local_z = z - cz * CHUNK_SIZE_M
                local_x = x - cx * CHUNK_SIZE_M
                base = local_x + local_z * CHUNK_SIZE_M
                for y in _cell_range(box["y0"], box["y1"]):
                    if y0 <= y < y1:
                        grid[base + (y - y0) * CHUNK_SIZE_M * CHUNK_SIZE_M] = block
    return chunks


def schematic_bytes(grid: bytearray, data_version: int) -> bytes:
    if type(data_version) is not int or not 1 <= data_version <= 2**31 - 1:
        raise CityExportError("target.data_version", "positive Java DataVersion is required")
    palette = _compound(*(_tag(3, block, struct.pack(">i", index)) for block, index in PALETTE.items()))
    packed = b"".join(_varint(index) for index in grid)
    blocks = _compound(_tag(10, "Palette", palette),
                       _tag(7, "Data", struct.pack(">i", len(packed)) + packed),
                       _tag(9, "BlockEntities", b"\x0a" + struct.pack(">i", 0)))
    schematic = _compound(
        _tag(3, "Version", struct.pack(">i", 3)),
        _tag(3, "DataVersion", struct.pack(">i", data_version)),
        _tag(2, "Width", struct.pack(">h", CHUNK_SIZE_M)),
        _tag(2, "Height", struct.pack(">h", 36)),
        _tag(2, "Length", struct.pack(">h", CHUNK_SIZE_M)),
        _tag(11, "Offset", struct.pack(">i", 3) + struct.pack(">iii", 0, 0, 0)),
        _tag(10, "Metadata", _compound(_tag(8, "Name", _utf8("WIR 512 m city chunk")),
                                      _tag(8, "Author", _utf8("world_builder")))),
        _tag(10, "Blocks", blocks),
    )
    root = _tag(10, "", _compound(_tag(10, "Schematic", schematic)))
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0, compresslevel=9) as target:
        target.write(root)
    return buffer.getvalue()


def export_city(package: dict, output_dir: str | Path, *, include_interiors: bool = False,
                data_version: int = DEFAULT_DATA_VERSION) -> dict:
    boxes = city_boxes(package, include_interiors=include_interiors)
    y0, y1 = -4, 32
    chunks = voxelize(boxes, y0, y1)
    entities = sorted((r for r in package["records"] if r["record_type"] == "entity"), key=lambda r: r["id"])
    source_hash = "sha256:" + hashlib.sha256(json.dumps(package, ensure_ascii=False, sort_keys=True,
                                                         separators=(",", ":")).encode()).hexdigest()
    represented = {box["source_id"] for box in boxes}
    items = []
    for record in entities:
        kind = record["kind"]
        if kind == "world":
            classification, target, message = "preserved", "world_id:" + record["id"], "source identity retained in manifest"
        elif kind in {"road", "bridge"}:
            classification, target, message = "approximated", "blocks:" + record["id"], "axis-aligned volume quantised to whole blocks at 1 m = 1 block"
        elif kind == "building":
            if include_interiors and record["attributes"]["interior_state"] == "generated":
                classification, target, message = "approximated", "blocks:" + record["id"] + "_*", "hollow shell, east opening, floors and stair from declared source parameters; stair treads fall below block resolution and merge into whole-block steps"
            else:
                classification, target, message = "approximated", "blocks:" + record["id"] + "_*", "hollow shell with the declared east opening and upper-floor void; source interior_state is deferred, so no stair, rooms or furniture exist to place"
        elif kind == "terrain":
            classification, target, message = "approximated", "blocks:terrain_*_proxy", "flat grass banks replace the sampled heightfield"
        elif kind == "river":
            classification, target, message = "approximated", "blocks:river_water_proxy", "static water volume; no fluid simulation"
        elif include_interiors and record["id"] in represented:
            classification, target, message = "approximated", "blocks:" + record["id"] + "_*", "source furniture or stair volume quantised to whole blocks"
        else:
            classification, target, message = "omitted", None, "source entity retained in the WIR package but not placed as blocks"
        items.append({"source_id": record["id"], "target_id": target,
                      "classification": classification, "message": message})
    summary = {key: sum(item["classification"] == key for item in items)
               for key in ("preserved", "approximated", "omitted", "unsupported", "failed")}
    report = {"record_type": "export_report", "id": "report_minecraft_city",
              "revision_id": package["manifest"]["revision_id"], "target_profile_id": PROFILE_ID,
              "status": "succeeded_with_warnings", "coordinate_transform_row_major":
              [1, 0, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1],
              "items": items, "summary": summary,
              "extensions": {"adapter_version": ADAPTER_VERSION, "target_load": "not_run",
                             "collision": "not_run", "walkthrough": "not_run"}}
    profile = {"record_type": "target_profile", "id": PROFILE_ID, "target": "minecraft_java",
               "target_version": TARGET_VERSION, "adapter_version": ADAPTER_VERSION,
               "configuration": {"meters_per_block": 1, "x_axis": "east", "y_axis": "up",
                                 "z_axis": "south", "format": "sponge-schematic-v3",
                                 "chunk_size_m": CHUNK_SIZE_M,
                                 "region_y_m": [y0, y1], "data_version": data_version},
               "declared_capabilities": ["blocks", "chunked_region_clipboard"], "extensions": {}}
    derived = copy.deepcopy(package)
    derived["records"].extend([profile, report])
    next(r for r in derived["records"] if r["record_type"] == "world_spec")["target_profile_ids"].append(PROFILE_ID)
    validate_package(derived)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    (output / "schematics").mkdir()
    index = []
    for (cx, cz), grid in sorted(chunks.items()):
        data = schematic_bytes(grid, data_version)
        name = f"city_c{cx:02d}_{abs(cz):02d}"
        path = f"schematics/{name}.schem"
        (output / path).write_bytes(data)
        solid = sum(1 for value in grid if value)
        index.append({"id": f"c{cx:02d}_{abs(cz):02d}", "path": path,
                      "chunk_x": cx, "chunk_z": cz,
                      "world_min": [cx * CHUNK_SIZE_M, y0, cz * CHUNK_SIZE_M],
                      "non_air_blocks": solid,
                      "schem_sha256": "sha256:" + hashlib.sha256(data).hexdigest()})
    manifest = {"format": "minecraft-schem-city-0.1", "source_world_id": package["manifest"]["world_id"],
                "source_revision_id": package["manifest"]["revision_id"], "source_snapshot_hash": source_hash,
                "adapter_version": ADAPTER_VERSION, "target_profile_id": PROFILE_ID,
                "target_version": TARGET_VERSION, "data_version": data_version,
                "meters_per_block": 1, "chunk_size_m": CHUNK_SIZE_M, "region_y_m": [y0, y1],
                "palette": PALETTE, "chunks": index, "boxes": boxes,
                "source_to_minecraft_row_major": report["coordinate_transform_row_major"],
                "target_load": "not_run", "walkthrough": "not_run"}
    (output / "manifest.json").write_bytes(_canonical(manifest))
    (output / "export_report.json").write_bytes(_canonical(report))
    (output / "target_profile.json").write_bytes(_canonical(profile))
    return {"output": str(output), "source_revision_id": package["manifest"]["revision_id"],
            "box_count": len(boxes), "chunk_count": len(chunks),
            "non_air_blocks": sum(item["non_air_blocks"] for item in index),
            "report_summary": summary}
