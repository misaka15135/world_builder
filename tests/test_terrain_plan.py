"""Stage B: terrain plans (work order 014)."""
from __future__ import annotations

import copy
import dataclasses
import importlib.util
import json
from pathlib import Path

import pytest

from world_builder.planning import (SceneError, load_terrain_spec, plan_terrain, render_preview, validate_terrain)
from world_builder.planning.catalogue import DEFAULT_SETTINGS_ROOT

SETTINGS = ("arcane_medieval", "harbour", "industrial_park", "modern_metropolis")
SEED = 4
REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def plans():
    return {setting: plan_terrain(setting, seed=SEED, region_m=512, spacing_m=8) for setting in SETTINGS}


def test_terrain_specs_load_and_are_coherent(packs_unused=None) -> None:
    kinds = {}
    for setting in SETTINGS:
        spec = load_terrain_spec(setting)
        kinds[setting] = spec.water_kind
        assert spec.min_m < spec.max_m
        assert spec.water_fraction[0] < spec.water_fraction[1]
        assert spec.width_m[0] <= spec.width_m[1]
        assert spec.coast == (spec.water_kind == "coast")
    assert kinds["harbour"] == "coast" and kinds["arcane_medieval"] == "river"
    assert kinds["modern_metropolis"] == kinds["industrial_park"] == "canal"


def test_every_background_plan_matches_its_spec(plans) -> None:
    for setting, plan in plans.items():
        report = validate_terrain(plan, load_terrain_spec(setting))
        failures = [check for check in report["checks"] if check["state"] != "pass"]
        assert report["state"] == "pass", (setting, failures)


def test_plans_are_deterministic() -> None:
    first = plan_terrain("arcane_medieval", seed=11, region_m=512, spacing_m=8)
    second = plan_terrain("arcane_medieval", seed=11, region_m=512, spacing_m=8)
    assert first.heights == second.heights
    assert first.channels == second.channels
    assert first.stats == second.stats
    assert first.reserved == second.reserved
    other = plan_terrain("arcane_medieval", seed=12, region_m=512, spacing_m=8)
    assert other.stats != first.stats, "a different seed should be a different landscape"


def test_samples_agree_with_the_stored_grid(plans) -> None:
    plan = plans["arcane_medieval"]
    for ix in (0, 7, plan.columns - 1):
        for iy in (0, 5, plan.rows - 1):
            assert plan.height_at(ix * plan.spacing_m, iy * plan.spacing_m) == pytest.approx(plan.heights[iy][ix])
    channel = plan.channels[0]
    mid = channel.points[len(channel.points) // 2]
    assert plan.water_at(*mid), "a channel centre is water"
    assert plan.buildable_at(*mid) == 0.0, "water is not buildable"
    far = next((x, y) for x in range(0, 512, 8) for y in range(0, 512, 8)
               if not plan.water_at(x, y) and plan.buildable_at(x, y) > 0.5)
    assert plan.distance_to_water_m(*far) > 0


def test_backgrounds_produce_different_landscapes(plans) -> None:
    stats = {setting: plan.stats for setting, plan in plans.items()}
    assert stats["harbour"]["water_fraction"] > 0.25, "a harbour is mostly water"
    assert stats["industrial_park"]["water_fraction"] < 0.10, "a works site has a canal, not a sea"
    assert stats["arcane_medieval"]["mean_slope_deg"] > stats["modern_metropolis"]["mean_slope_deg"]
    assert stats["modern_metropolis"]["max_m"] < stats["arcane_medieval"]["max_m"]
    assert any(channel.kind == "tributary" for channel in plans["arcane_medieval"].channels), \
        "the arcane valley should have tributaries"
    assert any(channel.kind == "coast" for channel in plans["harbour"].channels)
    # Channels meander rather than run straight: the arcane main course is
    # longer than the distance between its own ends.
    channel = plans["arcane_medieval"].channels[0]
    straight = ((channel.points[0][0] - channel.points[-1][0]) ** 2
                + (channel.points[0][1] - channel.points[-1][1]) ** 2) ** 0.5
    assert channel.length_m > straight * 1.2, "a river should not be a ruler line"


def test_validator_catches_a_raised_bed_and_a_ridge(plans) -> None:
    plan = plans["arcane_medieval"]
    spec = load_terrain_spec("arcane_medieval")
    channel = next(channel for channel in plan.channels if channel.kind != "coast")

    def bed_cells(target):
        return [(min(max(round(y / plan.spacing_m), 0), plan.rows - 1),
                 min(max(round(x / plan.spacing_m), 0), plan.columns - 1)) for x, y in target.points]

    cells = bed_cells(channel)
    raised = [list(row) for row in plan.heights]
    iy, ix = cells[len(cells) // 2]
    raised[iy][ix] += 5.0
    report = validate_terrain(dataclasses.replace(plan, heights=tuple(tuple(row) for row in raised)), spec)
    assert any(check["rule"] == "terrain.flow_downhill" and check["state"] == "fail" for check in report["checks"])

    # The same cell turned into a high point: the water would sit on a ridge.
    ridge = [list(row) for row in plan.heights]
    neighbours = [ridge[iy + oy][ix + ox] for oy, ox in ((1, 0), (-1, 0), (0, 1), (0, -1))
                  if 0 <= iy + oy < plan.rows and 0 <= ix + ox < plan.columns]
    ridge[iy][ix] = max(neighbours) + 3.0
    report = validate_terrain(dataclasses.replace(plan, heights=tuple(tuple(row) for row in ridge)), spec)
    assert any(check["rule"] == "terrain.water_in_valley" and check["state"] == "fail" for check in report["checks"])


def test_broken_terrain_specs_are_rejected(tmp_path: Path) -> None:
    source = DEFAULT_SETTINGS_ROOT / "arcane_medieval" / "terrain.json"
    good = json.loads(source.read_text(encoding="utf-8"))
    broken = tmp_path / "arcane_medieval"
    broken.mkdir()
    (broken / "catalogue.json").write_text(
        (DEFAULT_SETTINGS_ROOT / "arcane_medieval" / "catalogue.json").read_text(encoding="utf-8"), encoding="utf-8")
    setting = json.loads((DEFAULT_SETTINGS_ROOT / "arcane_medieval" / "setting.json").read_text(encoding="utf-8"))
    (broken / "setting.json").write_text(json.dumps(setting, ensure_ascii=False), encoding="utf-8")

    def write(payload):
        (broken / "terrain.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    write({**good, "relief": {**good["relief"], "roughness": "alpine"}})
    with pytest.raises(SceneError) as failure:
        load_terrain_spec("arcane_medieval", tmp_path)
    assert "roughness" in str(failure.value)

    write({**good, "water": {k: v for k, v in good["water"].items() if k != "width_m"}})
    with pytest.raises(SceneError) as failure:
        load_terrain_spec("arcane_medieval", tmp_path)
    assert "width_m" in str(failure.value)

    write({**good, "water": {**good["water"], "fraction": [0.4, 0.2]}})
    with pytest.raises(SceneError) as failure:
        load_terrain_spec("arcane_medieval", tmp_path)
    assert "low <= high" in str(failure.value)

    write({**good, "slope": {"max_deg": 5, "mean_deg": [1, 9]}})
    with pytest.raises(SceneError) as failure:
        load_terrain_spec("arcane_medieval", tmp_path)
    assert "must not exceed" in str(failure.value)

    write({**good, "setting": "harbour"})
    with pytest.raises(SceneError) as failure:
        load_terrain_spec("arcane_medieval", tmp_path)
    assert "harbour" in str(failure.value)


def test_preview_and_tool_report_a_usable_map(plans, tmp_path: Path, capsys) -> None:
    plan = plans["industrial_park"]
    preview = render_preview(plan, width=48)
    lines = preview.splitlines()
    assert len(lines) > 5 and all(len(line) > 5 for line in lines)
    assert "~" in preview, "the canal should be visible in the preview"

    spec = importlib.util.spec_from_file_location("plan_terrain_tool", REPO / "tools" / "plan_terrain.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "terrain.json"
    assert module.main(["--setting", "harbour", "--seed", "4", "--spacing-m", "8", "--output", str(output)]) == 0
    printed = capsys.readouterr().out
    assert "setting=harbour" in printed and "validation: pass" in printed
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["setting"] == "harbour" and payload["stats"]["water_fraction"] > 0.25
    assert len(payload["heights_m"]) == payload["heights_m"].__len__() > 5

    assert module.main(["--setting", "atlantis"]) == 1
    failure = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert failure["code"] == "terrain.spec_missing"
