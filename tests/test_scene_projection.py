"""Projection of a scene package into the Minecraft adapter's vocabulary."""
from __future__ import annotations

import pytest

from world_builder.adapters.minecraft.city import CityExportError, city_boxes
from world_builder.adapters.minecraft.scene import project_for_minecraft
from world_builder.planning import (assemble_scene, compile_brief, load_designs, load_setting_pack,
                                    plan_siting, plan_terrain)
from world_builder.planning.designer import design_building


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
        designs.append(design_building(site, pack.entry(site.type), pack, template,
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


def test_scene_water_cannot_overwrite_building_floors(scene_package) -> None:
    package, _ = scene_package
    boxes = city_boxes(project_for_minecraft(package), include_interiors=True)
    water = [index for index, box in enumerate(boxes) if box["block"] == "minecraft:water"]
    buildings = [index for index, box in enumerate(boxes)
                 if box["source_id"].startswith("building_")]
    assert water and buildings
    assert max(water) < min(buildings), "water must be laid before the shell and floor"
