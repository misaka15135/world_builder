"""Stage D: district ownership, blocks, skeleton and envelopes (work order 016)."""
from __future__ import annotations

import copy
import importlib.util
import json
import math
from pathlib import Path

import pytest

from world_builder.planning import (SceneError, compile_brief, load_districts_spec, load_setting_pack,
                                    plan_siting, plan_terrain, validate_siting)
from world_builder.planning.catalogue import DEFAULT_SETTINGS_ROOT
from world_builder.planning.siting import _mooring_rect, _rects_overlap, _work_rects

PROMPTS = {
    "arcane_medieval": "河谷里的魔法城邦，要有城堡和冒险者工会",
    "modern_metropolis": "现代大都市，有摩天楼和地铁枢纽",
    "industrial_park": "忙碌的工业产业园，成片厂房和铁路",
    "harbour": "海运港口，码头货轮和仓库",
}
REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def planned():
    result = {}
    for setting, prompt in PROMPTS.items():
        pack = load_setting_pack(setting)
        brief = compile_brief(prompt, seed=4)
        terrain = plan_terrain(setting, seed=4, region_m=512, spacing_m=8)
        plan = plan_siting(brief, pack, terrain)
        result[setting] = (pack, brief, terrain, plan, validate_siting(plan, brief, pack, terrain))
    return result


def test_district_specs_load_and_are_coherent() -> None:
    for setting in PROMPTS:
        spec = load_districts_spec(setting)
        assert spec.setting == setting
        assert spec.block_area_m2[0] < spec.block_area_m2[1]
        assert spec.target_blocks[0] <= spec.target_blocks[1]
        assert spec.uses and spec.domains
        for rules in spec.uses.values():
            assert 0 <= rules["share"][0] <= rules["share"][1] <= 1


def test_every_background_sits_within_its_rules(planned) -> None:
    for setting, (pack, brief, terrain, plan, report) in planned.items():
        failures = [check for check in report["checks"] if check["state"] != "pass"]
        assert report["state"] == "pass", (setting, failures)


def test_complete_site_envelopes_avoid_planned_water(planned) -> None:
    from world_builder.planning.siting import _footprint_is_dry

    for setting, (_, _, terrain, plan, report) in planned.items():
        assert all(_footprint_is_dry(terrain, (site.x0, site.y0, site.x1, site.y1))
                   for site in plan.sites), setting
        assert next(check for check in report["checks"]
                    if check["rule"] == "siting.site_footprints_dry")["state"] == "pass"
    arcane_terrain = planned["arcane_medieval"][2]
    assert not _footprint_is_dry(arcane_terrain, (361.157, 285.434, 376.747, 298.424))


def test_blocks_tile_the_region_and_respect_their_shares(planned) -> None:
    for setting, (pack, brief, terrain, plan, _) in planned.items():
        spec = load_districts_spec(setting)
        assert abs(sum(block.area_m2 for block in plan.blocks) - plan.region_m ** 2) < 1.0
        for index, first in enumerate(plan.blocks):
            for second in plan.blocks[index + 1:]:
                assert not (min(first.x1, second.x1) - max(first.x0, second.x0) > 0
                            and min(first.y1, second.y1) - max(first.y0, second.y0) > 0), setting
        for use, rules in spec.uses.items():
            share = sum(1 for block in plan.blocks if block.use == use) / len(plan.blocks)
            assert rules["share"][0] - 0.05 <= share <= rules["share"][1] + 0.05, (setting, use, share)


def test_ownership_covers_every_block_and_changes_the_heights(planned) -> None:
    for setting, (pack, brief, terrain, plan, report) in planned.items():
        owners = {block.domain for block in plan.blocks}
        assert owners == set(load_districts_spec(setting).domains), setting
        assert all(domain.block_ids for domain in plan.domains)
        # Several blocks under one owner is the point of the layer, and the
        # owner's factors must actually reach the envelopes.
        assert max(len(domain.block_ids) for domain in plan.domains) >= 3, setting
        applied = [check for check in report["checks"] if check["rule"] == "siting.domain_factors_applied"]
        assert applied and all(check["state"] == "pass" for check in applied), setting


def test_skeleton_is_connected_and_bridges_cross_water(planned) -> None:
    for setting, (pack, brief, terrain, plan, report) in planned.items():
        connected = next(check for check in report["checks"] if check["rule"] == "siting.network_connected")
        assert connected["state"] == "pass", setting
        assert plan.bridges, f"{setting} has water but no bridge"
        for bridge in plan.bridges:
            channel = next(channel for channel in terrain.channels if channel.id == bridge.channel_id)
            midpoint = ((bridge.start[0] + bridge.end[0]) / 2, (bridge.start[1] + bridge.end[1]) / 2)
            from world_builder.planning.terrain import _distance_to_channel
            assert _distance_to_channel(*midpoint, channel) <= channel.width_m / 2, bridge.id
        headings = plan.stats["arterial_headings_deg"]
        off_axis = [h for h in headings if min(abs(h % 90), 90 - abs(h % 90)) > 8]
        assert len(off_axis) >= 2, (setting, headings)


def test_every_demanded_building_has_an_envelope(planned) -> None:
    for setting, (pack, brief, terrain, plan, _) in planned.items():
        for requirement in brief.requirements(pack):
            entry = pack.entry(requirement.type)
            if entry.footprint_kind == "linear" or entry.role == "vessel":
                assert len([work for work in plan.works if work.type == requirement.type]) >= requirement.count, \
                    (setting, requirement.type)
                continue
            sites = plan.sites_of(requirement.type)
            assert len(sites) >= requirement.count, (setting, requirement.type, len(sites))
            for site in sites:
                assert entry.footprint_m2_range[0] - 1 <= site.area_m2 <= entry.footprint_m2_range[1] + 1
                if entry.height_m_range:
                    assert entry.height_m_range[0] - 0.5 <= site.max_height_m <= entry.height_m_range[1] + 0.5
                assert site.max_storeys >= 1


def test_a_ship_is_moored_clear_of_the_berths(planned) -> None:
    """Work order 016/017: a hull must not be parked through a pier.

    The first vessel in this project was moored by taking the nearest water to a
    harbour block and lying parallel to the shore, which ran the hull straight
    across the piers that jut out from that shore (measured 2026-09-28: a 6 x 14
    m overlap at the pier head). A berth is searched for instead: the hull is
    stepped away from the quay and along it until it clears every work already
    sited, and its whole waterline has to be on water.
    """
    pack, brief, terrain, plan, _ = planned["harbour"]
    berths = [rect for work in plan.works if work.type in {"pier", "quay_wall"}
              for rect in _work_rects(work.points, work.width_m)]
    assert berths, "the harbour sites piers to moor against"
    ships = [work for work in plan.works if work.type == "cargo_ship"]
    assert ships, "the harbour brief demands vessels"
    for ship in ships:
        along = math.atan2(ship.points[-1][1] - ship.points[0][1], ship.points[-1][0] - ship.points[0][0])
        centre = ((ship.points[0][0] + ship.points[-1][0]) / 2,
                  (ship.points[0][1] + ship.points[-1][1]) / 2)
        hull = _mooring_rect(centre, along, math.dist(ship.points[0], ship.points[-1]), ship.width_m)
        assert not [rect for rect in berths if _rects_overlap(hull, rect)], \
            "the hull clears every pier and quay"
        waterline = [(centre[0] + math.cos(along) * step * ship.length_m / 2,
                      centre[1] + math.sin(along) * step * ship.length_m / 2)
                     for step in (-1, -0.5, 0, 0.5, 1)]
        assert all(terrain.water_at(*point) for point in waterline), "the hull is afloat, not aground"


def test_linear_works_and_vessels_are_corridors_not_plots(planned) -> None:
    pack, brief, terrain, plan, _ = planned["harbour"]
    assert {work.type for work in plan.works} >= {"pier", "quay_wall", "cargo_ship"}
    for work in plan.works:
        assert len(work.points) >= 2 and work.length_m > 0
        if work.type == "cargo_ship":
            midpoint = ((work.points[0][0] + work.points[-1][0]) / 2,
                        (work.points[0][1] + work.points[-1][1]) / 2)
            assert terrain.water_at(*midpoint), "a ship belongs in the water"
    assert not plan.sites_of("cargo_ship"), "a ship is not a plot"
    arcane = planned["arcane_medieval"][3]
    assert any(work.type == "city_wall" for work in arcane.works), "the arcane pack demands a wall"


def test_plans_are_deterministic() -> None:
    pack = load_setting_pack("harbour")
    brief = compile_brief(PROMPTS["harbour"], seed=7)
    terrain = plan_terrain("harbour", seed=7, region_m=512, spacing_m=8)
    first = plan_siting(brief, pack, terrain)
    second = plan_siting(brief, pack, terrain)
    assert first.to_dict() == second.to_dict()


def test_broken_district_specs_are_rejected(tmp_path: Path) -> None:
    source = DEFAULT_SETTINGS_ROOT / "arcane_medieval" / "districts.json"
    good = json.loads(source.read_text(encoding="utf-8"))
    setting = json.loads((DEFAULT_SETTINGS_ROOT / "arcane_medieval" / "setting.json").read_text(encoding="utf-8"))
    catalogues = {
        name: (DEFAULT_SETTINGS_ROOT / name / "catalogue.json").read_text(encoding="utf-8")
        for name in ("arcane_medieval",)}
    broken = tmp_path / "arcane_medieval"
    broken.mkdir()
    (broken / "setting.json").write_text(json.dumps(setting, ensure_ascii=False), encoding="utf-8")
    (broken / "catalogue.json").write_text(catalogues["arcane_medieval"], encoding="utf-8")
    (broken / "terrain.json").write_text(
        (DEFAULT_SETTINGS_ROOT / "arcane_medieval" / "terrain.json").read_text(encoding="utf-8"), encoding="utf-8")

    def write(payload):
        (broken / "districts.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    bad_prefers = copy.deepcopy(good)
    bad_prefers["domains"]["castle"]["prefers"] = ["spaceport"]
    write(bad_prefers)
    with pytest.raises(SceneError) as failure:
        load_districts_spec("arcane_medieval", tmp_path)
    assert "unknown use" in str(failure.value)

    bad_share = copy.deepcopy(good)
    bad_share["uses"]["residential"]["share"] = [0.9, 0.95]
    write(bad_share)
    with pytest.raises(SceneError) as failure:
        load_districts_spec("arcane_medieval", tmp_path)
    assert "sum to" in str(failure.value)

    unknown_field = copy.deepcopy(good)
    unknown_field["uses"]["market"]["density"] = 2
    write(unknown_field)
    with pytest.raises(SceneError):
        load_districts_spec("arcane_medieval", tmp_path)

    wrong_setting = copy.deepcopy(good)
    wrong_setting["setting"] = "harbour"
    write(wrong_setting)
    with pytest.raises(SceneError) as failure:
        load_districts_spec("arcane_medieval", tmp_path)
    assert "harbour" in str(failure.value)


def test_district_tool_prints_a_map_and_passes(planned, tmp_path: Path, capsys) -> None:
    spec = importlib.util.spec_from_file_location("plan_districts_tool", REPO / "tools" / "plan_districts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "districts.json"
    assert module.main(["--prompt", PROMPTS["harbour"], "--seed", "4", "--output", str(output)]) == 0
    printed = capsys.readouterr().out
    assert "validation: pass" in printed and "setting=harbour" in printed
    assert "#" in printed or "*" in printed, "the block map should be drawn"
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["setting"] == "harbour" and payload["blocks"] and payload["sites"]
    assert payload["stats"]["blocks"] == len(payload["blocks"])
    assert math.isclose(sum(block["area_m2"] for block in payload["blocks"]), 512 * 512, rel_tol=0.01)


def test_arcane_paving_and_housing_stay_in_ratio(planned) -> None:
    """Pin the 2026-09-27 density pass (work order 016).

    Before it the arcane network was 19.4 km of street — about 97,000 m² of
    carriageway for 35 sites — and the pasted world read as a stone plaza; the
    city.7 reference scene, which reads as a town, paved 24,336 m² for 80
    buildings. The bounds below sit between the two and fail loudly if the
    connectors go back to reaching across the map.
    """
    _pack, _brief, _terrain, plan, _report = planned["arcane_medieval"]
    streets = [road for road in plan.roads if road.kind in {"arterial", "local", "quay"}]
    carriageway = sum(road.length_m * road.width_m for road in streets)
    assert len(plan.sites) >= 70, len(plan.sites)
    assert sum(1 for site in plan.sites if site.role == "housing") >= 50
    assert sum(road.length_m for road in streets) <= 14_000
    assert carriageway <= 60_000, carriageway
