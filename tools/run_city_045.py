"""Registered 512m city: explicit offline fixture, real API, or exact offline replay."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from world_builder.agents.contracts import ROOT, AgentError, canonical, digest, strict_json
from world_builder.agents.providers import APIProvider, ReplayProvider, load_config
from world_builder.agents.runtime import write_json
from world_builder.agents.city_scene import VERSION, BUILDER, CitySupervisor, construct_city, synthetic_plans
from world_builder.agents.city_export import save_city_world

PROMPT="在512米见方区域建造完整魔法中世纪城邦：48栋可进入的住宅和商铺，至少16栋住宅及16栋两层商铺，使用八种模型设计配方并有尺寸、屋顶和石材/灰泥外墙变化；四条横向街道、两条纵向大道、一条贯穿的河道与四座有护栏的可通行桥，四座带喷泉的广场和通路、城墙及通行城门；东北部一座有四塔、门楼、庭院和可进入两层主楼的城堡；80至140棵树与路灯。保留窗框、门廊、家具和可上楼的楼梯。"
FILES=["src/world_builder/agents/city_scene.py","src/world_builder/agents/city_export.py","src/world_builder/agents/city_routes.py",
       "src/world_builder/agents/style_scene.py","src/world_builder/agents/style_routes.py","src/world_builder/agents/runtime.py",
       "src/world_builder/agents/providers.py","src/world_builder/planning/designer.py","src/world_builder/adapters/minecraft/city.py",
       "src/world_builder/adapters/unity/sample.py","settings/arcane_medieval/designs.json","settings/arcane_medieval/catalogue.json",
       "settings/arcane_medieval/setting.json",*[f"skills/world-city-045/{s}.md" for s in ("B","C","D","E","F")]]


def context(config):
    return {"contract":VERSION,"builder":BUILDER,"prompt":PROMPT,"config_sha256":digest(config),
            "code_hashes":{p:"sha256:"+hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FILES}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument("--offline",action="store_true")
    mode.add_argument("--replay",type=Path)
    parser.add_argument("--check",action="store_true")
    parser.add_argument("--register",action="store_true",help="Freeze context without using the API")
    parser.add_argument("--batch",default="v1")
    parser.add_argument("--output",type=Path)
    parser.add_argument("--key-file",type=Path)
    args=parser.parse_args()
    if not args.batch.isalnum():parser.error("Invalid batch ID")
    config=load_config(ROOT/"config/agents.deepseek-city045.json")
    current=context(config)
    registration=ROOT/f"benchmarks/city045_arcane_{args.batch}.json"
    if args.check:
        print({"status":"ready","contract":VERSION,"scope":"512m city / 48 buildings + castle", "max_calls":config["limits"]["max_calls"]})
        return 0
    if args.register:
        if registration.exists():parser.error("Registration exists; never overwrite historical context")
        write_json(registration,{"batch_id":"045-arcane-city-"+args.batch,"context":current,"limits":config["limits"],"sample_count":1})
        print("Registered",registration.name)
        return 0
    if not args.output:parser.error("Use --output with a new directory")
    output=args.output.resolve()
    if output.exists():parser.error("Output exists; preserve earlier attempts")
    runner=None
    try:
        if args.offline:
            plans=synthetic_plans()
            geometry=construct_city(plans)
            accepted={"contract_version":VERSION,"prompt":"Explicit synthetic comparison, not API output","region_m":512,"seed":45,"plans":plans,"source":"synthetic"}
            write_json(output/"accepted.json",accepted);write_json(output/"city_geometry.json",geometry)
        else:
            if not registration.exists():parser.error("Freeze --register after offline tests, before paid calls")
            batch=strict_json(registration.read_bytes())
            if batch["context"]!=current:parser.error("Code/config/skills differ from registration; do not relabel a frozen batch")
            if args.replay:
                original=args.replay.resolve()
                if strict_json((original/"evaluation_context.json").read_bytes())!=batch:parser.error("Replay context differs")
                provider=ReplayProvider(original)
            else:
                if not args.key_file:parser.error("Supply a local key file; do not put keys in chat")
                with args.key_file.open("rb") as stream:encoding="utf-16" if stream.read(2) in (b"\xff\xfe",b"\xfe\xff") else "utf-8-sig"
                with args.key_file.open(encoding=encoding) as stream:key=stream.readline().strip()
                provider=APIProvider(config,api_key=key);del key
            runner=CitySupervisor(provider,config,output,region_m=512,seed=45)
            write_json(output/"evaluation_context.json",batch)
            accepted,geometry=runner.run(PROMPT)
        result=save_city_world(accepted,geometry,output)
        result.update(runner.usage() if runner else {"network_calls":0,"provider_calls":0})
        result["mode"]="synthetic" if args.offline else "replay" if args.replay else "api"
        write_json(output/"result.json",result)
        if args.replay:
            checks={name:(args.replay/name).read_bytes()==(output/name).read_bytes()
                    for name in ("scene.worldpkg","unity/scene.glb","city_geometry.json")}
            checks["zero_network"]=runner.network_calls==0
            write_json(output/"replay_validation.json",{"status":"pass" if all(checks.values()) else "fail","checks":checks})
            if not all(checks.values()):raise AgentError("replay.different","Generated city differs")
        print(canonical(result).decode("utf-8"))
        return 0
    except (AgentError,ValueError,OSError) as error:
        failure={"status":"fail","code":getattr(error,"code","execution.error"),"message":str(error),
                 **(runner.usage() if runner else {})}
        write_json(output/"failure.json",failure)
        print(canonical(failure).decode("utf-8"));return 1


if __name__=="__main__":raise SystemExit(main())
