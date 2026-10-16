"""Registered 768m rolling landscape: offline fixture, real B/D/F, recorded E reuse."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from world_builder.agents.contracts import ROOT, AgentError, canonical, digest, strict_json
from world_builder.agents.providers import APIProvider, ReplayProvider, load_config
from world_builder.agents.runtime import write_json
from world_builder.agents.nature_scene import VERSION, BUILDER, NatureSupervisor, build_nature, synthetic_parameters
from world_builder.agents.nature_export import save_nature_world

PROMPT="建造768米见方的自然魔法山谷地图：真实起伏地形、弯曲河流和两座通行桥，四个不规则的聚落共64栋可进入住宅与商铺，不采用行列网格，建筑不同尺寸和朝向；顺地形且避让房屋的土路连接每个入口，四个中心广场、300至440棵树，以及东北山丘的四塔城堡。建筑沿用先前045的九种真实API配方，仅重新规划地形与聚落。保留家具、窗框与通往二层的楼梯。"
FILES=["src/world_builder/agents/"+f+".py" for f in
       ("nature_scene","nature_mesh","nature_export","city_scene","city_routes","style_scene","style_routes","runtime","providers")]
FILES += ["src/world_builder/planning/designer.py","src/world_builder/adapters/minecraft/city.py",
          "src/world_builder/adapters/unity/sample.py","examples/nature046_recipes.json",
          *[f"skills/world-nature-046/{s}.md" for s in ("B","D","F")]]


def context(config):
    return {"contract":VERSION,"builder":BUILDER,"prompt":PROMPT,"config_sha256":digest(config),
            "code_hashes":{p:"sha256:"+hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FILES}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument("--offline",action="store_true")
    mode.add_argument("--replay",type=Path)
    parser.add_argument("--prepare-recipes",type=Path,help="Extract immutable accepted E recipes from 045")
    parser.add_argument("--check",action="store_true")
    parser.add_argument("--register",action="store_true")
    parser.add_argument("--batch",default="v1")
    parser.add_argument("--output",type=Path)
    parser.add_argument("--key-file",type=Path)
    parser.add_argument("--reuse-calls",type=Path,help="Reuse exact request-hash matches from a preserved failed batch")
    args=parser.parse_args()
    recipes_path=ROOT/"examples/nature046_recipes.json"
    if args.prepare_recipes:
        if recipes_path.exists():parser.error("Recipe snapshot already exists")
        accepted=strict_json((args.prepare_recipes/"accepted.json").read_bytes())
        result=strict_json((args.prepare_recipes/"result.json").read_bytes())
        require_real=result.get("mode")=="api" and accepted["contract_version"]=="0.1.0-city045"
        if not require_real:parser.error("Require accepted real API city045 provenance")
        write_json(recipes_path,{"source_contract":accepted["contract_version"],"source_world_id":result["world_id"],
                   "source_worldpkg_sha256":result["worldpkg_sha256"],"accepted_sha256":digest(accepted),
                   "accepted_E_responses":{k:v for k,v in accepted["accepted_responses"].items() if k.startswith("E:")},
                   "recipes":accepted["plans"]["E"]})
        print("Prepared recorded E recipe snapshot (no credentials/raw calls)");return 0
    if not args.batch.isalnum():parser.error("Invalid batch ID")
    config=load_config(ROOT/"config/agents.deepseek-nature046.json")
    current=context(config);registration=ROOT/f"benchmarks/nature046_organic_{args.batch}.json"
    reuse=strict_json(recipes_path.read_bytes())
    if args.check:
        print({"status":"ready","contract":VERSION,"scope":"768m terrain / 64 buildings + castle; new B,D,F / recorded E", "max_calls":config["limits"]["max_calls"]});return 0
    if args.register:
        if registration.exists():parser.error("Registration exists; preserve history")
        predecessor=None
        if args.reuse_calls:
            prior_context=strict_json((args.reuse_calls/'evaluation_context.json').read_bytes())
            prior_predecessor=prior_context.get('predecessor') or {}
            prior_data=strict_json((args.reuse_calls/('result.json' if (args.reuse_calls/'result.json').exists() else 'failure.json')).read_bytes())
            predecessor={"directory_label":args.reuse_calls.name,"context_sha256":digest(strict_json((args.reuse_calls/'evaluation_context.json').read_bytes())),
                         "prior_outcome":prior_data,
                         "cumulative_network_calls":prior_data['network_calls']+prior_predecessor.get('cumulative_network_calls',prior_predecessor.get('failure',{}).get('network_calls',0)),
                         "cumulative_accounted_tokens_upper_bound":prior_data['accounted_tokens']+prior_predecessor.get('cumulative_accounted_tokens_upper_bound',prior_predecessor.get('failure',{}).get('accounted_tokens',0))}
        write_json(registration,{"batch_id":"046-organic-"+args.batch,"context":current,"limits":config["limits"],"sample_count":1,"predecessor":predecessor})
        print("Registered",registration.name);return 0
    if not args.output:parser.error("Use --output with a new directory")
    output=args.output.resolve()
    if output.exists():parser.error("Output exists; preserve earlier attempts")
    runner=None
    try:
        if args.offline:
            geometry=build_nature(synthetic_parameters(),reuse["recipes"])
            accepted={"contract_version":VERSION,"prompt":"Explicit synthetic comparison, not API output","region_m":768,"seed":46,
                      "plans":{**synthetic_parameters(),"E":reuse["recipes"]},"source":"synthetic parameters / reused recorded E"}
            write_json(output/"accepted.json",accepted);write_json(output/"nature_geometry.json",geometry)
        else:
            if not registration.exists():parser.error("Freeze --register after offline tests")
            batch=strict_json(registration.read_bytes())
            if batch["context"]!=current:parser.error("Frozen code/config/skills differ; register a new batch")
            if args.replay:
                original=args.replay.resolve()
                if strict_json((original/"evaluation_context.json").read_bytes())!=batch:parser.error("Replay context differs")
                provider=ReplayProvider(original)
            else:
                if not args.key_file:parser.error("Supply local --key-file")
                with args.key_file.open("rb") as stream:encoding="utf-16" if stream.read(2) in (b"\xff\xfe",b"\xfe\xff") else "utf-8-sig"
                with args.key_file.open(encoding=encoding) as stream:key=stream.readline().strip()
                provider=APIProvider(config,api_key=key);del key
                if args.reuse_calls:
                    cached=ReplayProvider(args.reuse_calls);online=provider
                    if batch.get('predecessor',{}).get('context_sha256')!=digest(strict_json((args.reuse_calls/'evaluation_context.json').read_bytes())):
                        raise AgentError('reuse.context','Cached predecessor differs from registration')
                    class ExactReuse:
                        network=True
                        new_calls=0
                        def complete(self,request,*,timeout_s):
                            if (cached.root/'calls'/request['request_id'][7:]/'request.json').exists():
                                return cached.complete(request,timeout_s=timeout_s)
                            if batch['predecessor'].get('cumulative_network_calls',batch['predecessor'].get('failure',{}).get('network_calls',0))+self.new_calls>=config['limits']['max_calls']:
                                raise AgentError('budget.calls','Cumulative predecessor/network call limit')
                            self.new_calls+=1
                            return online.complete(request,timeout_s=timeout_s)
                    provider=ExactReuse()
            runner=NatureSupervisor(provider,config,output,region_m=768,seed=46)
            write_json(output/"evaluation_context.json",batch)
            accepted,geometry=runner.run(PROMPT,reuse)
        result=save_nature_world(accepted,geometry,output)
        result.update(runner.usage() if runner else {"network_calls":0,"provider_calls":0})
        if runner and batch.get('predecessor'):
            result['cumulative_network_calls']=batch['predecessor'].get('cumulative_network_calls',batch['predecessor'].get('failure',{}).get('network_calls',0))+result['network_calls']
        result["mode"]="synthetic" if args.offline else "replay" if args.replay else "api"
        write_json(output/"result.json",result)
        if args.replay:
            checks={name:(args.replay/name).read_bytes()==(output/name).read_bytes()
                    for name in ("scene.worldpkg","unity/scene.glb","nature_geometry.json")}
            checks["zero_network"]=runner.network_calls==0
            write_json(output/"replay_validation.json",{"status":"pass" if all(checks.values()) else "fail","checks":checks})
            if not all(checks.values()):raise AgentError("replay.different","Generated landscape differs")
        print(canonical(result).decode("utf-8"));return 0
    except (AgentError,ValueError,OSError) as error:
        failure={"status":"fail","code":getattr(error,"code","execution.error"),"message":str(error),**(runner.usage() if runner else {})}
        write_json(output/"failure.json",failure)
        print(canonical(failure).decode("utf-8"));return 1


if __name__=="__main__":raise SystemExit(main())
