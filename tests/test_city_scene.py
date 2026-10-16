from copy import deepcopy
import pytest
from world_builder.agents.contracts import AgentError, ROOT, canonical
from world_builder.agents.city_scene import (CitySupervisor, RECIPE_IDS, check_base, check_catalogue, check_network,
                                             check_no_overlap, construct_city, disjoint, project_sites, synthetic_plans)
from world_builder.agents.providers import Completion, load_config
from world_builder.agents.style_scene import box


@pytest.fixture(scope="module")
def plans():return synthetic_plans()


@pytest.fixture(scope="module")
def geometry(plans):return construct_city(plans,routes=False)


def test_48_unique_parcels_and_model_parameters_change_geometry(plans):
    sites=project_sites(plans["B"],plans["D"],plans["C"])
    assert len(sites)==48 and len({s["id"] for s in sites})==48
    changed=deepcopy(plans);changed["D"]["sites"][0]["width"]+=1
    newer=project_sites(changed["B"],changed["D"],changed["C"])
    sid=plans["D"]["sites"][0]["slot"]
    assert next(s for s in newer if s["id"]==sid)["rect"][2]==next(s for s in sites if s["id"]==sid)["rect"][2]+1
    changed["D"]["sites"][0]["slot"]=changed["D"]["sites"][1]["slot"]
    with pytest.raises(AgentError,match="48 slots"):project_sites(changed["B"],changed["D"],changed["C"])


def test_invalid_road_and_missing_recipe_rejected(plans):
    b=deepcopy(plans["B"]);b["street_y"][1]=b["street_y"][0]
    with pytest.raises(AgentError,match="street_y"):check_base(b)
    c=deepcopy(plans["C"]);c["archetypes"][0]["id"]="shop_a"
    with pytest.raises(AgentError,match="eight recipe"):check_catalogue(c)
    d=deepcopy(plans["D"])
    for s in d["sites"]:s["recipe_id"]="home_a"
    with pytest.raises(AgentError,match="eight recipes"):project_sites(plans["B"],d,plans["C"])


def test_city_detail_and_real_river_cut(geometry):
    assert len(geometry["buildings"])==49
    assert geometry["report"]["ordinary_buildings"]==48
    assert geometry["network"]["status"]=="pass"
    assert geometry["walking"]["status"]=="not_run"
    assert 4000<len(geometry["parts"])<=16000
    for p in geometry["parts"]:
        if p["group"]=="terrain":
            assert p["bounds_wir_m"][1][0]<=248 or p["bounds_wir_m"][0][0]>=264
    assert all(any(feature in p["source_id"] for p in geometry["parts"] if p["group"]=="row0_col0_south")
               for feature in ("window","porch","roof"))


def test_missing_bridge_is_not_a_connected_network(geometry,plans):
    broken={**geometry,"parts":[p for p in geometry["parts"] if not p["source_id"].startswith("bridge_0_")]}
    with pytest.raises(AgentError,match="cross_river_0"):check_network(broken,plans["B"],geometry["castle_site"])


def test_closed_castle_gate_rejected(geometry,plans):
    cx=geometry["castle_x"]+64
    broken={**geometry,"parts":geometry["parts"]+[box("closed_gate",[cx-5,432,cx+5,434],1.1,5,"minecraft:stone_bricks","test")]}
    with pytest.raises(AgentError,match="castle_gate"):check_network(broken,plans["B"],geometry["castle_site"])


def test_spatial_paint_preserves_volume_and_removes_overlap():
    raw=[box("a",[0,0,40,40],0,3,"minecraft:stone_bricks","a"),box("b",[4,4,8,8],1,2,"minecraft:glass","b")]
    parts=disjoint(raw);check_no_overlap(parts)
    volume=sum((b[0]-a[0])*(b[1]-a[1])*(b[2]-a[2]) for a,b in (p["bounds_wir_m"] for p in parts))
    assert volume==4800 and any(p["source_id"]=="b" for p in parts)
    with pytest.raises(AgentError,match="Overlapping"):check_no_overlap(raw)


def test_request_contract_and_e_scope(plans,tmp_path):
    class Provider:
        network=False
        def complete(self,request,**kwargs):
            envelope={k:request[k] for k in ("contract_version","stage","scope_id","request_id")}
            envelope["payload"]=plans[request["stage"]] if request["stage"]!="E" else plans["E"][request["scope_id"]]
            return Completion(canonical(envelope),"synthetic",0,0,"synthetic")
    cfg=load_config(ROOT/"config/agents.deepseek-city045.json")
    runner=CitySupervisor(Provider(),cfg,tmp_path/"run",region_m=512,seed=45);runner.prompt="Synthetic scope test"
    assert runner.ask("B",{})==plans["B"]
    assert runner.ask("E",{k:plans[k] for k in ("B","C","D")},scope_id="shop_a")==plans["E"]["shop_a"]
    assert runner.network_calls==0


@pytest.mark.parametrize("group",["row0_col0_south","row0_col0_north"])
def test_accelerated_clearance_matches_042_exact_paths(geometry,group):
    from world_builder.agents.style_routes import walking_routes as original
    from world_builder.agents.city_routes import walking_routes as accelerated
    one={**geometry,"buildings":{group:geometry["buildings"][group]}}
    assert original(one)["routes"]==accelerated(one)["routes"]
