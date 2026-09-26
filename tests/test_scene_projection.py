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


def test_export_still_stops_at_the_documented_gaps(scene_package) -> None:
    """The projection is not the whole job, and the failure says which part is left."""
    package, _ = scene_package
    projected = project_for_minecraft(package)
    with pytest.raises((CityExportError, ValueError)) as failure:
        city_boxes(projected, include_interiors=False)
    message = str(failure.value)
    assert "target.city_river" in message or "target.building" in message, message
