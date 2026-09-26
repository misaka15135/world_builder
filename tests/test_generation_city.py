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
    assert city.generator_version == "0.1.0-city.5"
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
    assert json.loads((root / "city_cases_v4.json").read_text(encoding="utf-8"))["generator_version"] == "0.1.0-city.4"
    current = json.loads((root / "city_cases_v5.json").read_text(encoding="utf-8"))
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


def test_outlying_districts_sit_on_a_looser_grid():
    spec = CitySpec(seed=101)
    records = initial_records(spec)
    for stage in STAGES:
        additions, _ = plan_stage(spec, stage, records)
        records.extend(additions)
        next(r for r in records if r["record_type"] == "world_spec")["extensions"]["stage"] = stage
    rows: dict[str, set] = {}
    for parcel in (r for r in records if r.get("kind") == "parcel"):
        rows.setdefault(parcel["parent_id"], set()).add(round(parcel["bounds"]["min"][1], 3))
    assert len(rows["district_0"]) == 30, "the residential edge should not sit on one line per row"
    assert len(rows["district_1"]) == 30
    assert len(rows["district_2"]) == 2, "the civic centre keeps a tidy grid"
    # every building still reaches a road, and the road network stays connected
    entrances = [r for r in records if r.get("relation_type") == "entrance"]
    assert len(entrances) == 80
    assert not [c for c in check_geometry(records) if c["rule"] == "pilot.network_connected" and c["state"] != "pass"]


def test_city_rooms_are_separated_by_declared_partitions():
    spec = CitySpec(seed=101)
    records = initial_records(spec)
    for stage in STAGES:
        additions, _ = plan_stage(spec, stage, records)
        records.extend(additions)
        next(r for r in records if r["record_type"] == "world_spec")["extensions"]["stage"] = stage
    storeys = [r for r in records if r.get("kind") == "storey"]
    walls = [r for r in records if r.get("kind") == "partition"]
    rooms = [r for r in records if r.get("kind") == "room"]
    assert len(walls) == len(storeys), "every storey declares its dividing wall"
    assert len(rooms) == 2 * len(storeys)
    for wall in walls:
        opening = wall["attributes"]["opening"]
        assert opening["side"] == "west" and opening["width_m"] > 0 and opening["height_m"] > 0
    checks = check_geometry(records)
    assert not [c for c in checks if c["rule"].startswith("city.partition") and c["state"] != "pass"]
    assert not [c for c in checks if c["rule"] == "city.room_circulation" and c["state"] != "pass"]


def test_style_profile_changes_the_silhouette():
    def build(style):
        spec = CitySpec(seed=101, style_profile=style)
        records = initial_records(spec)
        for stage in STAGES:
            additions, _ = plan_stage(spec, stage, records)
            records.extend(additions)
            next(r for r in records if r["record_type"] == "world_spec")["extensions"]["stage"] = stage
        return spec, records

    arcane_spec, arcane = build("arcane_medieval")
    modern_spec, modern = build("modern_grid")
    assert arcane_spec.world_id != modern_spec.world_id, "a different style is a different world"
    arcane_buildings = [r for r in arcane if r.get("kind") == "building"]
    modern_buildings = [r for r in modern if r.get("kind") == "building"]
    assert {r["attributes"]["roof_style"] for r in modern_buildings} == {"flat"}
    assert {"gable", "spire"} & {r["attributes"]["roof_style"] for r in arcane_buildings}
    mean = lambda rows, key: sum(key(r) for r in rows) / len(rows)
    assert mean(modern_buildings, lambda r: r["attributes"]["storeys"]) > mean(
        arcane_buildings, lambda r: r["attributes"]["storeys"])
    assert {r["attributes"]["programme"] for r in modern_buildings} <= {"apartment", "office", "shop", "inn", "library", "workshop", "residence"}
    assert not [c for c in check_geometry(modern) if c["severity"] == "hard" and c["state"] != "pass"]
    # The city wall belongs to the arcane profile only, and its gates are tied
    # back into the street network so the wall never isolates the city.
    arcane_walls = [r for r in arcane if r.get("kind") == "wall"]
    assert len(arcane_walls) == 6, "two gated sides split in two plus two solid sides"
    assert {r["id"] for r in arcane_walls} >= {"wall_west_south", "wall_west_north", "wall_south", "wall_north"}
    assert not [r for r in modern if r.get("kind") == "wall"], "the modern profile has no city wall"
    approaches = [r for r in arcane if r.get("id", "").startswith("approach_")]
    assert len(approaches) == 2
    road_ids = {r["id"] for r in arcane if r.get("kind") in {"road", "bridge"}}
    assert road_ids >= {"approach_west", "approach_east"}
