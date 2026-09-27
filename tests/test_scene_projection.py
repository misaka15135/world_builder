"""Projection of a scene package into the Minecraft adapter's vocabulary."""
from __future__ import annotations

import math

import pytest

from world_builder.adapters.minecraft.city import CityExportError, city_boxes
from world_builder.adapters.minecraft.scene import project_for_minecraft
from world_builder.planning import (assemble_scene, compile_brief, load_designs, load_setting_pack,
                                    plan_siting, plan_terrain)
from world_builder.planning.designer import design


@pytest.fixture(scope="module")
def scene_package():
    setting = "arcane_medieval"
    pack = load_setting_pack(setting)
    brief = compile_brief("河谷里的魔法城邦，要有城堡和冒险者工会", seed=4)
    terrain = plan_terrain(setting, seed=4, region_m=512, spacing_m=8)
    siting = plan_siting(brief, pack, terrain)
    templates = load_designs(setting)
    designs = []
    for site in siting.sites:
        template = templates.get(site.type)
        if template is None:
            continue
        block = siting.block(site.block_id)
        side = "south" if abs(block.centre[1] - site.y0) < abs(block.centre[1] - site.y1) else "north"
        designs.append(design(site, pack.entry(site.type), pack, template,
                                       entry_side=side, seed=4))
    return assemble_scene(brief, pack, terrain, siting, tuple(designs)), siting


def test_polylines_become_segment_boxes(scene_package) -> None:
    package, siting = scene_package
    projected = project_for_minecraft(package)
    roads = [record for record in projected["records"]
             if record["record_type"] == "entity" and record["kind"] == "road"]
    originals = [record for record in package["records"]
                 if record["record_type"] == "entity" and record["kind"] == "road"]
    assert roads, "the projected package has roads"
    assert len(roads) > len(originals), "each polyline becomes at least one box per segment"
    assert all(record["geometry"]["representation"] == "box" for record in roads)
    assert all(record["bounds"]["max"][i] > record["bounds"]["min"][i] for record in roads for i in (0, 1))
    assert all("projected_from" in record["extensions"] for record in roads)
    # The source package is untouched: the projection is a translation, not an
    # edit of the semantic model.
    assert any(record["geometry"]["representation"] == "polyline" for record in originals)


def test_projection_carries_the_target_style(scene_package) -> None:
    package, _ = scene_package
    projected = project_for_minecraft(package)
    spec = next(record for record in projected["records"] if record["record_type"] == "world_spec")
    assert spec["extensions"]["city_spec"]["style_profile"] == "arcane_medieval"
    assert spec["extensions"]["city_spec"]["region_size_m"] == 512


def test_projected_scene_exports_boxes(scene_package) -> None:
    """After projection the adapter accepts the package: water, roads, shells."""
    package, _ = scene_package
    projected = project_for_minecraft(package)
    boxes = city_boxes(projected, include_interiors=False)
    sources = [box["source_id"] for box in boxes]
    assert any("water" in source for source in sources), "the channel network becomes water boxes"
    assert any(source.startswith("terrain_proxy") for source in sources), "one flat ground proxy"
    # The ground storey is split around its opening, on whichever face the
    # street was taken to be: the scene's heuristic asks for south or north.
    assert any(source.endswith(("_east_wall_south", "_west_wall_south",
                                "_south_wall_west", "_north_wall_west")) for source in sources), \
        "the ground storey is split around its opening"
    assert sum(1 for source in sources if "_roof_" in source) > 0
    # The plaza (work order 017 class 2) reaches the blocks as paving, a path
    # and its fixtures rather than as a building.
    open_space = [box for box in boxes if box["source_id"].startswith("open_space_")]
    assert open_space, "the scene's plaza is exported as a ground plan"
    assert any("_path" in box["source_id"] for box in open_space)
    assert any("_lamp" in box["source_id"] or "_bench" in box["source_id"] or "_tree" in box["source_id"]
               for box in boxes), "the plaza carries fixtures"
    # The castle (work order 017 class 3) reaches the blocks as separate volumes
    # rather than one building box.
    castle = [box for box in boxes if box["source_id"].startswith("compound_")]
    assert castle, "the scene's castle is exported as a compound"
    assert any("tower" in box["source_id"] for box in castle), "the castle keeps its towers"


def test_scene_water_cannot_overwrite_building_floors(scene_package) -> None:
    package, _ = scene_package
    boxes = city_boxes(project_for_minecraft(package), include_interiors=True)
    water = [index for index, box in enumerate(boxes) if box["block"] == "minecraft:water"]
    buildings = [index for index, box in enumerate(boxes)
                 if box["source_id"].startswith("building_")]
    assert water and buildings
    assert max(water) < min(buildings), "water must be laid before the shell and floor"


def test_projected_corridors_stay_near_the_corridor_area(scene_package) -> None:
    """A diagonal run must not turn into its own bounding rectangle.

    Work order 020: with the bounding-box projection a single 187 x 368 m
    street box paved more ground than the whole 512 m scene, and 30 of 33
    building slabs came out as stone. The rasterised corridor keeps every
    cross-grid box one corridor wide and the painted area near the corridor.
    """
    package, _ = scene_package
    projected = project_for_minecraft(package)
    sources = {record["id"]: record for record in package["records"] if record["record_type"] == "entity"}
    boxes = [record for record in projected["records"]
             if record["record_type"] == "entity" and record["kind"] in {"road", "wall"}
             and record["geometry"]["representation"] == "box"]
    assert boxes
    box_area = 0.0
    for record in boxes:
        source = sources[record["extensions"]["projected_from"]]
        width = float(source["geometry"].get("width_m", 4.0))
        start = source["geometry"]["points_m"][record["extensions"]["segment"]]
        end = source["geometry"]["points_m"][record["extensions"]["segment"] + 1]
        size = record["geometry"]["size_m"]
        axis_aligned = abs(end[0] - start[0]) < 1e-9 or abs(end[1] - start[1]) < 1e-9
        if axis_aligned:
            assert size[0] <= abs(end[0] - start[0]) + width + 1e-6, record["id"]
            assert size[1] <= abs(end[1] - start[1]) + width + 1e-6, record["id"]
        else:
            assert max(size[0], size[1]) <= width + 1e-6, record["id"]
        box_area += size[0] * size[1]
    corridor_area = 0.0
    for source in sources.values():
        geometry = source.get("geometry") or {}
        if source["kind"] not in {"road", "wall"} or geometry.get("representation") != "polyline":
            continue
        width = float(geometry.get("width_m", 4.0))
        points = geometry["points_m"]
        corridor_area += sum(math.dist(start, end) for start, end in zip(points, points[1:])) * width
    assert box_area <= corridor_area * 1.5, (box_area, corridor_area)


def test_scene_streets_are_laid_before_the_building_shells(scene_package) -> None:
    """A street corridor and a ground slab share a block row: the building wins.

    The scene branch lays ground and water, then the street network, then the
    building shells, so `building_site_*` floors keep the material the WIR
    declares even where a corridor crosses the footprint (work order 020).
    """
    package, _ = scene_package
    boxes = city_boxes(project_for_minecraft(package), include_interiors=False)
    # Stone bricks are both street setts and (since the facade relief landed)
    # the plinth course, so the street set is filtered by what a street is: a
    # run that belongs to the network, not to a building.
    streets = [index for index, box in enumerate(boxes)
               if box["block"] == "minecraft:stone_bricks"
               and "_plinth_" not in box["source_id"] and "_post_" not in box["source_id"]
               and not box["source_id"].startswith(("building", "open_space", "compound"))]
    shells = [index for index, box in enumerate(boxes)
              if box["source_id"].startswith("building_site_")]
    assert streets and shells
    assert max(streets) < min(shells), "streets must be laid before the shell and floor"
