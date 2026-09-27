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

ADAPTER_VERSION = "0.1.0-city.6"
PROFILE_ID = "profile_minecraft_city_12111"
TARGET_VERSION = "1.21.11+worldedit-7.3.19+schem-v3"
CHUNK_SIZE_M = 128
# A polyline corridor is rasterised into axis-aligned boxes so that a diagonal
# street stays a street. A run that already lies on an axis stays one box; a run
# that cuts across the grid becomes a chain of squares one corridor wide, spaced
# this fraction of a width apart so consecutive squares overlap. Measured on the
# 512 m arcane city that chain covers ~1.4 x the corridor area, where the old
# bounding box covered 2.4 x the whole scene for a single 187 x 368 m street.
CORRIDOR_SPACING = 0.7
# A roof that stops flush with the wall reads as a lid; building guides get
# their depth from an eave, so the roof oversails the walls by half a metre.
ROOF_EAVE_M = 0.6
# Source bounds are rounded to six decimals: derived sums can differ from a
# declared value by a rounding step, and that is not a plan violation.
COORD_EPS_M = 1e-6
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
    "minecraft:dark_oak_planks": 20,
}


def _shell_materials(style: str) -> tuple[str, str]:
    """Wall and slab blocks for a style, one profile per background.

    A works estate is brick with concrete slabs, a harbour is pale stone with
    smooth-stone aprons, the CBD is concrete and glass, and the arcane town is
    stone with timber floors. Four backgrounds, four vocabularies.
    """
    if style == "industrial_works":
        return "minecraft:bricks", "minecraft:gray_concrete"
    if style == "harbour_works":
        return "minecraft:chiseled_quartz_block", "minecraft:smooth_stone"
    if style == "modern_grid":
        return "minecraft:light_gray_concrete", "minecraft:smooth_stone"
    return "minecraft:smooth_stone", "minecraft:oak_planks"


def _street_block(style: str) -> str:
    """Asphalt in the CBD, brick-toned setts for works, quay stone at the port."""
    if style == "industrial_works":
        return "minecraft:gray_concrete"
    if style == "harbour_works":
        return "minecraft:stone_bricks"
    return "minecraft:gray_concrete" if style == "modern_grid" else "minecraft:stone_bricks"


def _facade_blocks(style: str) -> tuple[str, str]:
    """Plinth and corner-post blocks: relief that contrasts by value, not hue.

    Building-skill rule 3 asks every facade for at least two devices that catch
    the light. The storey band already exists; the plinth and the corner posts
    are the other two, and both are the same boxes the adapter already knows how
    to place, so no source data changes.
    """
    if style == "modern_grid":
        return "minecraft:gray_concrete", "minecraft:light_gray_concrete"
    if style == "industrial_works":
        return "minecraft:stone_bricks", "minecraft:light_gray_concrete"
    if style == "harbour_works":
        return "minecraft:gray_concrete", "minecraft:stone_bricks"
    return "minecraft:stone_bricks", "minecraft:dark_oak_planks"


def corridor_spacing(width: float, factor: float = CORRIDOR_SPACING) -> float:
    """Centre spacing of the square chain for one corridor (never below 0.5 m)."""
    return max(float(width) * float(factor), 0.5)


def corridor_boxes(x0: float, y0: float, x1: float, y1: float, width: float,
                   factor: float = CORRIDOR_SPACING) -> list[tuple[float, float, float, float]]:
    """Split one polyline segment into axis-aligned corridor boxes.

    Every returned tuple is the (x0, y0, x1, y1) footprint of one box. An
    axis-aligned run returns a single box that *is* the corridor. A run that cuts
    across the grid returns a chain of squares of side `width`, centred on the
    line and spaced `corridor_spacing()` apart, so the union follows the line
    instead of filling the run's bounding rectangle. Lateral coverage is exact
    (a square covers +/- width/2 either side of a centre), and the chain is
    connected because the spacing is below one width.
    """
    width = float(width)
    half = width / 2.0
    dx, dy = x1 - x0, y1 - y0
    if abs(dx) < 1e-9 or abs(dy) < 1e-9:
        return [(min(x0, x1) - half, min(y0, y1) - half,
                 max(x0, x1) + half, max(y0, y1) + half)]
    length = math.hypot(dx, dy)
    count = max(2, math.ceil(length / corridor_spacing(width, factor)) + 1)
    return [(x0 + dx * index / (count - 1) - half, y0 + dy * index / (count - 1) - half,
             x0 + dx * index / (count - 1) + half, y0 + dy * index / (count - 1) + half)
            for index in range(count)]


def _storey_bands(name: str, outlines: list[tuple[float, float, float, float]], z0: float, wall: float,
                  wall_top: float, storey_h: float, block: str) -> list[dict]:
    """A one-metre band at each storey line: glazing for the modern profile, a
    timber course for the arcane one.

    Drawn as extra boxes over the shell rather than by splitting the wall, so
    the wall geometry stays as it was, and each band follows its own storey's
    outline so a setback floor keeps its band on the stepped edge. The ground
    storey's east side is left alone because that is where the entrance is.
    """
    parts: list[dict] = []
    for level, (x0, x1, n0, n1) in enumerate(outlines):
        high = z0 + (level + 1) * storey_h
        low = high - 1.0
        if low <= z0 + wall or high > wall_top:
            continue
        parts.append(_box(f"{name}_band_{level}_west", x0, x0 + wall, n0, n1, low, high, block))
        parts.append(_box(f"{name}_band_{level}_south", x0 + wall, x1 - wall, n0, n0 + wall, low, high, block))
        parts.append(_box(f"{name}_band_{level}_north", x0 + wall, x1 - wall, n1 - wall, n1, low, high, block))
        if level > 0:
            parts.append(_box(f"{name}_band_{level}_east", x1 - wall, x1, n0 + wall, n1 - wall, low, high, block))
    return parts


def _storey_outlines(building: dict) -> list[tuple[float, float, float, float]]:
    """West, east, south and north outline of every storey.

    The source declares one setback per storey; revisions that predate that
    field keep a single flush outline, which is what they were exported as.
    """
    (x0, n0, _), (x1, n1, _) = building["bounds"]["min"], building["bounds"]["max"]
    storeys = building["attributes"]["storeys"]
    insets = building["geometry"].get("storey_insets_local_m")
    if insets is None:
        insets = [[0.0, 0.0, 0.0, 0.0] for _ in range(storeys)]
    if len(insets) != storeys or any(len(o) != 4 or min(o) < 0 for o in insets):
        raise CityExportError("target.building_setbacks", building["id"])
    outlines = [(x0 + o[0], x1 - o[1], n0 + o[2], n1 - o[3]) for o in insets]
    previous = None
    for west, east, south, north in outlines:
        if not (west + 2.0 * 0.3 <= east and south + 2.0 * 0.3 <= north):
            raise CityExportError("target.building_setbacks", building["id"])
        if previous is not None and (west < previous[0] or east > previous[1]
                                     or south < previous[2] or north > previous[3]):
            raise CityExportError("target.building_setbacks", building["id"])
        previous = (west, east, south, north)
    return outlines

# Furniture is still a box proxy, but the block picks up the room's function so
# a bedroom, a workshop and a chapel do not read the same from inside.
FURNITURE_BLOCKS = {
    "hearth": "minecraft:furnace", "bench": "minecraft:oak_slab", "bed": "minecraft:red_bed",
    "counter": "minecraft:oak_fence", "display_rack": "minecraft:barrel", "crate_stack": "minecraft:barrel",
    "workbench": "minecraft:crafting_table", "anvil": "minecraft:anvil", "tool_rack": "minecraft:oak_fence",
    "reading_table": "minecraft:oak_slab", "chair": "minecraft:oak_slab", "shelf": "minecraft:bookshelf",
    "long_table": "minecraft:oak_planks", "chest": "minecraft:chest",
    "altar": "minecraft:chiseled_quartz_block", "pew": "minecraft:oak_slab", "cabinet": "minecraft:barrel",
    "desk": "minecraft:crafting_table",
    # The scene pipeline's furniture vocabulary: added here so a scene export
    # places these instead of failing closed, which is what it did for the
    # seven uses this map did not know yet.
    "table": "minecraft:oak_planks", "crate": "minecraft:barrel",
    "pallet": "minecraft:oak_slab", "machine": "minecraft:crafting_table",
    # `glowstone` is not in the palette, so a lamp is glass: a mapping to a
    # block the palette does not carry would fail at voxel time.
    "board": "minecraft:oak_fence", "lamp": "minecraft:glass",
    "reception": "minecraft:barrel", "desk_chair": "minecraft:oak_slab",
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
        return [_box(name + "_flat_roof_proxy", x0 - ROOF_EAVE_M, x1 + ROOF_EAVE_M,
                     n0 - ROOF_EAVE_M, n1 + ROOF_EAVE_M, z1 - roof_h, z1, block)]
    steps = max(2, min(4, int(round(roof_h))))
    parts: list[dict] = []
    ex0, ex1 = x0 - ROOF_EAVE_M, x1 + ROOF_EAVE_M
    en0, en1 = n0 - ROOF_EAVE_M, n1 + ROOF_EAVE_M
    for index in range(steps):
        low = z1 - roof_h + roof_h * index / steps
        high = z1 - roof_h + roof_h * (index + 1) / steps
        inset_n = (en1 - en0) * index / (2 * steps)
        inset_x = (ex1 - ex0) * index / (2 * steps) if style == "spire" else 0.0
        parts.append(_box(f"{name}_roof_{index:02}", ex0 + inset_x, ex1 - inset_x,
                          en0 + inset_n, en1 - inset_n, low, high, block))
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

    Envelope, storey count, storey height, wall and floor thickness, per-storey
    setbacks, stair void and east entrance all come from source fields, so the
    shell stays derived from the source rather than invented. Each storey's
    wall ring and band follow that storey's outline, so a declared setback
    becomes a stepped massing with a walkable terrace on the slab below it —
    the part of the slab the smaller storey no longer covers. Only buildings
    whose interior_state is `generated` carry partitions, a stair and
    furniture; the rest stay a shell with an open upper floor and no way up,
    which the report states explicitly. A stair only reaches the first upper
    slab, so storeys above the second are enclosed and unreachable — a source
    limitation, not an adapter choice.
    """
    g = building["geometry"]
    if g["representation"] != "parametric_building" or g["entry"].get("side") not in {
            "east", "west", "north", "south"}:
        raise CityExportError("target.building_geometry", building["id"])
    (x0, n0, z0), (x1, n1, z1) = building["bounds"]["min"], building["bounds"]["max"]
    wall, floor, roof = g["wall_thickness_m"], g["floor_thickness_m"], g["roof_height_m"]
    storey_count = building["attributes"]["storeys"]
    if type(storey_count) is not int or storey_count < 1:
        raise CityExportError("target.building_storeys", building["id"])
    outlines = _storey_outlines(building)
    storey_h = g["storey_height_m"]
    upper_z = z0 + storey_h
    upper_top = upper_z + floor
    void = g["stair_void_local_m"]
    vx0, vn0 = x0 + void["min"][0], n0 + void["min"][1]
    vx1, vn1 = x0 + void["max"][0], n0 + void["max"][1]
    # A single-storey building has no stair reservation to check: the scene
    # pipeline emits an empty one for those, and the void is never used below.
    if storey_count >= 2 and not (x0 < vx0 < vx1 < x1 and n0 < vn0 < vn1 < n1):
        raise CityExportError("target.building_void", building["id"])
    ground = outlines[0]
    entry = g["entry"]
    # The entrance may be on any of the four sides: the scene pipeline puts it
    # on the side that faces the street, and a shell that only understands an
    # east door cannot express that.
    side = entry.get("side")
    if side not in {"east", "west", "north", "south"}:
        raise CityExportError("target.building_entry", building["id"])
    horizontal = side in {"north", "south"}
    along_base = ground[0] if horizontal else ground[2]
    along_span = (ground[1] - ground[0]) if horizontal else (ground[3] - ground[2])
    door_a0 = along_base + entry["offset_m"]
    door_a1 = door_a0 + entry["width_m"]
    door_top = z0 + floor + entry["height_m"]
    # A door opening has to clear whole blocks: the declared height is snapped
    # up to at least two blocks and the lintel starts on that cell boundary,
    # otherwise the quantised gap collapses to a single block and is not
    # walkable. Carving with air afterwards would not work either, because
    # `//paste -a` skips air cells.
    door_clear_low = math.ceil(z0 + floor)
    door_blocks_tall = max(2, int(entry["height_m"]))
    lintel_low = max(door_top, door_clear_low + door_blocks_tall)
    # A storey squeezed below "slab + two walkable blocks" cannot hold that
    # opening above the slab (a 2.92 m apartment storey in the modern scene hit
    # this on 2026-09-27). Instead of refusing the shell, the doorway is taken
    # down to the ground: the ground slab is split around the doorway below and
    # the opening runs from the ground up, so the threshold is the 0.2—0.3 m
    # step from the terrain onto the slab and the way in stays walkable.
    carved = lintel_low > z0 + storey_h
    if carved:
        door_clear_low = math.floor(z0 + floor)
        lintel_low = max(door_top, door_clear_low + door_blocks_tall)
    # The ground storey carries the entrance, so the door and its lintel have to
    # fit inside that storey rather than somewhere up the facade. A door that
    # already reaches the storey line simply has no lintel to place.
    if not (along_base + wall < door_a0 < door_a1 < along_base + along_span - wall
            and lintel_low <= z0 + storey_h):
        raise CityExportError("target.building_entry", building["id"])
    name = building["id"]
    shell, plank = _shell_materials(style)
    if carved:
        if horizontal:
            parts = [_box(f"{name}_floor_west", ground[0], door_a0, ground[2], ground[3],
                          z0, z0 + floor, plank),
                     _box(f"{name}_floor_east", door_a1, ground[1], ground[2], ground[3],
                          z0, z0 + floor, plank)]
        else:
            parts = [_box(f"{name}_floor_south", ground[0], ground[1], ground[2], door_a0,
                          z0, z0 + floor, plank),
                     _box(f"{name}_floor_north", ground[0], ground[1], door_a1, ground[3],
                          z0, z0 + floor, plank)]
    else:
        parts = [_box(name, ground[0], ground[1], ground[2], ground[3], z0, z0 + floor, plank)]
    for level in range(1, storey_count):
        top = z0 + level * g["storey_height_m"]
        if top + floor > z1 - roof:
            raise CityExportError("target.building_slab", building["id"])
        # The slab covers the storey below, so the part a smaller upper storey
        # leaves exposed is already the terrace that makes the setback read.
        bx0, bx1, bn0, bn1 = outlines[level - 1]
        if level == 1:
            parts.extend([
                _box(f"{name}_floor{level}_west", bx0, vx0, bn0, bn1, top, top + floor, plank),
                _box(f"{name}_floor{level}_east", vx1, bx1, bn0, bn1, top, top + floor, plank),
                _box(f"{name}_floor{level}_south", vx0, vx1, bn0, vn0, top, top + floor, plank),
                _box(f"{name}_floor{level}_north", vx0, vx1, vn1, bn1, top, top + floor, plank),
            ])
        else:
            parts.append(_box(f"{name}_floor{level}", bx0, bx1, bn0, bn1, top, top + floor, plank))
    wall_top = z1 - roof
    for level, (sx0, sx1, sn0, sn1) in enumerate(outlines):
        bottom = z0 + level * storey_h + floor
        # The top storey reaches the roof base; the ones below stop under the
        # slab that separates them from the storey above.
        top = wall_top if level == storey_count - 1 else z0 + (level + 1) * storey_h
        # The ground storey keeps the original unsuffixed names so existing
        # probes and evidence still point at the same source ids.
        suffix = "" if level == 0 else f"_s{level}"
        # Four faces, and at ground level the entrance face is split around the
        # opening instead of being drawn whole over the door. Names are kept
        # stable for the faces that already existed, so old probes still resolve.
        for face, f0, f1, axis in (("west", sx0, sx0 + wall, "n"), ("east", sx1 - wall, sx1, "n"),
                                   ("south", sn0, sn0 + wall, "x"), ("north", sn1 - wall, sn1, "x")):
            if level == 0 and face == side:
                if axis == "n":
                    parts.append(_box(f"{name}_{face}_wall_south", f0, f1, sn0 + wall, door_a0, bottom, top, shell))
                    parts.append(_box(f"{name}_{face}_wall_north", f0, f1, door_a1, sn1 - wall, bottom, top, shell))
                else:
                    parts.append(_box(f"{name}_{face}_wall_west", sx0 + wall, door_a0, f0, f1, bottom, top, shell))
                    parts.append(_box(f"{name}_{face}_wall_east", door_a1, sx1 - wall, f0, f1, bottom, top, shell))
                if lintel_low < top:
                    lintel_id = name + ("_east_door_lintel" if face == "east" else f"_{face}_door_lintel")
                    parts.append(_box(lintel_id, f0, f1, door_a0, door_a1, lintel_low, top, shell) if axis == "n"
                                 else _box(lintel_id, door_a0, door_a1, f0, f1, lintel_low, top, shell))
            elif axis == "n":
                parts.append(_box(f"{name}{suffix}_{face}_wall", f0, f1, sn0 + wall, sn1 - wall,
                                  bottom, top, shell))
            else:
                parts.append(_box(f"{name}{suffix}_{face}_wall", sx0 + wall, sx1 - wall, f0, f1,
                                  bottom, top, shell))
    tx0, tx1, tn0, tn1 = outlines[-1]
    # The declared roof style lives in geometry; revisions that only carried it
    # as an attribute still get their real silhouette instead of a flat slab.
    roof_style = g.get("roof_style") or building["attributes"].get("roof_style", "flat")
    parts.extend(_roof_boxes(name, tx0, tx1, tn0, tn1, z1, roof, roof_style, plank))
    band_block = "minecraft:dark_oak_planks" if style == "arcane_medieval" else "minecraft:glass"
    parts.extend(_storey_bands(name, outlines, z0, wall, wall_top, storey_h, band_block))
    # Facade relief (building skill rule 3): a plinth along the ground storey
    # and corner posts on every storey edge. The entrance side keeps its plinth
    # gap so the doorway stays clear; everything else is additive, so existing
    # wall boxes and probe coordinates do not move.
    plinth_block, post_block = _facade_blocks(style)
    gx0, gx1, gn0, gn1 = outlines[0]
    plinth_top = z0 + floor + 1.0
    for face, box in (("south", (gx0, gx1, gn0, gn0 + wall)),
                      ("north", (gx0, gx1, gn1 - wall, gn1)),
                      ("west", (gx0, gx0 + wall, gn0 + wall, gn1 - wall)),
                      ("east", (gx1 - wall, gx1, gn0 + wall, gn1 - wall))):
        if face == side:
            continue
        parts.append(_box(f"{name}_plinth_{face}", box[0], box[1], box[2], box[3],
                          z0 + floor, plinth_top, plinth_block))
    for level, (sx0, sx1, sn0, sn1) in enumerate(outlines):
        bottom = z0 + level * storey_h + floor
        top = wall_top if level == storey_count - 1 else z0 + (level + 1) * storey_h
        suffix = "" if level == 0 else f"_s{level}"
        parts.extend([
            _box(f"{name}{suffix}_post_sw", sx0, sx0 + wall, sn0, sn0 + wall, bottom, top, post_block),
            _box(f"{name}{suffix}_post_se", sx1 - wall, sx1, sn0, sn0 + wall, bottom, top, post_block),
            _box(f"{name}{suffix}_post_nw", sx0, sx0 + wall, sn1 - wall, sn1, bottom, top, post_block),
            _box(f"{name}{suffix}_post_ne", sx1 - wall, sx1, sn1 - wall, sn1, bottom, top, post_block),
        ])
    # Entrance articulation (building-skill rule 6): a step bridging the ground
    # and the slab, plus a porch slab over the doorway. Both stand outside the
    # wall on purpose. Applied to scene-pipeline buildings only: the frozen
    # city.7 reference keeps exactly the geometry its evidence was taken from,
    # and its tests require every part to sit inside the building envelope.
    if g.get("assignment") == "scene_pipeline_stage_e":
        porch_block = ("minecraft:dark_oak_planks" if style == "arcane_medieval"
                       else "minecraft:smooth_stone")
        head = z0 + floor + float(entry["height_m"])
        depth = 1.0
        if horizontal:
            s0, s1 = (gn0 - depth, gn0) if side == "south" else (gn1, gn1 + depth)
            parts.append(_box(f"{name}_entry_step", door_a0, door_a1, s0, s1, z0, z0 + floor,
                              porch_block))
            p0, p1 = (s0 - 0.6, gn0 + 0.6) if side == "south" else (gn1 - 0.6, s1 + 0.6)
            parts.append(_box(f"{name}_porch", door_a0 - 1.0, door_a1 + 1.0, p0, p1, head, head + 0.4,
                              porch_block))
        else:
            s0, s1 = (gx0 - depth, gx0) if side == "west" else (gx1, gx1 + depth)
            parts.append(_box(f"{name}_entry_step", s0, s1, door_a0, door_a1, z0, z0 + floor,
                              porch_block))
            p0, p1 = (s0 - 0.6, gx0 + 0.6) if side == "west" else (gx1 - 0.6, s1 + 0.6)
            parts.append(_box(f"{name}_porch", p0, p1, door_a0 - 1.0, door_a1 + 1.0, head, head + 0.4,
                              porch_block))
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
    if not stairs:
        raise CityExportError("target.interior_plan", building["id"])
    # Every storey above the first needs its own flight, and each flight has to
    # start and end on storey floor levels: that is what makes the upper floors
    # reachable at all (work orders 017/022). One flight was the old contract.
    levels = [round(z0 + floor + index * storey_h, 3) for index in range(storey_count)]
    for stair in stairs:
        sg = stair["geometry"]
        if sg["representation"] != "straight_stair" or sg["steps"] < 1:
            raise CityExportError("target.interior_geometry", building["id"])
        (sx0, sn0, _), (sx1, sn1, _) = stair["bounds"]["min"], stair["bounds"]["max"]
        flight_levels = sg.get("floor_levels_m") or []
        if len(flight_levels) != 2 or abs((flight_levels[1] - flight_levels[0]) - storey_h) > 0.01:
            raise CityExportError("target.interior_void", building["id"])
        if not any(abs(flight_levels[0] - level) < 0.01 for level in levels):
            raise CityExportError("target.interior_void", building["id"])
        # Source bounds are rounded to six decimals while the void is derived
        # from the lot origin, so a stair that fills its reservation exactly can
        # land a femtometre outside it. Compare the plan fit with that epsilon.
        if not (vx0 - COORD_EPS_M <= sx0 < sx1 <= vx1 + COORD_EPS_M
                and vn0 - COORD_EPS_M <= sn0 < sn1 <= vn1 + COORD_EPS_M):
            raise CityExportError("target.interior_void", building["id"])
        step_run, step_rise = sg["run_m"] / sg["steps"], sg["rise_m"] / sg["steps"]
        clear_x0 = sx0 + (sx1 - sx0 - sg["clear_width_m"]) / 2
        base, top = flight_levels[0], flight_levels[1]
        for index in range(sg["steps"]):
            parts.append(_box(f"{stair['id']}_tread_{index + 1:02}", clear_x0,
                              clear_x0 + sg["clear_width_m"],
                              sn0 + index * step_run, sn0 + (index + 1) * step_run,
                              base, base + (index + 1) * step_rise, plank))
        parts.append(_box(stair["id"] + "_landing", clear_x0, clear_x0 + sg["clear_width_m"],
                          sn0 + sg["run_m"], sn1, top - floor, top, plank))
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
    shell_ranges: list[tuple[int, int]] = []
    for record in entities:
        if record["kind"] not in {"road", "bridge", "building", "wall"}:
            continue
        if record["geometry"]["representation"] not in {"box", "parametric_building"}:
            raise CityExportError("target.city_geometry", record["id"])
        if record["kind"] == "building":
            with_interior = include_interiors and record["attributes"]["interior_state"] == "generated"
            start = len(boxes)
            boxes.extend(_building_shell(record, by_id, with_interior=with_interior, style=style))
            shell_ranges.append((start, len(boxes)))
            continue
        low, high = record["bounds"]["min"], record["bounds"]["max"]
        block = {"road": _street_block(style), "bridge": "minecraft:oak_planks",
                 "wall": "minecraft:stone_bricks"}[record["kind"]]
        boxes.append(_box(record["id"], low[0], high[0], low[1], high[1], low[2], high[2], block))
    terrain = next(r for r in entities if r["kind"] == "terrain")
    tlo, thi = terrain["bounds"]["min"], terrain["bounds"]["max"]
    if (specs[0].get("extensions") or {}).get("scene_spec"):
        # A scene pipeline plans a river network, a canal or a coastline, so the
        # flat-bank policy cannot apply: the ground is one flat proxy and the
        # water is whatever the source channel polylines say it is.
        surface_boxes = [_box("terrain_proxy", tlo[0], thi[0], tlo[1], thi[1], -0.2, 0.25,
                              "minecraft:grass_block")]
        for record in entities:
            if record["kind"] not in {"river", "coast"}:
                continue
            geometry = record["geometry"]
            points = geometry.get("centerline_m") or []
            if len(points) < 2:
                raise CityExportError("target.city_river", f"{record['id']} has no centreline")
            width = float(geometry.get("width_m", 8.0))
            for index in range(len(points) - 1):
                x0, y0 = points[index][0], points[index][1]
                x1, y1 = points[index + 1][0], points[index + 1][1]
                for sub, (wx0, wy0, wx1, wy1) in enumerate(corridor_boxes(x0, y0, x1, y1, width)):
                    surface_boxes.append(_box(f"{record['id']}_water_{index:03}_{sub:02}", wx0, wx1,
                                              wy0, wy1, -0.05, 0.05, "minecraft:water"))
        # Open spaces (work order 017 class 2): a plaza or a park is paving, a
        # path and fixed furniture on the ground row. The source names material
        # families; the palette decides the blocks.
        paving_blocks = {"stone": "minecraft:stone_bricks", "path": "minecraft:smooth_stone",
                         "gravel": "minecraft:gray_concrete"}
        fixture_blocks = {"lamp": "minecraft:glass", "bench": "minecraft:oak_slab",
                          "tree": "minecraft:oak_fence", "planter": "minecraft:grass_block",
                          # Yards: a crate is a barrel, a stacked container is a
                          # plain block that reads as a box.
                          "crate": "minecraft:barrel", "stack": "minecraft:gray_concrete"}
        for record in entities:
            if record["kind"] != "open_space":
                continue
            (ox, on, _), (mx, mn, _) = record["bounds"]["min"], record["bounds"]["max"]
            plan = record["geometry"]
            surface_boxes.append(_box(record["id"], ox, mx, on, mn, 0.0, 0.25,
                                      paving_blocks[plan["paving_token"]]))
            px0, py0, px1, py1 = plan["path"]["rect"]
            surface_boxes.append(_box(f"{record['id']}_path", ox + px0, ox + px1, on + py0, on + py1,
                                      0.25, 0.4, paving_blocks[plan["path"]["token"]]))
            for item in plan["fixtures"]:
                surface_boxes.append(_box(item["id"], ox + item["x0"], ox + item["x1"],
                                          on + item["y0"], on + item["y1"], 0.25, 1.25,
                                          fixture_blocks[item["use"]]))
        # Compounds (work order 017 class 3): a castle is a keep, towers, a hall
        # and a curtain wall. Each volume becomes a hollow shell with its own
        # roof, so the bailey stays open and the parts read as separate masses.
        for record in entities:
            if record["kind"] != "compound":
                continue
            (ox, on, _), (_, _, _) = record["bounds"]["min"], record["bounds"]["max"]
            shell_wall = 0.3
            for volume in record["geometry"]["volumes"]:
                vx0, vy0 = ox + volume["x0"], on + volume["y0"]
                vx1, vy1 = ox + volume["x1"], on + volume["y1"]
                top = volume["height_m"]
                block = "minecraft:oak_planks" if volume["role"] == "hall" else "minecraft:smooth_stone"
                name = f"{record['id']}_{volume['id']}"
                surface_boxes.append(_box(f"{name}_west", vx0, vx0 + shell_wall, vy0, vy1,
                                          0.0, top, block))
                surface_boxes.append(_box(f"{name}_east", vx1 - shell_wall, vx1, vy0, vy1,
                                          0.0, top, block))
                surface_boxes.append(_box(f"{name}_south", vx0 + shell_wall, vx1 - shell_wall,
                                          vy0, vy0 + shell_wall, 0.0, top, block))
                surface_boxes.append(_box(f"{name}_north", vx0 + shell_wall, vx1 - shell_wall,
                                          vy1 - shell_wall, vy1, 0.0, top, block))
                roof_height = 0.4 if volume["roof"] == "flat" else \
                    min(2.4, max(0.6, min(vx1 - vx0, vy1 - vy0) * 0.15))
                surface_boxes.extend(_roof_boxes(name, vx0, vx1, vy0, vy1, top,
                                                 roof_height, volume["roof"], "minecraft:oak_planks"))
        # The source forbids wet building footprints. Keep the target robust as
        # well: flat water proxies must not replace a quantised floor or road.
        # Ground and water first, then the street network, and the building
        # shells last: a street corridor and a ground slab share the same block
        # row, and the building's own floor material has to win inside its
        # footprint. The legacy city.7 path keeps its original box order.
        shell_cells = {index for start, stop in shell_ranges for index in range(start, stop)}
        network = [box for index, box in enumerate(boxes) if index not in shell_cells]
        shells = [box for index, box in enumerate(boxes) if index in shell_cells]
        return surface_boxes + network + shells
    river = next(r for r in entities if r["kind"] == "river")
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
            # A declared setback means the shell is no longer one extruded
            # footprint, so the report has to say which storeys step back.
            insets = (record.get("geometry") or {}).get("storey_insets_local_m") or []
            stepped = [i for i, o in enumerate(insets) if any(abs(v) > 1e-6 for v in o)]
            setback = ("; storeys " + ", ".join(str(i) for i in stepped) + " step back from the outline below"
                       if stepped else "")
            if include_interiors and record["attributes"]["interior_state"] == "generated":
                classification, target, message = "approximated", "blocks:" + record["id"] + "_*", "hollow shell over " + str(record["attributes"]["storeys"]) + " storey(s) with the declared east opening, room partitions, floors and stair; treads below block resolution merge into whole-block steps and storeys above the second have no stair" + setback
            else:
                classification, target, message = "approximated", "blocks:" + record["id"] + "_*", "hollow shell with the declared east opening and upper-floor void; source interior_state is deferred, so no stair, rooms or furniture exist to place" + setback
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
