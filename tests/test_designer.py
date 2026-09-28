"""Stage E: single building designs (work order 017)."""
from __future__ import annotations

import copy
import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import pytest

from world_builder.planning import (BuildingDesign, CompoundDesign, CylinderDesign, DockDesign,
                                    OpenSpaceDesign, SceneError, compile_brief, load_designs,
                                    load_setting_pack, plan_siting, plan_terrain, validate_compound,
                                    validate_cylinder, validate_design, validate_dock, validate_open_space)
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
            elif isinstance(plan, CylinderDesign):
                reports.append(validate_cylinder(plan, site))
            elif isinstance(plan, DockDesign):
                reports.append(validate_dock(plan, site))
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
            if template.kind == "cylinders":
                assert template.vessel_diameter_m and template.vessel_height_m
                assert template.vessel_count and template.vessel_roof in ("flat", "dome")
                continue
            if template.kind == "dock":
                assert template.basin_depth_m and template.basin_margin_m
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


def test_a_dry_dock_cuts_a_basin_inside_its_plot() -> None:
    """Work order 017 class 3: the harbour's last missing type.

    The basin is the plot minus a working margin, its floor sits `depth_m` below
    grade, and the gate goes on the face the vessel enters from. A plot with no
    room around the basin is refused, so the scoped feedback can drop that one
    plot instead of cutting a trench through the quay.
    """
    from world_builder.planning import Site
    from world_builder.planning.designer import DesignTemplate, design_dock, validate_dock
    pack = load_setting_pack("harbour")
    template = DesignTemplate(type="dry_dock", kind="dock", basin_depth_m=5.0, basin_margin_m=6.0)
    site = Site(id="site_dock", type="dry_dock", role="infrastructure", design_state="planned",
                block_id="block_000", domain_id="port_authority", x0=100.0, y0=200.0, x1=181.2, y1=267.7,
                max_height_m=14.4, max_storeys=1, needs=("water",), adjacency=())
    design = design_dock(site, pack, template, entry_side="north")
    report = validate_dock(design, site)
    assert report["state"] == "pass", [c for c in report["checks"] if c["state"] != "pass"]
    assert (design.x0, design.y0) == (106.0, 206.0) and (design.x1, design.y1) == (175.2, 261.7)
    assert design.depth_m == 5.0 and design.gate_side == "north"
    assert design.gantry_height_m >= 6.0
    tight = replace(site, x1=site.x0 + 14.0, y1=site.y0 + 14.0)
    with pytest.raises(SceneError) as raised:
        design_dock(tight, pack, template, entry_side="north")
    assert raised.value.code == "design.envelope"


def test_a_plot_that_cannot_hold_the_plan_is_refused() -> None:
    """Work order 018: the design stage refuses an impossible envelope.

    A 1x1 m plot used to "design" successfully with rooms of negative width, and
    a plot too flat for the minimum storey plus its roof produced a building
    taller than its envelope. Neither raised, so the scoped failure feedback had
    nothing to catch. Both now raise `design.envelope` -- which is what makes the
    per-plot retry meaningful rather than decorative.
    """
    from world_builder.planning import Site
    from world_builder.planning.designer import design as design_one
    pack = load_setting_pack("industrial_park")
    template = load_designs("industrial_park")["workshop"]

    def attempt(width: float, depth: float, height: float):
        site = Site(id="site_probe", type="workshop", role="works", design_state="planned",
                    block_id="block_000", domain_id="works", x0=0.0, y0=0.0, x1=width, y1=depth,
                    max_height_m=height, max_storeys=2, needs=(), adjacency=())
        return design_one(site, pack.entry("workshop"), pack, template, entry_side="south", seed=4)

    for width, depth in ((1.0, 1.0), (2.0, 2.0), (6.0, 4.0)):
        with pytest.raises(SceneError) as raised:
            attempt(width, depth, 12.0)
        assert raised.value.code == "design.envelope", (width, depth)
    with pytest.raises(SceneError) as raised:
        attempt(20.0, 20.0, 1.0)
    assert raised.value.code == "design.envelope", "a plot too flat for a storey is refused"
    roomy = attempt(20.0, 20.0, 12.0)
    assert roomy.storeys and roomy.height_m <= 12.0 + 1e-6


def test_design_tool_reads_setting_and_prompt_the_same_way(tmp_path: Path) -> None:
    """Work order 016: one input convention across the tools.

    `design_buildings.py` used to synthesise a "<setting> scene" prompt for
    `--setting`, so the same setting designed 13 harbour plots through this tool
    and 14 through `assemble_scene.py`. `--setting` now means the setting's own
    registered prompt in both.
    """
    spec = importlib.util.spec_from_file_location("design_tool_parity",
                                                  REPO / "tools" / "design_buildings.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    by_setting, by_prompt = tmp_path / "setting.json", tmp_path / "prompt.json"
    assert module.main(["--setting", "harbour", "--seed", "4", "--output", str(by_setting)]) == 0
    assert module.main(["--prompt", PROMPTS["harbour"], "--seed", "4", "--output", str(by_prompt)]) == 0
    setting_doc = json.loads(by_setting.read_text(encoding="utf-8"))
    prompt_doc = json.loads(by_prompt.read_text(encoding="utf-8"))
    assert setting_doc["designs"] and setting_doc["designs"] == prompt_doc["designs"]


def test_one_bad_plot_does_not_take_the_scene_down() -> None:
    """Work order 018: failure is scoped to the plot that failed.

    A building that cannot be designed on its envelope is re-fitted on the same
    envelope first, and only dropped -- with the reason recorded -- if that fails
    too. The other plots are designed exactly as before, so one bad plot costs
    one building instead of the whole city.
    """
    from types import SimpleNamespace
    from world_builder.planning import Site, design_sites
    pack = load_setting_pack("industrial_park")
    templates = load_designs("industrial_park")
    block = SimpleNamespace(centre=(0.0, 0.0))
    good = Site(id="site_ok", type="workshop", role="works", design_state="planned",
                block_id="block_000", domain_id="works", x0=0.0, y0=0.0, x1=40.0, y1=30.0,
                max_height_m=12.0, max_storeys=2, needs=(), adjacency=())
    # A plot too small for the vessels the template demands: the design rule
    # refuses rather than shrinking a silo into a pipe (design.no_fit).
    hopeless = Site(id="site_bad", type="silo_tank", role="works", design_state="planned",
                    block_id="block_000", domain_id="works", x0=100.0, y0=100.0, x1=106.0, y1=106.0,
                    max_height_m=12.0, max_storeys=2, needs=(), adjacency=())
    unknown = Site(id="site_unknown", type="no_such_type", role="works", design_state="planned",
                   block_id="block_000", domain_id="works", x0=200.0, y0=200.0, x1=230.0, y1=220.0,
                   max_height_m=12.0, max_storeys=2, needs=(), adjacency=())
    siting = SimpleNamespace(sites=(good, hopeless, unknown), block=lambda _: block)
    designs, failures, skipped = design_sites(siting, pack, templates, seed=4)
    assert [design.site_id for design in designs] == ["site_ok"], "the good plot is designed"
    assert [item["site_id"] for item in failures] == ["site_bad"], "the bad plot is dropped, with its reason"
    assert failures[0]["code"] == "design.no_fit" and failures[0]["attempts"] == 3
    assert failures[0]["shrink"] == 0.20, "the scoped retry re-fits the same envelope"
    assert skipped == {"no_such_type"}, "a missing template is reported separately"


def test_cylinder_design_lays_a_tank_farm_without_overlap() -> None:
    """Stage E class 3 (work order 017 main line): the first round geometry.

    A tank farm states one vessel; the rule decides how many fit. A roomy plot
    keeps the template's diameter; a narrow one keeps the vessels round by
    standing fewer of them rather than squeezing them into pipes.
    """
    from world_builder.planning import Site
    from world_builder.planning.designer import DesignTemplate, design_cylinders, validate_cylinder
    pack = load_setting_pack("industrial_park")
    template = DesignTemplate(type="silo_tank", kind="cylinders", vessel_diameter_m=10.0,
                              vessel_height_m=22.0, vessel_count=4, vessel_roof="dome")
    site = Site(id="site_tank", type="silo_tank", role="works", design_state="planned",
                block_id="block_000", domain_id="tank", x0=0.0, y0=0.0, x1=40.0, y1=30.0,
                max_height_m=24.0, max_storeys=1, needs=(), adjacency=())
    plan = design_cylinders(site, pack, template)
    report = validate_cylinder(plan, site)
    assert report["state"] == "pass", [c for c in report["checks"] if c["state"] != "pass"]
    assert len(plan.barrels) == 4, "a roomy plot takes every vessel"
    assert all(abs(barrel["radius_m"] - 5.0) < 1e-6 for barrel in plan.barrels)
    assert plan.height_m == 22.0 and {b["roof"] for b in plan.barrels} == {"dome"}
    narrow = Site(id="site_tight", type="silo_tank", role="works", design_state="planned",
                  block_id="block_000", domain_id="tank", x0=0.0, y0=0.0, x1=14.0, y1=12.0,
                  max_height_m=20.0, max_storeys=1, needs=(), adjacency=())
    tight = design_cylinders(narrow, pack, template)
    assert len(tight.barrels) < 4, "a narrow plot drops vessels instead of fattening pipes"
    assert all(barrel["radius_m"] >= 2.0 for barrel in tight.barrels)
    assert validate_cylinder(tight, narrow)["state"] == "pass"
    assert tight.height_m == 20.0, "the vessel is capped by the plot's envelope"


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
    # The harbour used to report `no design template yet for: ['dry_dock']`; the
    # dry dock now has a design, so every sited type is designed (2026-09-28).
    assert "no design template yet for" not in printed
    assert "'dry_dock': 1" in printed, "the dry dock is designed rather than missing"


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
