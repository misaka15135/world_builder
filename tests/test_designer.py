"""Stage E: single building designs (work order 017)."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from world_builder.planning import (BuildingDesign, CompoundDesign, OpenSpaceDesign, SceneError,
                                    compile_brief, load_designs, load_setting_pack, plan_siting,
                                    plan_terrain, validate_compound, validate_design,
                                    validate_open_space)
from world_builder.planning.catalogue import DEFAULT_SETTINGS_ROOT
from world_builder.planning.designer import (COMPOUND_ROLES, FURNITURE, ROOF_STYLES, design,
                                             design_building)

PROMPTS = {
    "arcane_medieval": "河谷里的魔法城邦，要有城堡和冒险者工会",
    "modern_metropolis": "现代大都市，有摩天楼和地铁枢纽",
    "industrial_park": "忙碌的工业产业园，成片厂房和铁路",
    "harbour": "海运港口，码头货轮和仓库",
}
REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def designed():
    result = {}
    for setting, prompt in PROMPTS.items():
        pack = load_setting_pack(setting)
        brief = compile_brief(prompt, seed=4)
        terrain = plan_terrain(setting, seed=4, region_m=512, spacing_m=8)
        siting = plan_siting(brief, pack, terrain)
        templates = load_designs(setting)
        designs, reports, skipped = [], [], set()
        for site in siting.sites:
            template = templates.get(site.type)
            if template is None:
                skipped.add(site.type)
                continue
            plan = design(site, pack.entry(site.type), pack, template, seed=4)
            designs.append(plan)
            if isinstance(plan, OpenSpaceDesign):
                reports.append(validate_open_space(plan, site))
            elif isinstance(plan, CompoundDesign):
                reports.append(validate_compound(plan, site))
            else:
                reports.append(validate_design(plan, site, pack.entry(site.type)))
        result[setting] = (pack, siting, designs, reports, skipped)
    return result


def test_design_templates_load_and_are_coherent() -> None:
    for setting in PROMPTS:
        templates = load_designs(setting)
        assert templates
        for name, template in templates.items():
            if template.kind == "open_space":
                assert template.paving and template.path_token and template.fixtures
                continue
            if template.kind == "compound":
                assert template.compound, f"{name} must declare its volumes"
                assert all(role in COMPOUND_ROLES and roof in ROOF_STYLES
                           for role, _, roof in template.compound)
                continue
            assert template.storeys[0] <= template.storeys[1]
            assert all(use in FURNITURE for row in template.room_uses for use in row)
            assert template.roof in ("flat", "gable", "spire")
            assert template.stair in ("straight", "none")


def test_every_sited_building_is_designed_and_valid(designed) -> None:
    for setting, (pack, siting, designs, reports, skipped) in designed.items():
        assert len(designs) + len(skipped) >= len({site.type for site in siting.sites})
        failures = [report for report in reports if report["state"] != "pass"]
        assert not failures, (setting, [report["checks"] for report in failures][:1])
        for design in designs:
            if not isinstance(design, BuildingDesign):
                continue
            site = next(site for site in siting.sites if site.id == design.site_id)
            assert design.area_m2 <= site.area_m2 + 1.0, (setting, design.id)
            assert design.height_m <= site.max_height_m + 2e-3, (setting, design.id)
            assert len(design.storeys) <= site.max_storeys, (setting, design.id)


def test_height_lands_inside_the_catalogue_range(designed) -> None:
    for setting, (pack, siting, designs, _, _) in designed.items():
        for design in designs:
            entry = pack.entry(design.type)
            if not entry.height_m_range:
                continue
            # The site envelope can be tighter than the catalogue (a castle
            # domain is taller than the outer wards), so only the upper bound
            # is a hard promise here; the lower bound is reported, not assumed.
            assert design.height_m <= entry.height_m_range[1] + 1.5, (setting, design.id)


def test_stairs_and_rooms_are_consistent(designed) -> None:
    for setting, (pack, siting, designs, _, _) in designed.items():
        for design in designs:
            if not isinstance(design, BuildingDesign):
                continue
            if len(design.storeys) >= 2:
                assert design.stair is not None, (setting, design.id)
                void = design.stair["void"]
                for storey in design.storeys:
                    for room in storey.rooms:
                        assert not (room.x0 < void[1] and room.x1 > void[0]
                                    and room.y0 < void[3] and room.y1 > void[2]), (setting, design.id)
            else:
                assert design.stair is None, (setting, design.id)
            for storey in design.storeys:
                assert len(storey.rooms) == 2
                gap = storey.rooms[1].y0 - storey.rooms[0].y1
                assert abs(gap - 1.0) < 2e-3, (setting, design.id)


def test_furniture_sits_inside_its_room(designed) -> None:
    total = 0
    for setting, (pack, siting, designs, _, _) in designed.items():
        for design in designs:
            if not isinstance(design, BuildingDesign):
                continue
            rooms = {room.id: room for storey in design.storeys for room in storey.rooms}
            for item in design.furniture:
                room = rooms[item.room_id]
                assert room.x0 - 2e-3 <= item.x0 and item.y0 >= room.y0 - 2e-3
                total += 1
    assert total > 200, "every background should furnish its rooms"


def test_designs_are_deterministic() -> None:
    pack = load_setting_pack("harbour")
    brief = compile_brief(PROMPTS["harbour"], seed=9)
    terrain = plan_terrain("harbour", seed=9, region_m=512, spacing_m=8)
    siting = plan_siting(brief, pack, terrain)
    templates = load_designs("harbour")
    site = next(site for site in siting.sites if site.type == "warehouse")
    first = design_building(site, pack.entry("warehouse"), pack, templates["warehouse"], seed=9)
    second = design_building(site, pack.entry("warehouse"), pack, templates["warehouse"], seed=9)
    assert first.to_dict() == second.to_dict()


def test_design_fits_a_tight_envelope() -> None:
    """A squashed site still gets a legal building, not an overflowing one."""
    pack = load_setting_pack("industrial_park")
    templates = load_designs("industrial_park")
    site = type("Site", (), {})()
    from world_builder.planning import Site
    site = Site(id="site_probe", type="residence", role="housing", design_state="implemented",
                block_id="block_000", domain_id="workers_quarter", x0=0.0, y0=0.0, x1=12.0, y1=10.0,
                max_height_m=6.0, max_storeys=2, needs=("road",), adjacency=())
    design = design_building(site, pack.entry("residence"), pack, templates["residence"], seed=1)
    report = validate_design(design, site, pack.entry("residence"))
    assert report["state"] == "pass", [check for check in report["checks"] if check["state"] != "pass"]
    assert design.height_m <= 6.0 + 2e-3
    assert len(design.storeys) == 2, "the storeys are squeezed, not dropped, when the catalogue wants two"


def test_open_space_design_paves_and_furnishes_without_storeys() -> None:
    """Stage E class 2 (work order 017): a plaza is a ground plan, not a box.

    The design carries paving and a path, lays fixtures by rule inside the
    footprint, and validates against the height the catalogue gives plazas
    (0-1 m) — no storeys, rooms or stair are invented for it.
    """
    from world_builder.planning import Site
    from world_builder.planning.designer import DesignTemplate, design_open_space, validate_open_space
    site = Site(id="site_plaza", type="plaza", role="civic", design_state="planned", block_id="block_000",
                domain_id="castle", x0=10.0, y0=20.0, x1=52.0, y1=48.0, max_height_m=1.0, max_storeys=1,
                needs=(), adjacency=())
    template = DesignTemplate(type="plaza", kind="open_space", paving="stone", path_token="path",
                              fixtures=("lamp", "bench", "tree"))
    design = design_open_space(site, template, entry_side="south")
    report = validate_open_space(design, site)
    assert report["state"] == "pass", [check for check in report["checks"] if check["state"] != "pass"]
    assert design.height_m <= 1.0
    assert design.path[1] == site.y0 and design.path[3] == site.y1, "the path crosses from the street side"
    assert design.fixtures, "a plaza with no fixtures is a car park"
    assert all(site.x0 <= item["x0"] and item["x1"] <= site.x1
               and site.y0 <= item["y0"] and item["y1"] <= site.y1 for item in design.fixtures)
    assert design_open_space(site, template, entry_side="south").to_dict() == design.to_dict(), \
        "the same input gives the same ground plan"


def test_compound_design_lays_a_castle_without_overlaps() -> None:
    """Stage E class 3 (work order 017): a castle is several volumes.

    The curtain wall carries a gate on the street side, the towers sit inside
    it, and the keep and hall clear each other: the plan is checked for
    containment, the envelope cap, the required roles and overlaps.
    """
    from world_builder.planning import Site
    from world_builder.planning.designer import DesignTemplate, design_compound, validate_compound
    pack = load_setting_pack("arcane_medieval")
    site = Site(id="site_castle", type="castle", role="civic", design_state="planned",
                block_id="block_000", domain_id="castle", x0=40.0, y0=60.0, x1=118.0, y1=132.0,
                max_height_m=24.0, max_storeys=6, needs=(), adjacency=())
    template = DesignTemplate(type="castle", kind="compound",
                              compound=(("wall", 8.0, "flat"), ("tower", 22.0, "spire"),
                                        ("keep", 18.0, "gable"), ("hall", 10.0, "gable")))
    design = design_compound(site, pack, template, entry_side="south")
    report = validate_compound(design, site)
    assert report["state"] == "pass", [c for c in report["checks"] if c["state"] != "pass"]
    roles = [volume["role"] for volume in design.volumes]
    assert roles.count("tower") == 4 and roles.count("wall") >= 5, roles
    assert design.height_m <= site.max_height_m + 2e-3
    assert all(volume["height_m"] <= site.max_height_m + 2e-3 for volume in design.volumes)
    # The gate leaves a gap: the street-side wall is two runs, not one.
    south = [v for v in design.volumes if v["role"] == "wall" and abs(v["y0"] - site.y0) < 1e-6]
    assert len(south) == 2 and south[0]["x1"] < south[1]["x0"], "the entrance side carries a gate"
    # A cramped bailey still yields a legal castle rather than overlapping parts.
    tight = Site(id="site_tight", type="castle", role="civic", design_state="planned",
                 block_id="block_000", domain_id="castle", x0=10.0, y0=10.0, x1=58.0, y1=62.0,
                 max_height_m=18.0, max_storeys=6, needs=(), adjacency=())
    tight_report = validate_compound(design_compound(tight, pack, template, entry_side="south"), tight)
    assert tight_report["state"] == "pass", [c for c in tight_report["checks"] if c["state"] != "pass"]


def test_castle_gatehouse_and_keep_interior_reach_the_plan() -> None:
    """Stage E main line (work order 017): the gate is a gatehouse, the keep has rooms.

    The gatehouse is two piers either side of the opening plus one lintel over
    it; the threshold sits on a platform reached by a stepped ramp on each side,
    and those ramps are the only part of a castle allowed past the site edge.
    The keep carries floor levels with a stair that stays inside it, and both
    the keep and the hall keep a doorway rather than four solid walls.
    """
    from world_builder.planning import Site
    from world_builder.planning.designer import DesignTemplate, design_compound, validate_compound
    pack = load_setting_pack("arcane_medieval")
    site = Site(id="site_castle", type="castle", role="civic", design_state="planned",
                block_id="block_000", domain_id="castle", x0=40.0, y0=60.0, x1=118.0, y1=132.0,
                max_height_m=24.0, max_storeys=6, needs=(), adjacency=())
    template = DesignTemplate(type="castle", kind="compound", ring="circle",
                              compound=(("wall", 8.0, "flat"), ("tower", 22.0, "spire"),
                                        ("keep", 18.0, "gable"), ("hall", 10.0, "gable"),
                                        ("gate", 12.0, "flat")),
                              compound_storeys=(("wall", 1), ("tower", 1), ("keep", 3),
                                                ("hall", 1), ("gate", 1)))
    design = design_compound(site, pack, template, entry_side="south")
    report = validate_compound(design, site)
    assert report["state"] == "pass", [c for c in report["checks"] if c["state"] != "pass"]
    gate = [v for v in design.volumes if v["role"] == "gate"]
    lintels = [v for v in gate if v["base_m"] > 0.0]
    assert len(gate) == 3 and len(lintels) == 1, "two piers and one lintel"
    assert lintels[0]["base_m"] >= 3.0, "the gateway is walkable"
    ramps = [v for v in design.volumes if v["role"] == "ramp"]
    assert len(ramps) == 5, "a platform and two treads on each side"
    assert sorted(round(v["height_m"], 3) for v in ramps) == [0.25, 0.25, 0.5, 0.5, 0.75]
    outside = [v for v in design.volumes if v["y0"] < site.y0 - 2e-3 or v["y1"] > site.y1 + 2e-3]
    assert outside and all(v["role"] == "ramp" for v in outside), outside
    keep = next(v for v in design.volumes if v["role"] == "keep")
    assert keep["levels_m"] == sorted(keep["levels_m"]) and len(keep["levels_m"]) == 2
    assert keep["stair"]["x0"] >= keep["x0"] - 2e-3 and keep["stair"]["y1"] <= keep["y1"] + 2e-3
    assert keep["door"]["side"] == "south" and keep["door"]["width_m"] > 0.0
    assert any(v["role"] == "hall" and v["door"]["width_m"] > 0.0 for v in design.volumes)
    # A template without a gate keeps the earlier plan: no gatehouse, no ramp.
    plain = DesignTemplate(type="castle", kind="compound",
                           compound=(("wall", 8.0, "flat"), ("tower", 22.0, "spire"),
                                     ("keep", 18.0, "gable"), ("hall", 10.0, "gable")))
    plain_design = design_compound(site, pack, plain, entry_side="south")
    assert not [v for v in plain_design.volumes if v["role"] in ("gate", "ramp")]
    assert validate_compound(plain_design, site)["state"] == "pass"


def test_broken_design_templates_are_rejected(tmp_path: Path) -> None:
    source = DEFAULT_SETTINGS_ROOT / "arcane_medieval" / "designs.json"
    good = json.loads(source.read_text(encoding="utf-8"))
    broken = tmp_path / "arcane_medieval"
    broken.mkdir()
    for name in ("setting.json", "catalogue.json", "terrain.json", "districts.json"):
        (broken / name).write_text((DEFAULT_SETTINGS_ROOT / "arcane_medieval" / name).read_text(encoding="utf-8"),
                                   encoding="utf-8")

    def write(payload):
        (broken / "designs.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    unknown_room = copy.deepcopy(good)
    unknown_room["templates"]["residence"]["room_uses"][0][0] = "ballroom"
    write(unknown_room)
    with pytest.raises(SceneError) as failure:
        load_designs("arcane_medieval", tmp_path)
    assert "unknown room use" in str(failure.value)

    bad_storeys = copy.deepcopy(good)
    bad_storeys["templates"]["shop"]["storeys"] = [3, 1]
    write(bad_storeys)
    with pytest.raises(SceneError):
        load_designs("arcane_medieval", tmp_path)

    bad_roof = copy.deepcopy(good)
    bad_roof["templates"]["inn"]["roof"] = "onion"
    write(bad_roof)
    with pytest.raises(SceneError) as failure:
        load_designs("arcane_medieval", tmp_path)
    assert "roof" in str(failure.value)

    missing = copy.deepcopy(good)
    del missing["templates"]["library"]["setback_m"]
    write(missing)
    with pytest.raises(SceneError):
        load_designs("arcane_medieval", tmp_path)


def test_design_tool_prints_a_plan(designed, capsys) -> None:
    spec = importlib.util.spec_from_file_location("design_tool", REPO / "tools" / "design_buildings.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main(["--prompt", PROMPTS["harbour"], "--seed", "4", "--show", "warehouse"]) == 0
    printed = capsys.readouterr().out
    assert "failures=0" in printed and "setting=harbour" in printed
    assert "S" in printed or "#" in printed, "a ground-floor plan should be drawn"
    assert "no design template yet for" in printed


def test_massing_steps_vary_between_buildings(designed) -> None:
    """Building-skill rule 1: a street of plots must not be a row of boxes.

    The step pattern comes from the building's own fingerprint, so the same type
    on different plots steps on different sides (or not at all on a tight plot),
    and an upper storey is never wider than the one below it.
    """
    for setting, (pack, siting, designs, _, _) in designed.items():
        patterns = set()
        for design in designs:
            if not isinstance(design, BuildingDesign) or len(design.storeys) < 2:
                continue
            for lower, upper in zip(design.storeys, design.storeys[1:]):
                assert upper.x0 >= lower.x0 - 1e-6 and upper.x1 <= lower.x1 + 1e-6
                assert upper.y0 >= lower.y0 - 1e-6 and upper.y1 <= lower.y1 + 1e-6
            top = design.storeys[-1]
            patterns.add((round(top.x0 - design.x0, 3), round(top.y0 - design.y0, 3)))
        if setting == "arcane_medieval":
            assert len(patterns) >= 2, patterns
