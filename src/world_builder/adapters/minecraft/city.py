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

ADAPTER_VERSION = "0.1.0-city.2"
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
    "minecraft:oak_slab": 7,
    "minecraft:bookshelf": 8,
    "minecraft:barrel": 9,
    "minecraft:crafting_table": 10,
    "minecraft:anvil": 11,
    "minecraft:furnace": 12,
    "minecraft:chest": 13,
    "minecraft:red_bed": 14,
    "minecraft:oak_fence": 15,
    "minecraft:chiseled_quartz_block": 16,
    "minecraft:light_gray_concrete": 17,
    "minecraft:glass": 18,
    "minecraft:gray_concrete": 19,
}


def _shell_materials(style: str) -> tuple[str, str]:
    """Wall and slab blocks for a style; the modern profile rereads as a CBD."""
    if style == "modern_grid":
        return "minecraft:light_gray_concrete", "minecraft:smooth_stone"
    return "minecraft:smooth_stone", "minecraft:oak_planks"


def _street_block(style: str) -> str:
    """Modern streets read as asphalt; the arcane profile keeps stone setts."""
    return "minecraft:gray_concrete" if style == "modern_grid" else "minecraft:stone_bricks"


def _window_bands(building: dict, x0: float, x1: float, n0: float, n1: float,
                  z0: float, wall: float, roof: float, storeys: int, storey_h: float) -> list[dict]:
    """A one-metre glass band at the top of each upper storey.

    Drawn as extra boxes over the shell rather than by splitting the wall, so
    the wall geometry stays as it was. The ground storey's east side is left
    alone because that is where the entrance is.
    """
    parts: list[dict] = []
    name = building["id"]
    for level in range(storeys):
        top = z0 + (level + 1) * storey_h
        low, high = top - 1.0, top
        if low <= z0 + 0.2 or high > building["bounds"]["max"][2] - roof:
            continue
        parts.append(_box(f"{name}_glass_{level}_west", x0, x0 + wall, n0, n1, low, high, "minecraft:glass"))
        parts.append(_box(f"{name}_glass_{level}_south", x0 + wall, x1 - wall, n0, n0 + wall, low, high, "minecraft:glass"))
        parts.append(_box(f"{name}_glass_{level}_north", x0 + wall, x1 - wall, n1 - wall, n1, low, high, "minecraft:glass"))
        if level > 0:
            parts.append(_box(f"{name}_glass_{level}_east", x1 - wall, x1, n0 + wall, n1 - wall, low, high, "minecraft:glass"))
    return parts

# Furniture is still a box proxy, but the block picks up the room's function so
# a bedroom, a workshop and a chapel do not read the same from inside.
FURNITURE_BLOCKS = {
    "hearth": "minecraft:furnace", "bench": "minecraft:oak_slab", "bed": "minecraft:red_bed",
    "counter": "minecraft:oak_fence", "display_rack": "minecraft:barrel", "crate_stack": "minecraft:barrel",
    "workbench": "minecraft:crafting_table", "anvil": "minecraft:anvil", "tool_rack": "minecraft:oak_fence",
    "reading_table": "minecraft:oak_slab", "chair": "minecraft:oak_slab", "shelf": "minecraft:bookshelf",
    "long_table": "minecraft:oak_planks", "chest": "minecraft:chest",
    "altar": "minecraft:chiseled_quartz_block", "pew": "minecraft:oak_slab", "cabinet": "minecraft:barrel",
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


def _roof_boxes(name: str, x0: float, x1: float, n0: float, n1: float, z1: float,
                roof_h: float, style: str, block: str) -> list[dict]:
    """Stepped roof geometry driven by the declared style and roof height.

    A flat or very thin roof stays a single slab. A gable narrows along the
    north axis only, a spire narrows on both horizontal axes, so the three
    silhouettes read differently from the street. Steps are one block high on
    purpose: thinner slices would quantise into the same cell and disappear.
    """
    if style not in {"gable", "spire"} or roof_h < 1.0:
        return [_box(name + "_flat_roof_proxy", x0, x1, n0, n1, z1 - roof_h, z1, block)]
    steps = max(2, min(4, int(round(roof_h))))
    parts: list[dict] = []
    for index in range(steps):
        low = z1 - roof_h + roof_h * index / steps
        high = z1 - roof_h + roof_h * (index + 1) / steps
        inset_n = (n1 - n0) * index / (2 * steps)
        inset_x = (x1 - x0) * index / (2 * steps) if style == "spire" else 0.0
        parts.append(_box(f"{name}_roof_{index:02}", x0 + inset_x, x1 - inset_x,
                          n0 + inset_n, n1 - inset_n, low, high, block))
    return parts


def _partition_boxes(building: dict, entities: dict, storeys: list[dict]) -> list[dict]:
    """Walls the source declares, each with the opening it declares.

    The wall itself is already one block thick in the source; the opening is
    snapped to whole blocks above the floor slab for the same reason as the
    building's east entrance, otherwise a 2 m doorway can quantise shut.
    """
    block = "minecraft:smooth_stone"
    parts: list[dict] = []
    for storey in storeys:
        walls = sorted((r for r in entities.values()
                        if r["kind"] == "partition" and r["parent_id"] == storey["id"]), key=lambda r: r["id"])
        for wall in walls:
            opening = (wall.get("attributes") or {}).get("opening")
            if not isinstance(opening, dict) or opening.get("side") != "west":
                raise CityExportError("target.partition_opening", wall["id"])
            (x0, n0, z0), (x1, n1, z1) = wall["bounds"]["min"], wall["bounds"]["max"]
            door_w = float(opening["width_m"])
            opening_low = math.ceil(z0)
            opening_high = opening_low + max(2, int(opening["height_m"]))
            if not (x0 + door_w < x1 and z1 > opening_low):
                raise CityExportError("target.partition_geometry", wall["id"])
            parts.append(_box(wall["id"], x0 + door_w, x1, n0, n1, z0, z1, block))
            if z1 > opening_high:
                parts.append(_box(wall["id"] + "_head", x0, x0 + door_w, n0, n1, opening_high, z1, block))
    return parts


def _building_shell(building: dict, entities: dict, *, with_interior: bool,
                    style: str = "arcane_medieval") -> list[dict]:
    """Hollow multi-storey shell from declared source parameters.

    Envelope, storey count, storey height, wall and floor thickness, stair void
    and east entrance all come from source fields, so the shell stays derived
    from the source rather than invented. Only buildings whose interior_state is
    `generated` carry partitions, a stair and furniture; the rest stay a shell
    with an open upper floor and no way up, which the report states explicitly.
    A stair only reaches the first upper slab, so storeys above the second are
    enclosed and unreachable — a source limitation, not an adapter choice.
    """
    g = building["geometry"]
    if g["representation"] != "parametric_building" or g["entry"]["side"] != "east":
        raise CityExportError("target.building_geometry", building["id"])
    (x0, n0, z0), (x1, n1, z1) = building["bounds"]["min"], building["bounds"]["max"]
    wall, floor, roof = g["wall_thickness_m"], g["floor_thickness_m"], g["roof_height_m"]
    storey_count = building["attributes"]["storeys"]
    if type(storey_count) is not int or storey_count < 1:
        raise CityExportError("target.building_storeys", building["id"])
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
    # A single-storey building has no room above its door: the opening reaches
    # the ceiling and there is simply no lintel to place.
    if not (n0 + wall < door_n0 < door_n1 < n1 - wall and lintel_low <= z1 - roof):
        raise CityExportError("target.building_entry", building["id"])
    name = building["id"]
    shell, plank = _shell_materials(style)
    parts = [_box(name, x0, x1, n0, n1, z0, z0 + floor, plank)]
    for level in range(1, storey_count):
        top = z0 + level * g["storey_height_m"]
        if top + floor > z1 - roof:
            raise CityExportError("target.building_slab", building["id"])
        if level == 1:
            parts.extend([
                _box(f"{name}_floor{level}_west", x0, vx0, n0, n1, top, top + floor, plank),
                _box(f"{name}_floor{level}_east", vx1, x1, n0, n1, top, top + floor, plank),
                _box(f"{name}_floor{level}_south", vx0, vx1, n0, vn0, top, top + floor, plank),
                _box(f"{name}_floor{level}_north", vx0, vx1, vn1, n1, top, top + floor, plank),
            ])
        else:
            parts.append(_box(f"{name}_floor{level}", x0, x1, n0, n1, top, top + floor, plank))
    parts.extend([
        _box(name + "_west_wall", x0, x0 + wall, n0, n1, z0 + floor, z1 - roof, shell),
        _box(name + "_south_wall", x0 + wall, x1 - wall, n0, n0 + wall, z0 + floor, z1 - roof, shell),
        _box(name + "_north_wall", x0 + wall, x1 - wall, n1 - wall, n1, z0 + floor, z1 - roof, shell),
        _box(name + "_east_wall_south", x1 - wall, x1, n0 + wall, door_n0, z0 + floor, z1 - roof, shell),
        _box(name + "_east_wall_north", x1 - wall, x1, door_n1, n1 - wall, z0 + floor, z1 - roof, shell),
    ])
    if lintel_low < z1 - roof:
        parts.append(_box(name + "_east_door_lintel", x1 - wall, x1, door_n0, door_n1, lintel_low, z1 - roof, shell))
    parts.extend(_roof_boxes(name, x0, x1, n0, n1, z1, roof, g.get("roof_style", "flat"), plank))
    if style == "modern_grid":
        parts.extend(_window_bands(building, x0, x1, n0, n1, z0, wall, roof, storey_count, storey_h))
    if not with_interior:
        return parts
    children = [r for r in entities.values() if r["parent_id"] == building["id"]]
    storeys = sorted((r for r in children if r["kind"] == "storey"), key=lambda r: r["bounds"]["min"][2])
    if len(storeys) != storey_count:
        raise CityExportError("target.interior_plan", building["id"])
    parts.extend(_partition_boxes(building, entities, storeys))
    room_ids = {r["id"] for r in entities.values() if r["kind"] == "room" and r["parent_id"] in {s["id"] for s in storeys}}
    for item in sorted((r for r in entities.values()
                        if r["kind"] == "furniture" and r["parent_id"] in room_ids), key=lambda r: r["id"]):
        block = FURNITURE_BLOCKS.get(item["attributes"].get("use"))
        if block is None:
            raise CityExportError("target.furniture_use", item["id"])
        low, high = item["bounds"]["min"], item["bounds"]["max"]
        parts.append(_box(item["id"], low[0], high[0], low[1], high[1], low[2], high[2], block))
    stairs = [r for r in children if r["kind"] == "stair"]
    if storey_count < 2:
        if stairs:
            raise CityExportError("target.interior_plan", building["id"])
        return parts
    if len(stairs) != 1:
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
    style = (specs[0].get("extensions") or {}).get("city_spec", {}).get("style_profile", "arcane_medieval")
    boxes: list[dict] = []
    for record in entities:
        if record["kind"] not in {"road", "bridge", "building", "wall"}:
            continue
        if record["geometry"]["representation"] not in {"box", "parametric_building"}:
            raise CityExportError("target.city_geometry", record["id"])
        if record["kind"] == "building":
            with_interior = include_interiors and record["attributes"]["interior_state"] == "generated"
            boxes.extend(_building_shell(record, by_id, with_interior=with_interior, style=style))
            continue
        low, high = record["bounds"]["min"], record["bounds"]["max"]
        block = {"road": _street_block(style), "bridge": "minecraft:oak_planks",
                 "wall": "minecraft:stone_bricks"}[record["kind"]]
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


def schematic_bytes(grid: bytearray, data_version: int, height: int) -> bytes:
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
        _tag(2, "Height", struct.pack(">h", height)),
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
    # The region starts just below the city's own ground so the paste base lands
    # on a solid block. Starting at the overworld floor would put the player
    # inside bedrock, which pushes them out of the world instead of anchoring
    # the clipboard there.
    y0, y1 = -1, 32
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
        elif kind in {"road", "bridge", "wall"}:
            classification, target, message = "approximated", "blocks:" + record["id"], "axis-aligned volume quantised to whole blocks at 1 m = 1 block"
        elif kind == "building":
            if include_interiors and record["attributes"]["interior_state"] == "generated":
                classification, target, message = "approximated", "blocks:" + record["id"] + "_*", "hollow shell over " + str(record["attributes"]["storeys"]) + " storey(s) with the declared east opening, room partitions, floors and stair; treads below block resolution merge into whole-block steps and storeys above the second have no stair"
            else:
                classification, target, message = "approximated", "blocks:" + record["id"] + "_*", "hollow shell with the declared east opening and upper-floor void; source interior_state is deferred, so no stair, rooms or furniture exist to place"
        elif kind == "terrain":
            classification, target, message = "approximated", "blocks:terrain_*_proxy", "flat grass banks replace the sampled heightfield"
        elif kind == "river":
            classification, target, message = "approximated", "blocks:river_water_proxy", "static water volume; no fluid simulation"
        elif include_interiors and record["id"] in represented:
            classification, target, message = "approximated", "blocks:" + record["id"] + "_*", "source furniture, partition or stair volume quantised to whole blocks"
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
        data = schematic_bytes(grid, data_version, y1 - y0)
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
