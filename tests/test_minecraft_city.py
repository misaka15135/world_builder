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

from world_builder.adapters.minecraft.city import (CityExportError, _berth_boxes, _building_shell,
                                                   _compound_boxes, _cylinder_boxes, _dock_boxes, _partition_boxes,
                                                   _roof_boxes, _shell_materials, _storey_bands,
                                                   _storey_outlines, _street_block, _vessel_boxes,
                                                   _window_boxes, export_city)
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
        # The west wall's lowest course is the plinth (building skill rule 3),
        # so the ground band reads as a base rather than as more wall.
        assert at(int(bx0), slab + 1, inner_z) == "minecraft:stone_bricks"  # west wall plinth
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
            # Roofs deliberately oversail the walls, so they are exempt.
            if "_roof_" in box["source_id"] or box["source_id"].endswith("_roof_proxy"):
                continue
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


def test_modern_style_gets_asphalt_streets_and_glazing() -> None:
    assert _street_block("arcane_medieval") == "minecraft:stone_bricks"
    assert _street_block("modern_grid") == "minecraft:gray_concrete"
    outlines = [(0.0, 10.0, 0.0, 12.0), (0.0, 10.0, 0.0, 12.0)]
    bands = _storey_bands("b", outlines, 0.0, 0.2, 9.0, 3.0, "minecraft:glass")
    assert len(bands) == 7, "three sides on both storeys plus the east side above the entrance"
    assert {band["block"] for band in bands} == {"minecraft:glass"}
    assert all(band["y1"] <= 9.0 + 1e-6 for band in bands), "glazing stays under the roof"
    assert not [band for band in bands if band["source_id"].endswith("_0_east")], "the entrance storey is not glazed"
    timber = _storey_bands("b", outlines, 0.0, 0.2, 9.0, 3.0, "minecraft:dark_oak_planks")
    assert {band["block"] for band in timber} == {"minecraft:dark_oak_planks"}


def test_a_berth_is_a_deck_over_the_water_and_a_quay_is_a_face() -> None:
    """Main line c (work order 017): piers and quays reach the blocks.

    Both are corridors in the WIR and both used to produce nothing, so the
    harbour had ships with nowhere to lie. A pier is a beam plus a deck above
    the waterline; a quay is a solid face rising to the quay top.
    """
    pier = {"id": "work_000", "kind": "pier", "attributes": {"work_type": "pier", "width_m": 14.0},
            "geometry": {"representation": "box", "size_m": [12.0, 14.0, 14.0]},
            "bounds": {"min": [0.0, 321.6, 0], "max": [12.0, 335.6, 14.0]}}
    boxes = _berth_boxes(pier)
    assert [box["source_id"] for box in boxes] == ["work_000_beam", "work_000_deck"]
    beam, deck = boxes
    assert beam["block"] == "minecraft:oak_planks" and deck["block"] == "minecraft:smooth_stone"
    assert beam["y1"] <= deck["y0"] + 1e-6, "the deck sits on its beam"
    assert beam["y0"] >= 1.0, "the pier stands above the waterline"
    quay = {"id": "work_004", "kind": "quay", "attributes": {"work_type": "quay_wall", "width_m": 9.0},
            "geometry": {"representation": "box", "size_m": [12.0, 9.0, 3.0]},
            "bounds": {"min": [0.0, 500.0, 0], "max": [12.0, 509.0, 3.0]}}
    wall = _berth_boxes(quay)
    assert len(wall) == 1 and wall[0]["block"] == "minecraft:stone_bricks"
    assert wall[0]["y0"] == 0.0 and wall[0]["y1"] == 3.0, "the quay rises from the waterline"


def test_a_cargo_ship_tapers_from_amidships_to_bow_and_stern() -> None:
    """Main line c (work order 017): a vessel is a stepped, tapered hull.

    The source states a mooring line and a beam. The hull is a run of sections
    that narrow towards both ends, with a boot-top below the waterline, a deck
    plate, a stern house and a funnel — before this the ship produced no blocks
    at all.
    """
    record = {"id": "work_002", "kind": "work",
              "attributes": {"work_type": "cargo_ship", "width_m": 12.0},
              "geometry": {"representation": "polyline", "width_m": 12.0,
                           "points_m": [[0.0, 0.0], [0.0, 60.0]]},
              "bounds": {"min": [0.0, 0.0, 0], "max": [1.0, 60.0, 12.0]}}
    boxes = _vessel_boxes(record)
    hull = [box for box in boxes if "_hull_" in box["source_id"] and "_boot_" not in box["source_id"]]
    assert len(hull) >= 8, "the hull is a run of sections"
    widths = [box["x1"] - box["x0"] for box in hull]
    middle = widths[len(widths) // 2]
    assert middle == max(widths), "the beam is widest amidships"
    assert widths[0] < middle * 0.5, "the bow tapers to well under the beam"
    assert widths[-1] < middle * 0.5, "the stern tapers too"
    assert {box["block"] for box in hull} == {"minecraft:gray_concrete"}
    boot = [box for box in boxes if "_hull_boot_" in box["source_id"]]
    assert {box["block"] for box in boot} == {"minecraft:red_concrete"}
    assert all(box["y1"] <= 1.2 + 1e-6 for box in boot), "the boot-top sits below the waterline"
    assert all(box["y0"] >= 5.0 - 1e-6 for box in boxes
               if "_deck_" in box["source_id"]), "the deck rides above the hull"
    house = next(box for box in boxes if box["source_id"].endswith("_house"))
    funnel = next(box for box in boxes if box["source_id"].endswith("_funnel"))
    assert house["y0"] >= 5.0 and funnel["y0"] >= house["y1"] - 1e-6, "the funnel stands on the house"
    assert house["z0"] < -30.0, "the house is aft, not amidships"


def test_a_round_tower_is_a_stepped_ring_not_a_box() -> None:
    """Main line c (work order 017): the curtain-wall towers read as round.

    The castle's towers were the last big silhouette still made of four flat
    faces. A tower declared `shape: round` is now built from the same stepped
    ring as a silo, with a stepped spire above the wall head, and the ring is
    inscribed in the square the designer reserved so the bailey does not move.
    """
    record = {"id": "c", "kind": "compound",
              "geometry": {"representation": "compound", "entry_side": "south", "materials": {},
                           "volumes": [{"id": "t0", "role": "tower", "x0": 0.0, "y0": 0.0,
                                        "x1": 8.0, "y1": 8.0, "base_m": 0.0, "height_m": 20.0,
                                        "roof": "spire", "shape": "round"},
                                       {"id": "k0", "role": "keep", "x0": 10.0, "y0": 10.0,
                                        "x1": 26.0, "y1": 26.0, "base_m": 0.0, "height_m": 18.0,
                                        "roof": "gable", "shape": "box"}]},
              "bounds": {"min": [0, 0, 0], "max": [30, 30, 25]}}
    boxes = _compound_boxes(record, 0.0, 0.0)
    ring = [box for box in boxes if "_t0_ring_" in box["source_id"]]
    assert len(ring) >= 12, "a circle needs a ring of chords"
    assert {box["block"] for box in ring} == {"minecraft:smooth_stone"}
    assert any("_t0_spire1" in box["source_id"] for box in boxes), "the spire is stepped, not one cone"
    # The ring stays inside the reserved square: no corner of the square is filled.
    assert all(box["x0"] >= -1e-6 and box["x1"] <= 8.0 + 1e-6 for box in ring)
    corners = [box for box in ring if box["x0"] < 1.0 and box["z0"] > -1.0]
    assert not corners, "the square's corner is outside the inscribed circle"
    keep = [box for box in boxes if "_k0_" in box["source_id"]]
    assert any(box["source_id"].endswith("_k0_south") for box in keep), "a box volume keeps its faces"


def test_a_dry_dock_excavates_its_basin_and_raises_a_gantry() -> None:
    """Main line c (work order 017): the one volume that removes material.

    The basin box carries air and is written after everything else, so it cuts
    the hollow the ground plan asks for; the floor sits under it, three faces
    are stone, the fourth is the gate sill the vessel crosses, and the gantry is
    two legs joined by a beam.
    """
    record = {"id": "dock_site_001", "kind": "dock",
              "attributes": {"design_state": "planned", "gate_side": "north", "gantry_height_m": 13.0},
              "geometry": {"representation": "basin", "depth_m": 5.0, "gate_side": "north",
                           "gantry_height_m": 13.0},
              "bounds": {"min": [106.0, 206.0, -5.0], "max": [175.2, 261.7, 5.0]}}
    boxes = _dock_boxes(record)
    basin = next(box for box in boxes if box["source_id"].endswith("_basin"))
    floor = next(box for box in boxes if box["source_id"].endswith("_floor"))
    assert basin["block"] == "minecraft:air" and floor["block"] == "minecraft:stone_bricks"
    assert floor["y1"] <= basin["y0"] + 1e-6, "the floor is under the excavation"
    walls = [box for box in boxes if "_wall_" in box["source_id"]]
    assert len(walls) == 3, "the gate face is left open"
    assert not [box for box in walls if box["source_id"].endswith("_wall_north")]
    assert any("_gate_sill" in box["source_id"] for box in boxes)
    gantry = [box for box in boxes if "_gantry_" in box["source_id"]]
    assert len(gantry) == 3, "two legs and a beam"
    assert max(box["y1"] for box in gantry) == 13.0


def test_a_tank_farm_is_stepped_into_a_round_shell() -> None:
    """Main line c (work order 017): the first non-box geometry reaches blocks.

    A vessel is a ring of chord boxes (the same polygonal approximation the
    castle's round wall uses) on a foundation disc, capped by a stepped dome.
    The inside stays hollow: only the foundation reaches the centre line.
    """
    record = {"id": "cyl", "kind": "cylinders",
              "geometry": {"representation": "cylinders",
                           "vessels": [{"id": "vessel0", "cx": 8.0, "cy": 8.0, "radius_m": 4.0,
                                        "height_m": 20.0, "roof": "dome"}]},
              "bounds": {"min": [0, 0, 0], "max": [16, 16, 20]}}
    boxes = _cylinder_boxes(record, 100.0, 200.0)
    shells = [box for box in boxes if "_shell_" in box["source_id"]]
    assert len(shells) >= 12, "a circle needs a ring of chords"
    assert {box["block"] for box in shells} == {"minecraft:light_gray_concrete"}
    assert any("_plinth_" in box["source_id"] for box in boxes), "the vessel stands on a foundation disc"
    assert any("_dome1" in box["source_id"] for box in boxes), "a dome is stepped, not one slab"
    assert all(box["y1"] <= 20.0 + 3 * 0.8 + 1e-6 for box in boxes), "the cap stays inside the stated height"
    centre = [box for box in boxes if box["x0"] <= 108 <= box["x1"] and box["z0"] <= -208 <= box["z1"]]
    # Only the foundation disc reaches the centre line at the bottom and the
    # dome closes over it at the top: nothing fills the drum in between.
    assert centre, "the foundation and the dome both cross the centre"
    assert not [box for box in centre if box["y0"] > 1.0 and box["y1"] <= 20.0], \
        "the vessel is a shell, not a filled drum"


def test_each_style_gets_its_own_framed_window() -> None:
    """Main line b (work order 017): windows carry frames, one profile per style.

    The adapter used to draw a bare one-metre glass column every six metres.
    Each background now states its own opening — narrow timber-framed slots in
    the arcane town, a ribbon of glass in the CBD, high mullioned lights on the
    works estate and squared stone frames at the harbour — and every window has
    a jamb either side, a sill course under it and a head over it.
    """
    cast = {}
    for style in ("arcane_medieval", "modern_grid", "industrial_works", "harbour_works"):
        boxes = _window_boxes("b", "", "south", 0.0, 0.3, 0.0, 20.0, 0.0, 12.0, style)
        cast[style] = boxes
        assert boxes, style
        panes = [box for box in boxes if box["block"] == "minecraft:glass"]
        jambs = [box for box in boxes if box["source_id"].endswith("_jamb_west")]
        sills = [box for box in boxes if box["source_id"].endswith("_sill")]
        heads = [box for box in boxes if box["source_id"].endswith("_head")]
        assert panes and len(jambs) == len(panes) == len(sills) == len(heads)
        assert all(box["y1"] <= 12.0 + 1e-6 for box in boxes), "the head stays under the slab above"
    # Four backgrounds, four window vocabularies.
    def jamb_block(style: str) -> set[str]:
        return {box["block"] for box in cast[style] if box["source_id"].endswith("_jamb_west")}

    assert jamb_block("arcane_medieval") == {"minecraft:dark_oak_planks"}
    assert jamb_block("modern_grid") == {"minecraft:light_gray_concrete"}
    assert jamb_block("harbour_works") == {"minecraft:stone_bricks"}
    widest = max(box["x1"] - box["x0"] for box in cast["modern_grid"] if box["block"] == "minecraft:glass")
    narrowest = max(box["x1"] - box["x0"] for box in cast["arcane_medieval"] if box["block"] == "minecraft:glass")
    # Two panes of timber-framed slot against four of CBD ribbon: a one-metre
    # slot between two dark jambs reads as a boarded hole, not a window.
    assert narrowest == 2.0 < widest == 4.0, "the CBD gets a ribbon, the timber town a slot"
    assert any(box["source_id"].endswith("_mullion") for box in cast["industrial_works"])
    assert not any(box["source_id"].endswith("_mullion") for box in cast["harbour_works"])
    # A window whose head would collide with the slab above is dropped, not clipped.
    assert _window_boxes("b", "", "south", 0.0, 0.3, 0.0, 20.0, 8.0, 9.0, "arcane_medieval") == []


def test_a_setback_storey_carries_its_own_outline() -> None:
    building = {"id": "b", "attributes": {"storeys": 2},
                "bounds": {"min": [0, 0, 0], "max": [16, 18, 11.2]},
                "geometry": {"storey_insets_local_m": [[0.0, 0.0, 0.0, 0.0], [2.0, 0.0, 1.0, 1.0]]}}
    outlines = _storey_outlines(building)
    assert outlines[0] == (0.0, 16.0, 0.0, 18.0)
    assert outlines[1] == (2.0, 16.0, 1.0, 17.0), "only the declared sides step back"
    building["geometry"]["storey_insets_local_m"] = [[0.0, 0.0, 0.0, 0.0], [-1.0, 0.0, 0.0, 0.0]]
    with pytest.raises(CityExportError):
        # A negative setback would be an overhang, which this template refuses.
        _storey_outlines(building)


def test_setbacks_reach_the_blocks_as_a_step() -> None:
    building = {
        "id": "building_x", "kind": "building", "parent_id": "parcel_x",
        "attributes": {"storeys": 2, "interior_state": "deferred"},
        "bounds": {"min": [0.0, 0.0, 2.0], "max": [16.0, 18.0, 11.2]},
        "geometry": {"representation": "parametric_building", "storey_height_m": 3.0,
                     "wall_thickness_m": 0.2, "floor_thickness_m": 0.2, "roof_height_m": 1.2,
                     "stair_void_local_m": {"min": [11, 3, 3], "max": [14, 13, 3.2]},
                     "entry": {"side": "east", "offset_m": 2, "width_m": 2, "height_m": 2.4},
                     "roof_style": "gable",
                     "storey_insets_local_m": [[0.0, 0.0, 0.0, 0.0], [2.0, 0.0, 1.0, 1.0]]},
    }
    parts = {part["source_id"]: part for part in _building_shell(building, {}, with_interior=False)}
    assert parts["building_x_west_wall"]["x0"] == 0.0, "the ground storey keeps the street edge"
    assert parts["building_x_s1_west_wall"]["x0"] == 2.0, "the upper storey steps back"
    assert parts["building_x_s1_south_wall"]["z0"] == -1.0 - 0.2
    assert parts["building_x_s1_north_wall"]["z1"] == -17.0 + 0.2
    # The slab under the setback still covers the whole storey below, so the
    # ring the smaller storey leaves exposed is a terrace rather than a hole.
    assert parts["building_x_floor1_west"]["x0"] == 0.0
    assert parts["building_x_floor1_east"]["x1"] == 16.0
    assert parts["building_x_floor1_north"]["z0"] == -18.0
    # The roof follows the top storey's outline, eave included.
    assert parts["building_x_roof_00"]["x0"] == 1.4
    assert parts["building_x_roof_00"]["z0"] == -17.6


def test_roofs_oversail_the_walls() -> None:
    flat = _roof_boxes("b", 0, 10, 0, 12, 20, 0.4, "flat", "minecraft:oak_planks")[0]
    assert flat["x0"] < 0 and flat["x1"] > 10 and flat["z0"] < -12 and flat["z1"] > 0, "an eave oversails every side"
    gable = _roof_boxes("b", 0, 10, 0, 12, 20, 1.2, "gable", "minecraft:oak_planks")
    assert gable[0]["x0"] < 0 and gable[0]["z0"] < -12
    assert gable[-1]["z0"] > gable[0]["z0"], "the gable still tapers above the eave"


def test_roof_style_drives_the_silhouette() -> None:
    # The declared roof has to reach the blocks from wherever the source keeps
    # it: older revisions only carried the style as an attribute, and reading
    # the wrong field is why every exported roof used to be a flat slab.
    building = {"id": "b", "attributes": {"storeys": 1, "roof_style": "gable"},
                "bounds": {"min": [0.0, 0.0, 2.0], "max": [10.0, 12.0, 6.4]},
                "geometry": {"representation": "parametric_building", "storey_height_m": 3.0,
                             "wall_thickness_m": 0.2, "floor_thickness_m": 0.2, "roof_height_m": 1.2,
                             "stair_void_local_m": {"min": [5, 3, 3], "max": [8, 9, 3.2]},
                             "entry": {"side": "east", "offset_m": 2, "width_m": 2, "height_m": 2.4}}}
    parts = {part["source_id"]: part for part in _building_shell(building, {}, with_interior=False)}
    assert "b_flat_roof_proxy" not in parts, "a gable is not a slab"
    assert "b_roof_00" in parts and "b_roof_01" in parts
    assert parts["b_roof_01"]["z0"] > parts["b_roof_00"]["z0"], "the gable tapers as it rises"
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
    assert spire[0]["x0"] < 0 and spire[0]["z1"] > 0, "the lowest step oversails the footprint"


def test_short_ground_storey_carves_the_doorway_through_the_floor() -> None:
    """A squeezed storey still gets a walkable entrance (adapter 0.1.0-city.6).

    The ground slab occupies block 0, so a 2.92 m storey cannot hold a two-block
    opening above it: the lintel would land at 3.0 m. Rather than reject the
    shell, the adapter cuts the doorway through the slab so the opening starts
    at the ground and the threshold is the 0.3 m step onto the slab. A modern
    apartment storey hit exactly this on 2026-09-27.
    """
    building = {
        "id": "building_short", "kind": "building", "parent_id": "parcel_x",
        "attributes": {"storeys": 1, "interior_state": "deferred"},
        "bounds": {"min": [0.0, 0.0, 2.0], "max": [16.0, 18.0, 5.32]},
        "geometry": {"representation": "parametric_building", "storey_height_m": 2.92,
                     "wall_thickness_m": 0.2, "floor_thickness_m": 0.3, "roof_height_m": 0.4,
                     "stair_void_local_m": {"min": [0, 0, 0], "max": [0, 0, 0]},
                     "entry": {"side": "south", "offset_m": 6.0, "width_m": 2.0, "height_m": 2.4},
                     "roof_style": "flat"},
    }
    parts = {part["source_id"]: part for part in _building_shell(building, {}, with_interior=False)}
    assert {"building_short_floor_west", "building_short_floor_east"} <= set(parts), \
        "the ground slab is split around the doorway"
    assert parts["building_short_floor_west"]["x1"] == 6.0
    assert parts["building_short_floor_east"]["x0"] == 8.0
    # 2.0 m base + 0.3 m slab + the 2.4 m door: the lintel starts above the door
    # and still stops under the 2.92 m storey line at 4.92 m.
    lintel = parts["building_short_south_door_lintel"]
    assert lintel["y0"] == pytest.approx(4.7)
    assert lintel["y1"] <= 2.0 + 2.92 + 1e-6
