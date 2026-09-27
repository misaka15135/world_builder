"""Stage F: assembling the scene into one WIR package (work order 018)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from world_builder.planning import (BuildingDesign, CompoundDesign, OpenSpaceDesign, assemble_scene,
                                    compile_brief, load_designs, load_setting_pack, plan_siting,
                                    plan_terrain, render_svg, validate_scene)
from world_builder.planning.designer import design

PROMPTS = {
    "arcane_medieval": "河谷里的魔法城邦，要有城堡和冒险者工会",
    "modern_metropolis": "现代大都市，有摩天楼和地铁枢纽",
    "industrial_park": "忙碌的工业产业园，成片厂房和铁路",
    "harbour": "海运港口，码头货轮和仓库",
}


def _scene(setting: str, seed: int = 4):
    pack = load_setting_pack(setting)
    brief = compile_brief(PROMPTS[setting], seed=seed)
    terrain = plan_terrain(setting, seed=seed, region_m=512, spacing_m=8)
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
                                       entry_side=side, seed=seed))
    designs = tuple(designs)
    package = assemble_scene(brief, pack, terrain, siting, designs)
    return pack, terrain, siting, designs, package, validate_scene(package, terrain, siting, designs)


@pytest.mark.parametrize("setting", sorted(PROMPTS))
def test_every_background_assembles_into_a_valid_package(setting: str) -> None:
    pack, terrain, siting, designs, package, report = _scene(setting)
    failures = [check for check in report["checks"] if check["state"] != "pass"]
    assert report["state"] == "pass", (setting, failures)
    buildings = [plan for plan in designs if isinstance(plan, BuildingDesign)]
    assert report["kinds"]["building"] == len(buildings)
    assert report["kinds"].get("open_space", 0) == sum(1 for plan in designs
                                                       if isinstance(plan, OpenSpaceDesign))
    assert report["kinds"].get("compound", 0) == sum(1 for plan in designs
                                                     if isinstance(plan, CompoundDesign))
    for kind in ("world", "terrain", "district", "road", "building", "storey", "room"):
        assert report["kinds"].get(kind, 0) > 0, (setting, kind)
    assert package["manifest"]["revision_id"].startswith("revision_")
    assert any(record["record_type"] == "revision" for record in package["records"])
    assert any(record["record_type"] == "asset" for record in package["records"]), "the heightfield is an asset"


def test_package_is_reproducible_and_carries_the_brief() -> None:
    first = _scene("harbour", seed=5)
    second = _scene("harbour", seed=5)
    assert first[4]["manifest"]["world_id"] == second[4]["manifest"]["world_id"]
    assert json.dumps(first[4], sort_keys=True) == json.dumps(second[4], sort_keys=True)
    spec = next(record for record in first[4]["records"] if record["record_type"] == "world_spec")
    scene = spec["extensions"]["scene_spec"]
    assert scene["setting"] == "harbour"
    assert scene["brief"]["setting"] == "harbour" and scene["brief_digest"].startswith("sha256:")
    assert set(scene["intended_targets"]) <= {"minecraft", "unity", "viewer", "ifc"}


def test_svg_plan_is_written(tmp_path: Path) -> None:
    pack, terrain, siting, designs, package, _ = _scene("industrial_park")
    path = render_svg(package, terrain, siting, designs, tmp_path / "plan.svg")
    text = path.read_text(encoding="utf-8")
    assert text.startswith("<svg") and text.rstrip().endswith("</svg>")
    assert "<polyline" in text and "<rect" in text
    assert text.count("<polyline") >= len(terrain.channels), "water is drawn"


def test_setting_and_registered_prompt_produce_the_same_scene(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "tools" / "assemble_scene.py"
    spec = importlib.util.spec_from_file_location("assemble_scene_tool", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    setting_path = tmp_path / "by-setting.json"
    prompt_path = tmp_path / "by-prompt.json"
    assert module.main(["--setting", "harbour", "--seed", "4", "--output", str(setting_path)]) == 0
    assert module.main(["--prompt", PROMPTS["harbour"], "--seed", "4", "--output", str(prompt_path)]) == 0
    assert json.loads(setting_path.read_text(encoding="utf-8")) == json.loads(prompt_path.read_text(encoding="utf-8"))
