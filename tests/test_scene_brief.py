"""Stage A and C: scene brief and setting packs (work orders 013 and 015)."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from world_builder.generation.planner import PROGRAMMES
from world_builder.planning import (SceneError, available_settings, brief_from_dict, compile_brief,
                                    compile_brief_with_provider, load_setting_pack, FixtureBriefProvider,
                                    brief_from_response)
from world_builder.planning.catalogue import DEFAULT_SETTINGS_ROOT

EXPECTED_SETTINGS = ("arcane_medieval", "harbour", "industrial_park", "modern_metropolis")
REPO = Path(__file__).resolve().parents[1]
BRIEF_FIXTURE = REPO / "examples" / "brief_model_response.json"


@pytest.fixture(scope="module")
def packs():
    return {setting: load_setting_pack(setting) for setting in EXPECTED_SETTINGS}


def test_all_setting_packs_load_and_validate(packs) -> None:
    assert available_settings() == EXPECTED_SETTINGS
    for setting, pack in packs.items():
        assert pack.id == setting
        assert pack.entries, setting
        assert pack.required_entries, f"{setting} must require something"
        assert pack.style_profile in ("arcane_medieval", "modern_grid")
        assert pack.materials and all(pack.materials.values())
        counts = pack.summary_counts()
        assert counts["entries"] == counts["implemented"] + counts["planned"]


def test_default_prompts_match_the_frozen_scene_registry(packs) -> None:
    registry = json.loads((REPO / "benchmarks" / "scene_cases_v1.json").read_text(encoding="utf-8"))
    for setting, pack in packs.items():
        assert pack.default_prompt == registry["settings"][setting]
        assert compile_brief(pack.default_prompt, seed=4).setting == setting


def test_settings_are_actually_different_backgrounds(packs) -> None:
    """Four packs must not be the same list under four names."""
    required = {setting: {entry.type for entry in pack.required_entries} for setting, pack in packs.items()}
    assert len({frozenset(types) for types in required.values()}) == len(EXPECTED_SETTINGS)
    assert "castle" in required["arcane_medieval"]
    assert {"pier", "cargo_ship"} <= required["harbour"]
    assert {"factory_hall", "rail_line"} <= required["industrial_park"]
    assert {"skyscraper", "transit_hub", "metro_line"} <= required["modern_metropolis"]


def test_catalogues_migrate_the_existing_programmes(packs) -> None:
    """The packs are the current generator's repertoire, renamed and split.

    Every implemented entry must name a programme the generator really has, no
    programme may be claimed twice inside one pack, and between them the four
    packs must still cover every programme the pipeline could already produce.
    """
    expected = {
        "arcane_medieval": {"residence", "shop", "workshop", "library", "inn", "temple", "town_hall"},
        "modern_metropolis": {"apartment", "office", "shop", "inn", "library"},
        "industrial_park": {"residence", "office", "shop", "workshop"},
        "harbour": {"residence", "inn", "office"},
    }
    covered = set()
    for setting, pack in packs.items():
        mapped = [entry.maps_to_programme for entry in pack.implemented_entries]
        assert set(mapped) == expected[setting], setting
        assert len(mapped) == len(set(mapped)), f"{setting} maps two entries onto one programme"
        assert set(mapped) <= set(PROGRAMMES), setting
        covered |= set(mapped)
    assert covered == set(PROGRAMMES), "the migration lost a programme the generator already has"


def test_planned_entries_declare_what_is_missing(packs) -> None:
    """A type with no design must say so, and must not claim a mapping."""
    total_planned = 0
    for pack in packs.values():
        for entry in pack.planned_entries:
            total_planned += 1
            assert entry.maps_to_programme is None, entry.type
            assert entry.note.strip(), f"{pack.id}.{entry.type} needs a note saying what is missing"
    assert total_planned >= 12, "the new backgrounds are mostly not designed yet; say so"


def test_catalogue_sizes_fit_the_declared_scale(packs) -> None:
    """No required landmark may demand an implausible share of the map."""
    for setting, pack in packs.items():
        area = pack.default_scale["region_m"] ** 2
        for entry in pack.required_entries:
            if entry.footprint_m2_range is not None:
                assert entry.footprint_m2_range[1] <= area / 10, f"{setting}.{entry.type}"
            if entry.linear_m is not None:
                assert entry.linear_m[1] <= pack.default_scale["region_m"] * 8, f"{setting}.{entry.type}"


def test_compile_brief_detects_each_background_and_is_deterministic(packs) -> None:
    prompts = {
        "河谷里的魔法城邦，要有城堡和冒险者工会": "arcane_medieval",
        "现代大都市，有摩天楼、地铁枢纽和公园": "modern_metropolis",
        "忙碌的工业产业园，成片厂房和铁路": "industrial_park",
        "海运港口，码头、货轮和仓库": "harbour",
    }
    for prompt, expected in prompts.items():
        brief = compile_brief(prompt, seed=7)
        assert brief.setting == expected, prompt
        assert brief == compile_brief(prompt, seed=7), "compilation must be deterministic"
        assert brief.region_m == packs[expected].default_scale["region_m"]
        assert brief.source_prompt == prompt
        assert brief.seed == 7 and brief.model_calls == 0


def test_compile_brief_scales_with_small_and_large_wording(packs) -> None:
    small = compile_brief("一个魔法小镇，要有教堂", seed=1)
    large = compile_brief("一片魔法大区域，要有城堡", seed=1)
    assert small.region_m == 256 and large.region_m == 1024
    assert small.buildings[1] < packs["arcane_medieval"].default_scale["buildings"][1] < large.buildings[1]


def test_compile_brief_picks_requested_landmarks_and_targets(packs) -> None:
    brief = compile_brief("港口，要有灯塔和船坞，导出到 unity", seed=3)
    types = {landmark.type for landmark in brief.required_landmarks}
    assert {"lighthouse", "dry_dock"} <= types
    assert brief.targets == ("unity",)
    assert compile_brief("港口，导出到我的世界", seed=3).targets == ("minecraft",)


def test_brief_requirements_merge_background_defaults(packs) -> None:
    """A brief cannot lower what its background already requires."""
    pack = packs["harbour"]
    raw = {"brief_version": "0.1.0", "setting": "harbour", "era": "maritime_modern",
           "scale": {"region_m": 512, "buildings": [30, 80]},
           "required_landmarks": [{"type": "residence", "count": 1, "priority": "may"}],
           "targets": ["viewer"]}
    brief = brief_from_dict(raw, pack)
    merged = {landmark.type: landmark for landmark in brief.requirements(pack)}
    assert merged["residence"].priority == "must", "the background requires housing"
    assert merged["residence"].count == 6, "the larger count wins"
    assert "pier" in merged and "cargo_ship" in merged


def test_brief_rejects_unknown_landmark_and_impossible_budget(packs) -> None:
    pack = packs["arcane_medieval"]
    base = {"brief_version": "0.1.0", "setting": "arcane_medieval", "era": "high_medieval",
            "scale": {"region_m": 512, "buildings": [60, 120]}, "targets": ["minecraft"]}
    unknown = copy.deepcopy(base)
    unknown["required_landmarks"] = [{"type": "space_elevator"}]
    with pytest.raises(SceneError) as failure:
        brief_from_dict(unknown, pack)
    assert failure.value.code == "brief.unknown_landmark"

    too_many = copy.deepcopy(base)
    too_many["required_landmarks"] = [{"type": "residence", "count": 90}]
    too_many["scale"]["buildings"] = [10, 40]
    with pytest.raises(SceneError) as failure:
        brief_from_dict(too_many, pack)
    assert failure.value.code == "brief.landmark_budget"

    bad_scale = copy.deepcopy(base)
    bad_scale["required_landmarks"] = [{"type": "residence", "count": 30}]
    bad_scale["scale"]["region_m"] = 300
    with pytest.raises(SceneError) as failure:
        brief_from_dict(bad_scale, pack)
    assert failure.value.code == "brief.scale"


def test_brief_json_round_trip_and_digest(packs) -> None:
    brief = compile_brief("现代大都市，要有写字楼和地铁", seed=11)
    again = brief_from_dict(json.loads(json.dumps(brief.to_dict())), packs["modern_metropolis"])
    assert again == brief
    assert brief.digest() == again.digest()
    assert brief.digest().startswith("sha256:")


def test_broken_packs_are_rejected(tmp_path: Path) -> None:
    """A typo in a pack must fail loudly, never silently do nothing."""
    source = DEFAULT_SETTINGS_ROOT / "arcane_medieval"
    broken = tmp_path / "broken_setting"
    broken.mkdir()
    setting = json.loads((source / "setting.json").read_text(encoding="utf-8"))
    setting["id"] = "broken_setting"
    (broken / "setting.json").write_text(json.dumps(setting, ensure_ascii=False), encoding="utf-8")

    catalogue = json.loads((source / "catalogue.json").read_text(encoding="utf-8"))

    def write(entries):
        (broken / "catalogue.json").write_text(
            json.dumps({"catalogue_version": "0.1.0", "setting": "broken_setting", "entries": entries},
                       ensure_ascii=False), encoding="utf-8")

    base = copy.deepcopy(catalogue["entries"][0])
    write([{**base, "role": "palace"}])
    with pytest.raises(SceneError) as failure:
        load_setting_pack("broken_setting", tmp_path)
    assert failure.value.code == "catalogue.entry"

    write([{**base, "design_state": "implemented", "maps_to_programme": None}])
    with pytest.raises(SceneError) as failure:
        load_setting_pack("broken_setting", tmp_path)
    assert "implemented designs must name maps_to_programme" in str(failure.value)

    write([{**base, "design_state": "planned", "maps_to_programme": None, "note": ""}])
    with pytest.raises(SceneError) as failure:
        load_setting_pack("broken_setting", tmp_path)
    assert "must say what is missing" in str(failure.value)

    write([{**base, "count_range": [5, 1]}])
    with pytest.raises(SceneError) as failure:
        load_setting_pack("broken_setting", tmp_path)
    assert "low <= high" in str(failure.value)

    write([{**base, "needs": ["river"]}])
    with pytest.raises(SceneError) as failure:
        load_setting_pack("broken_setting", tmp_path)
    assert "must be a site feature" in str(failure.value)

    write([{**base, "footprint_m2_range": [10, 20], "linear_m": [10, 20], "width_m_range": [1, 2]}])
    with pytest.raises(SceneError) as failure:
        load_setting_pack("broken_setting", tmp_path)
    assert "exactly one of" in str(failure.value)


def test_unknown_setting_and_typo_fields_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(SceneError) as failure:
        load_setting_pack("atlantis")
    assert failure.value.code == "setting.unknown"

    source = DEFAULT_SETTINGS_ROOT / "arcane_medieval"
    broken = tmp_path / "arcane_medieval"
    broken.mkdir()
    setting = json.loads((source / "setting.json").read_text(encoding="utf-8"))
    setting["material"] = setting.pop("materials")
    (broken / "setting.json").write_text(json.dumps(setting, ensure_ascii=False), encoding="utf-8")
    (broken / "catalogue.json").write_text((source / "catalogue.json").read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(SceneError) as failure:
        load_setting_pack("arcane_medieval", tmp_path)
    assert "unknown field" in str(failure.value) or "missing" in str(failure.value)

    setting = json.loads((source / "setting.json").read_text(encoding="utf-8"))
    setting.pop("default_prompt")
    (broken / "setting.json").write_text(json.dumps(setting, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SceneError, match="default_prompt"):
        load_setting_pack("arcane_medieval", tmp_path)


def test_fixture_model_response_runs_through_the_same_rules(packs) -> None:
    """The optional model path is a proposal: same validation, hashed provenance."""
    brief = compile_brief_with_provider("港口，黄昏时分", 5, FixtureBriefProvider(BRIEF_FIXTURE), "harbour")
    assert brief.extensions["compiled_by"] == "model"
    assert brief.extensions["provider_id"] == "fixture.local"
    assert brief.extensions["accepted_response_hash"].startswith("sha256:")
    assert brief.extensions["usage"] == {"input_tokens": 0, "output_tokens": 0}
    merged = {landmark.type: landmark for landmark in brief.requirements(packs["harbour"])}
    assert merged["residence"].count == 8, "the fixture asks for more housing than the pack minimum"
    assert merged["pier"].priority == "must", "the background still requires its piers"


def test_model_response_cannot_override_the_catalogue(packs) -> None:
    pack = packs["harbour"]
    response = json.loads(BRIEF_FIXTURE.read_text(encoding="utf-8"))

    wrong_type = copy.deepcopy(response)
    wrong_type["brief"]["required_landmarks"] = [{"type": "castle", "count": 1, "priority": "must"}]
    with pytest.raises(SceneError) as failure:
        brief_from_response(json.dumps(wrong_type).encode("utf-8"), pack)
    assert failure.value.code == "brief.unknown_landmark"

    extra_key = copy.deepcopy(response)
    extra_key["notes"] = "not part of the contract"
    with pytest.raises(SceneError) as failure:
        brief_from_response(json.dumps(extra_key).encode("utf-8"), pack)
    assert failure.value.code == "brief.response_shape"

    over_catalogue = copy.deepcopy(response)
    over_catalogue["brief"]["required_landmarks"] = [{"type": "residence", "count": 79, "priority": "must"}]
    with pytest.raises(SceneError) as failure:
        brief_from_response(json.dumps(over_catalogue).encode("utf-8"), pack)
    assert failure.value.code == "brief.landmark_count"

    # 30 homes is inside the catalogue, but with the harbour's own required
    # works the scene can no longer fit in a 30-building budget.
    oversized = copy.deepcopy(response)
    oversized["brief"]["scale"]["buildings"] = [30, 30]
    oversized["brief"]["required_landmarks"] = [{"type": "residence", "count": 30, "priority": "must"}]
    with pytest.raises(SceneError) as failure:
        brief_from_response(json.dumps(oversized).encode("utf-8"), pack)
    assert failure.value.code == "brief.landmark_budget"

    with pytest.raises(SceneError) as failure:
        brief_from_response(b"x" * (65_536 + 1), pack)
    assert failure.value.code == "brief.response_size"


def test_compile_brief_tool_reports_the_setting_and_the_gaps(tmp_path: Path, capsys) -> None:
    spec = importlib.util.spec_from_file_location("compile_brief_tool", REPO / "tools" / "compile_brief.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "brief.json"
    assert module.main(["--prompt", "港口，要有灯塔和货轮", "--seed", "9", "--output", str(output)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["setting"]["id"] == "harbour"
    assert report["brief_digest"].startswith("sha256:")
    assert {"lighthouse", "cargo_ship"} <= {item["type"] for item in report["effective_requirements"]}
    assert "dry_dock" in report["not_designed_yet"], "the harbour pack has no docking design yet"
    assert json.loads(output.read_text(encoding="utf-8")) == report["brief"]

    assert module.main(["--prompt", "河谷里的魔法城邦", "--setting", "harbour"]) == 1
    failure = json.loads(capsys.readouterr().out)
    assert failure["code"] == "brief.setting"
