"""Evidence and failure gates for the bounded 042 style bridge."""
from copy import deepcopy
import pytest
from world_builder.agents.contracts import ROOT, AgentError, canonical, strict_json
from world_builder.agents.providers import Completion, ReplayProvider, load_config
from world_builder.agents.style_scene import StyleSupervisor, check_layout, construct, raw_building, save_style_world, project_layout
from world_builder.agents.validation import overlaps


@pytest.fixture(scope="module")
def reference():
    return strict_json((ROOT/"examples/style042_baseline.json").read_bytes())


@pytest.fixture(scope="module")
def geometry(reference):
    return construct(reference["layout"],reference["designs"])


def test_layout_rejects_missing_site_and_detached_entrance(reference):
    b=deepcopy(reference["layout"])
    b["sites"][0]["entry_side"]="north"
    with pytest.raises(AgentError,match="facade must touch"):
        check_layout(b)
    b=deepcopy(reference["layout"])
    b["sites"][0]["type"]="shop"
    with pytest.raises(AgentError,match="two residences"):
        check_layout(b)


def test_geometry_preserves_detail_and_clear_routes(geometry):
    assert len(geometry["walking"]["routes"])==14
    assert all(len(r["cells"])>1 for r in geometry["walking"]["routes"])
    parts=geometry["parts"]
    assert any(p["block"]=="minecraft:glass" for p in parts)
    for i,p in enumerate(parts):
        a={"min":p["bounds_wir_m"][0],"max":p["bounds_wir_m"][1]}
        assert not any(overlaps(a,{"min":q["bounds_wir_m"][0],"max":q["bounds_wir_m"][1]}) for q in parts[:i])
    for g,s in geometry["report"]["sites"].items():
        if s["type"]!="plaza": assert s["features"]["window"]>0 and s["features"]["porch"]>0


def test_model_parameters_change_actual_geometry(reference):
    site=reference["layout"]["sites"][0]
    params=deepcopy(reference["designs"][site["id"]])
    a,_=raw_building(site,params)
    params["storeys"]=2
    params["room_uses"].append(["bed","store"])
    b,semantic=raw_building(site,params)
    assert a!=b and len(semantic["rooms"])==4
    params["site_id"]="wrong"
    with pytest.raises(AgentError): raw_building(site,params)


def test_parameter_layout_projection_and_narrow_shop_treads(reference):
    assert project_layout(reference["layout_parameters"])==reference["layout"]
    layout=deepcopy(reference["layout"])
    layout["sites"][3]["rect"][2]=20  # 12m-wide shop has 0.2m stair treads.
    geometry=construct(layout,reference["designs"])
    upper=[r for r in geometry["walking"]["routes"] if r["group"]=="shop_south" and r["level"]==1]
    assert len(upper)==2


def test_blocked_door_is_not_accepted_as_reachable(geometry):
    from world_builder.agents.style_routes import walking_routes
    obstructed=deepcopy(geometry)
    obstructed["parts"].append({"block":"minecraft:stone_bricks","bounds_wir_m":[[8.2,31,1],[10.2,33,4]]})
    with pytest.raises(AgentError): walking_routes(obstructed)


def test_synthetic_pipeline_exact_replay_and_package(tmp_path,reference):
    class Provider:
        network=False
        def complete(self,request,**kwargs):
            stage=request["stage"]
            payload=reference["layout_parameters"] if stage=="D" else reference["designs"][request["scope_id"]] if stage=="E" else {
                "verdict":"accept","evidence":"Synthetic evidence only","issues":[],"limitations":["Target not tested"]}
            response={k:request[k] for k in ("contract_version","stage","request_id","scope_id")}
            response["payload"]=payload
            return Completion(canonical(response),"synthetic",0,0,"synthetic")
    config=load_config(ROOT/"config/agents.deepseek-style042.json")
    original=StyleSupervisor(Provider(),config,tmp_path/"original",region_m=64)
    a,g=original.run(reference["prompt"])
    result=save_style_world(a,g,original.root)
    assert result["source_geometry_validation"]=="pass" and result["target_load"]=="not_run"
    replay=StyleSupervisor(ReplayProvider(original.root),config,tmp_path/"replay",region_m=64)
    ra,rg=replay.run(reference["prompt"])
    save_style_world(ra,rg,replay.root)
    assert replay.network_calls==0
    for name in ("scene.worldpkg","unity/scene.glb","unity/routes.json"):
        assert (original.root/name).read_bytes()==(replay.root/name).read_bytes()
