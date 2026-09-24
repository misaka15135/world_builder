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
    assert city.generator_version == "0.1.0-city.1"
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


def test_city_batch_registration_was_fixed_before_results():
    path = Path(__file__).resolve().parents[1] / "benchmarks/city_cases_v1.json"
    registration = json.loads(path.read_text(encoding="utf-8"))
    assert registration["generator_version"] == CitySpec().generator_version
    assert len(registration["cases"]) == 30
    for scenario, seed_start in (("riverside", 101), ("hillside", 201), ("dense", 301)):
        cases = [case for case in registration["cases"] if case["spec"]["scenario"] == scenario]
        assert [case["spec"]["seed"] for case in cases] == list(range(seed_start, seed_start + 10))
        assert [case["spec"]["layout_profile"] for case in cases] == ["standard"] * 5 + ["compact"] * 5
        assert all(case["spec"]["building_count"] == 80 and case["spec"]["interior_count"] == 5 for case in cases)
