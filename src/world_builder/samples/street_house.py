"""Two-storey timber street house study shared by Unity and Minecraft.

Coordinates: x east, n north, u up, 1 m = 1 Minecraft block. The study is
hand-designed from a documented precedent; it does not represent the current
stage-E procedural designer or the WIR building contract.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import struct
from pathlib import Path

from world_builder.adapters.minecraft.sample import _compound, _tag, _utf8, _varint
from world_builder.adapters.unity.sample import _box, _canonical, _glb, UNITY_VERSION

VERSION = "street-house-study-0.5"
SOURCE_ID = "building_street_house_001"
WIDTH, HEIGHT, LENGTH = 20, 12, 18
DATA_VERSION = 4671
BLOCKS = [
    "minecraft:air", "minecraft:grass_block", "minecraft:stone_bricks",
    "minecraft:light_gray_concrete", "minecraft:dark_oak_planks",
    "minecraft:oak_planks", "minecraft:glass", "minecraft:smooth_stone",
    "minecraft:barrel", "minecraft:bookshelf",
    "minecraft:oak_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]",
    "minecraft:gray_concrete",
]
AIR, GRASS, STONE, PLASTER, FRAME, FLOOR, GLASS, PATH, BARREL, SHELF, STAIR, ROOF = range(len(BLOCKS))
UNITY_MATERIALS = [
    ("grass", (.28, .43, .20, 1)),
    ("stone_plinth", (.42, .42, .43, 1)),
    ("light_infill", (.85, .80, .70, 1)),
    ("dark_timber", (.12, .06, .03, 1)),
    ("oak_floor", (.52, .33, .17, 1)),
    ("window_glass", (.57, .78, .84, .65)),
    ("street_path", (.65, .64, .59, 1)),
    ("furnishing", (.38, .24, .13, 1)),
    ("dark_roof_tile_proxy", (.20, .21, .22, 1)),
]
MATERIAL = {GRASS: 0, STONE: 1, PLASTER: 2, FRAME: 3, FLOOR: 4,
            GLASS: 5, PATH: 6, BARREL: 7, SHELF: 7, STAIR: 4, ROOF: 8}


def _index(x: int, n: int, u: int) -> int:
    if not (0 <= x < WIDTH and 0 <= n < LENGTH and 0 <= u < HEIGHT):
        raise ValueError(f"study.bounds: {(x, n, u)}")
    return x + (LENGTH - 1 - n) * WIDTH + u * WIDTH * LENGTH


def build_grid() -> bytearray:
    grid = bytearray(WIDTH * LENGTH * HEIGHT)

    def put(x: int, n: int, u: int, block: int) -> None:
        grid[_index(x, n, u)] = block

    def fill(x0: int, x1: int, n0: int, n1: int, u0: int, u1: int, block: int) -> None:
        for u in range(u0, u1):
            for n in range(n0, n1):
                for x in range(x0, x1):
                    put(x, n, u, block)

    fill(0, WIDTH, 0, LENGTH, 0, 1, GRASS)
    fill(7, 11, 0, 3, 0, 1, PATH)
    fill(3, 17, 3, 16, 0, 1, STONE)
    fill(4, 16, 4, 15, 0, 1, FLOOR)
    # Ground shell: a 14 x 13 m shop facing south, workshop at the back.
    fill(3, 17, 3, 4, 1, 4, PLASTER)
    fill(3, 17, 15, 16, 1, 8, PLASTER)
    fill(3, 4, 4, 15, 1, 8, PLASTER)
    fill(16, 17, 4, 15, 1, 8, PLASTER)
    for x0, x1 in ((5, 7), (11, 13)):
        fill(x0, x1, 3, 4, 1, 3, GLASS)
    fill(8, 10, 3, 4, 1, 3, AIR)  # Road -> shop entrance.
    # Rear work area, with a two-cell passage and a direct stair approach.
    fill(4, 16, 10, 11, 1, 4, FRAME)
    fill(12, 15, 10, 11, 1, 4, AIR)
    fill(5, 8, 11, 13, 1, 2, BARREL)
    fill(4, 7, 7, 8, 1, 2, BARREL)  # Counter stays away from the doorway.
    # Upper floor has a real four-cell stair opening, so floor and stair meet.
    fill(3, 17, 2, 16, 4, 5, FLOOR)
    fill(12, 15, 6, 10, 4, 5, AIR)
    for n, u in zip(range(6, 10), range(1, 5)):
        fill(12, 15, n, n + 1, u, u + 1, STAIR)
    # Upper storey jetties one block over the shopfront.
    fill(3, 17, 2, 3, 5, 8, PLASTER)
    for x0, x1 in ((5, 7), (12, 14)):
        fill(x0, x1, 2, 3, 5, 7, GLASS)
    fill(5, 7, 8, 9, 5, 7, SHELF)
    fill(4, 13, 11, 12, 5, 8, FRAME)
    fill(6, 8, 11, 12, 5, 7, AIR)
    # Side windows: clear openings rather than glass pasted onto a solid wall.
    for n in (6, 7, 12, 13):
        for u in (5, 6):
            put(3, n, u, GLASS)
    for n in (12, 13):
        for u in (1, 2):
            put(16, n, u, GLASS)
    for n in (6, 7):
        for u in (1, 2):
            put(16, n, u, GLASS)
    for n in (10, 11):
        for u in (5, 6):
            put(16, n, u, GLASS)
    # Front facade frame follows the storey and opening rhythm.
    for x in (3, 7, 10, 16):
        fill(x, x + 1, 3, 4, 1, 4, FRAME)
        fill(x, x + 1, 2, 3, 5, 8, FRAME)
    fill(3, 17, 3, 4, 3, 4, FRAME)
    fill(8, 10, 3, 4, 3, 4, AIR)  # Full-height entrance clearance for Unity CharacterController.
    fill(3, 17, 2, 3, 7, 8, FRAME)
    fill(3, 17, 2, 3, 4, 5, FRAME)  # Readable jetty edge.
    fill(7, 11, 1, 3, 4, 5, FRAME)  # Clear the 1.8 m player below the entrance canopy.
    for x, u in ((8, 5), (9, 6), (14, 5), (15, 6)):
        put(x, 2, u, FRAME)
    for n in (3, 15):
        for x in (3, 16):
            fill(x, x + 1, n, n + 1, 1, 8, FRAME)
    # Long side receives the same post-and-beam rhythm as the street front.
    for n in (5, 9, 13):
        fill(16, 17, n, n + 1, 1, 8, FRAME)
    for u in (3, 7):
        fill(16, 17, 4, 15, u, u + 1, FRAME)
    # Stepped, deep gable roof. The ridge runs north-south.
    for u, inset in ((8, 0), (9, 2), (10, 4), (11, 6)):
        fill(2 + inset, 18 - inset, 1, 17, u, u + 1, ROOF)
    # Street-facing plaster gable framed by the roof; a chimney gives the side skyline a use.
    for u, x0, x1 in ((8, 4, 16), (9, 6, 14), (10, 8, 12)):
        fill(x0, x1, 1, 2, u, u + 1, PLASTER)
    for x, u in ((6, 8), (7, 9), (9, 8), (10, 9), (12, 8), (13, 9)):
        put(x, 1, u, FRAME)
    fill(14, 16, 12, 14, 9, 12, STONE)
    return grid


def _cuboids(grid: bytearray) -> list[dict]:
    """Greedy partition of target cells into material-consistent cuboids."""
    seen: set[tuple[int, int, int]] = set()
    pieces = []
    for u in range(HEIGHT):
        for n in range(LENGTH):
            for x in range(WIDTH):
                if (x, n, u) in seen:
                    continue
                block = grid[_index(x, n, u)]
                if block == AIR:
                    continue
                if block == STAIR:
                    seen.add((x, n, u))
                    for n0, n1, u0, u1 in ((n, n + 1, u, u + .5),
                                            (n + .5, n + 1, u + .5, u + 1)):
                        piece = _box(f"street_house_part_{len(pieces):03d}", SOURCE_ID,
                                     x, x + 1, n0, n1, u0, u1, MATERIAL[block])
                        piece["block"] = BLOCKS[block]
                        pieces.append(piece)
                    continue
                x1 = x + 1
                while x1 < WIDTH and (x1, n, u) not in seen and grid[_index(x1, n, u)] == block:
                    x1 += 1
                n1 = n + 1
                while n1 < LENGTH and all((xx, n1, u) not in seen and grid[_index(xx, n1, u)] == block
                                          for xx in range(x, x1)):
                    n1 += 1
                u1 = u + 1
                while u1 < HEIGHT and all((xx, nn, u1) not in seen and grid[_index(xx, nn, u1)] == block
                                          for nn in range(n, n1) for xx in range(x, x1)):
                    u1 += 1
                for uu in range(u, u1):
                    for nn in range(n, n1):
                        for xx in range(x, x1):
                            seen.add((xx, nn, uu))
                piece = _box(f"street_house_part_{len(pieces):03d}", SOURCE_ID,
                             x, x1, n, n1, u, u1, MATERIAL[block])
                piece["block"] = BLOCKS[block]
                pieces.append(piece)
    return pieces


def _schematic(grid: bytearray) -> bytes:
    palette = _compound(*(_tag(3, block, struct.pack(">i", i)) for i, block in enumerate(BLOCKS)))
    packed = b"".join(_varint(index) for index in grid)
    blocks = _compound(_tag(10, "Palette", palette),
                       _tag(7, "Data", struct.pack(">i", len(packed)) + packed),
                       _tag(9, "BlockEntities", b"\x0a" + struct.pack(">i", 0)))
    schematic = _compound(
        _tag(3, "Version", struct.pack(">i", 3)),
        _tag(3, "DataVersion", struct.pack(">i", DATA_VERSION)),
        _tag(2, "Width", struct.pack(">h", WIDTH)),
        _tag(2, "Height", struct.pack(">h", HEIGHT)),
        _tag(2, "Length", struct.pack(">h", LENGTH)),
        _tag(11, "Offset", struct.pack(">i", 3) + struct.pack(">iii", 0, 0, 0)),
        _tag(10, "Metadata", _compound(_tag(8, "Name", _utf8("Street house style study")),
                                      _tag(8, "Author", _utf8("world_builder")))),
        _tag(10, "Blocks", blocks),
    )
    root = _tag(10, "", _compound(_tag(10, "Schematic", schematic)))
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0, compresslevel=9) as target:
        target.write(root)
    return buffer.getvalue()


def _route_checks(grid: bytearray) -> dict:
    # These checks prove only voxel clearance/support, not a target player walk.
    checks = {
        "street_path": grid[_index(8, 1, 0)] == PATH,
        "front_door_clearance": all(grid[_index(x, 3, u)] == AIR for x in (8, 9) for u in (1, 2, 3)),
        "shop_floor": grid[_index(8, 6, 0)] == FLOOR,
        "workroom_passage": all(grid[_index(x, 10, u)] == AIR for x in (12, 13) for u in (1, 2)),
        "stair_flights": all(grid[_index(13, n, u)] == STAIR for n, u in zip(range(6, 10), range(1, 5))),
        "stair_headroom": all(grid[_index(13, n, u + 1)] == AIR for n, u in zip(range(6, 10), range(1, 5))),
        "upper_landing": grid[_index(13, 10, 4)] == FLOOR,
        "upper_room": all(grid[_index(10, 8, u)] == AIR for u in (5, 6)),
        "jetty": grid[_index(11, 2, 5)] == PLASTER and grid[_index(11, 2, 1)] == AIR,
        "roof_ridge": grid[_index(9, 8, 11)] == ROOF,
    }
    return checks


def export_study(output: str | Path) -> dict:
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=False)
    grid = build_grid()
    checks = _route_checks(grid)
    if not all(checks.values()):
        raise ValueError(f"study.route: {checks}")
    pieces = _cuboids(grid)
    glb = _glb(pieces, UNITY_MATERIALS)
    schem = _schematic(grid)
    geometry_hash = "sha256:" + hashlib.sha256(grid).hexdigest()
    design = {
        "version": VERSION, "source_id": SOURCE_ID,
        "precedent": "Historic England 1100401 (medieval timber-framed house)",
        "source_url": "https://historicengland.org.uk/listing/the-list/list-entry/1100401?section=comments-and-photos",
        "design_inference": "street shop + back workshop + upper dwelling; jettied timber facade and gable roof",
        "coordinates": "x east, n north, u up; metres; Minecraft target z = -n",
        "dimensions_m": [WIDTH, LENGTH, HEIGHT],
        "route": ["street", "south entrance", "front shop", "east stair", "upper landing", "upper room"],
        "geometry_sha256": geometry_hash,
        "static_checks": checks,
        "limits": ["hand-designed bounded sample, not the procedural E designer",
                   "Unity stairs use two half-height cuboids per cell; Minecraft uses north-facing stair blocks",
                   "no door leaf, diagonal timber bracing, true roof tiles, accessibility or building code claim"],
    }
    manifest = {
        "version": VERSION, "source_id": SOURCE_ID, "geometry_sha256": geometry_hash,
        "source_dimensions_m": [WIDTH, LENGTH, HEIGHT], "piece_count": len(pieces),
        "pieces": [{"name": piece["name"], "source_id": piece["source_id"]} for piece in pieces],
        "unity_version": UNITY_VERSION, "minecraft_data_version": DATA_VERSION,
        "glb_sha256": "sha256:" + hashlib.sha256(glb).hexdigest(),
        "schem_sha256": "sha256:" + hashlib.sha256(schem).hexdigest(),
        "non_air_blocks": sum(v != AIR for v in grid),
        "target_load": {"unity": "not_run", "minecraft": "not_run"},
    }
    (destination / "design.json").write_bytes(_canonical(design))
    (destination / "manifest.json").write_bytes(_canonical(manifest))
    (destination / "street_house.glb").write_bytes(glb)
    (destination / "street_house.schem").write_bytes(schem)
    return manifest
