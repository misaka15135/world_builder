from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from world_builder.generation.planner import STAGES, initial_records, plan_stage
from world_builder.generation.spec import CitySpec, PilotSpec
from world_builder.generation.validation import check_geometry


def test_city_contract_is_distinct_from_historical_pilot():
    pilot = PilotSpec(seed=101)
    city = CitySpec(seed=101)
    assert pilot.generator_version == "0.1.0-pilot.3"
    assert pilot.to_dict().get("region_size_m") is None
    assert city.generator_version == "0.1.0-city.4"
    assert city.interior_count == 80
    assert city.world_id != pilot.world_id
    with pytest.raises(ValueError, match="008/009"):
        PilotSpec(building_count=80)
    with pytest.raises(ValueError, match="80"):
        CitySpec(building_count=79)


@pytest.mark.parametrize("scenario", ["riverside", "hillside", "dense"])
def test_city_layout_and_overlap_rule(scenario):
    spec = CitySpec(scenario=scenario)
    records = initial_records(spec)
    for stage in STAGES[:4]:
        additions, _ = plan_stage(spec, stage, records)
        records.extend(additions)
        next(r for r in records if r["record_type"] == "world_spec")["extensions"]["stage"] = stage
        assert not [c for c in check_geometry(records) if c["severity"] == "hard" and c["state"] == "fail"]
    buildings = [r for r in records if r.get("kind") == "building"]
    assert len(buildings) == 80
    assert len([r for r in records if r.get("kind") == "district"]) == 3
    assert len([r for r in records if r.get("kind") == "bridge"]) == 1
    damaged = copy.deepcopy(records)
    first = next(r for r in damaged if r["id"] == "building_000")
    second = next(r for r in damaged if r["id"] == "building_001")
    second["bounds"] = copy.deepcopy(first["bounds"])
    assert any(c["rule"] == "pilot.building_overlap" and c["state"] == "fail"
               for c in check_geometry(damaged))


def test_city_batch_registrations_are_fixed_before_results():
    root = Path(__file__).resolve().parents[1] / "benchmarks"
    history = json.loads((root / "city_cases_v1.json").read_text(encoding="utf-8"))
    assert history["generator_version"] == "0.1.0-city.1"
    assert all(case["spec"]["interior_count"] == 5 for case in history["cases"])
    assert json.loads((root / "city_cases_v2.json").read_text(encoding="utf-8"))["generator_version"] == "0.1.0-city.2"
    assert json.loads((root / "city_cases_v3.json").read_text(encoding="utf-8"))["generator_version"] == "0.1.0-city.3"
    current = json.loads((root / "city_cases_v4.json").read_text(encoding="utf-8"))
    assert current["generator_version"] == CitySpec().generator_version
    assert len(current["cases"]) == 30
    for scenario, seed_start in (("riverside", 101), ("hillside", 201), ("dense", 301)):
        cases = [case for case in current["cases"] if case["spec"]["scenario"] == scenario]
        assert [case["spec"]["seed"] for case in cases] == list(range(seed_start, seed_start + 10))
        assert [case["spec"]["layout_profile"] for case in cases] == ["standard"] * 5 + ["compact"] * 5
        assert all(case["spec"]["building_count"] == 80 and case["spec"]["interior_count"] == 80 for case in cases)


def test_city_buildings_vary_and_carry_room_programmes():
    spec = CitySpec(seed=101)
    records = initial_records(spec)
    for stage in STAGES:
        additions, _ = plan_stage(spec, stage, records)
        records.extend(additions)
        next(r for r in records if r["record_type"] == "world_spec")["extensions"]["stage"] = stage
    buildings = [r for r in records if r.get("kind") == "building"]
    envelopes = {(r["geometry"]["size_m"][0], r["geometry"]["size_m"][1], r["attributes"]["storeys"]) for r in buildings}
    assert len(envelopes) > 3, "buildings should not all share one envelope"
    assert len({r["attributes"]["programme"] for r in buildings}) >= 3
    rooms = [r for r in records if r.get("kind") == "room"]
    assert len(rooms) == 2 * sum(r["attributes"]["storeys"] for r in buildings)
    assert all(r["attributes"].get("use") for r in rooms)
    furniture = [r for r in records if r.get("kind") == "furniture"]
    assert len(furniture) >= len(rooms)
    assert all(r["attributes"].get("use") for r in furniture)
    assert not [c for c in check_geometry(records) if c["severity"] == "hard" and c["state"] != "pass"]


def test_city_districts_drive_building_scale_and_programme():
    spec = CitySpec(seed=101)
    records = initial_records(spec)
    for stage in STAGES:
        additions, _ = plan_stage(spec, stage, records)
        records.extend(additions)
        next(r for r in records if r["record_type"] == "world_spec")["extensions"]["stage"] = stage
    districts = {r["id"]: r["attributes"]["use"] for r in records if r.get("kind") == "district"}
    parcels = {r["id"]: r["parent_id"] for r in records if r.get("kind") == "parcel"}
    heights: dict[str, list] = {}
    programmes: dict[str, list] = {}
    for building in (r for r in records if r.get("kind") == "building"):
        use = districts[parcels[building["parent_id"]]]
        heights.setdefault(use, []).append(building["geometry"]["size_m"][2])
        programmes.setdefault(use, []).append(building["attributes"]["programme"])
    assert set(heights) == {"residential", "market", "civic"}
    assert max(heights["residential"]) <= max(heights["civic"]), "the civic band should not be shorter than the edge"
    mean = lambda values: sum(values) / len(values)
    assert mean(heights["civic"]) > mean(heights["residential"])
    assert mean(heights["civic"]) > mean(heights["market"]) > mean(heights["residential"])
    assert "library" not in programmes["residential"]
    assert programmes["residential"].count("residence") >= len(programmes["residential"]) // 2


def test_city_roads_widen_towards_the_centre():
    spec = CitySpec(seed=101)
    records = initial_records(spec)
    for stage in STAGES:
        additions, _ = plan_stage(spec, stage, records)
        records.extend(additions)
        next(r for r in records if r["record_type"] == "world_spec")["extensions"]["stage"] = stage
    spines = [r for r in records if r.get("kind") == "road"
              and (r["id"].startswith("road_west_") or r["id"].startswith("road_east_"))]
    assert len(spines) == 30, "ten columns split into three district bands"
    widths = {}
    for spine in spines:
        widths.setdefault(spine["id"].rsplit("_", 1)[1], set()).add(spine["geometry"]["size_m"][0])
    assert widths == {"0": {3}, "1": {4}, "2": {6}}, widths
    road_ids = {r["id"] for r in records if r.get("kind") in {"road", "bridge"}}
    entrances = [r for r in records if r.get("relation_type") == "entrance"]
    assert entrances, "every building keeps an entrance relation"
    for relation in records:
        if relation.get("relation_type") == "connects" and relation["source_id"] in road_ids:
            assert set(relation["target_ids"]) <= road_ids, relation["id"]
