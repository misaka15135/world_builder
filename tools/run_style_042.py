"""Run the registered bounded 042 street, offline baseline or exact replay."""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from world_builder.agents.contracts import ROOT, AgentError, canonical, digest, strict_json
from world_builder.agents.providers import APIProvider, ReplayProvider, load_config
from world_builder.agents.runtime import write_json
from world_builder.agents.style_scene import VERSION, BUILDER, StyleSupervisor, construct, save_style_world


class RecordedPrefixProvider:
    """Reuse exact recorded API requests; make new calls only for missing IDs."""
    network=True
    def __init__(self,original,live):
        self.recorded,self.live=ReplayProvider(original),live
    def complete(self,request,**kwargs):
        try:
            return self.recorded.complete(request,**kwargs)
        except AgentError as error:
            if error.code!="replay.missing": raise
            return self.live.complete(request,**kwargs)


def code_manifest():
    names=["src/world_builder/agents/style_scene.py","src/world_builder/agents/runtime.py",
           "src/world_builder/agents/style_routes.py",
           "src/world_builder/planning/designer.py","src/world_builder/adapters/minecraft/city.py",
           "src/world_builder/adapters/unity/sample.py","settings/arcane_medieval/designs.json",
           "settings/arcane_medieval/setting.json","settings/arcane_medieval/catalogue.json",
           "skills/world-style-042/D.md","skills/world-style-042/E.md","skills/world-style-042/F.md"]
    return {p:"sha256:"+hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in names}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check",action="store_true")
    parser.add_argument("--baseline",action="store_true")
    parser.add_argument("--replay",action="store_true")
    parser.add_argument("--batch",default="v1")
    parser.add_argument("--key-file",type=Path)
    args=parser.parse_args()
    if not args.batch.isalnum(): parser.error("Invalid batch ID")
    batch=strict_json((ROOT/f"benchmarks/style042_arcane_{args.batch}.json").read_bytes())
    cfg=load_config(ROOT/batch["config"])
    reference=strict_json((ROOT/batch["input"]).read_bytes())
    if args.check:
        print({"status":"ready","contract":VERSION,"builder":BUILDER,"batch_id":batch["batch_id"]})
        return 0
    if args.baseline and args.replay: parser.error("Choose baseline or replay")
    if batch["contract"]!=VERSION: parser.error("This entry point requires the current registered contract version")
    original=ROOT/f"artifacts/style042/arcane-{args.batch}"
    output=ROOT/f"artifacts/style042/baseline-{args.batch}" if args.baseline else original.with_name(original.name+"-replay") if args.replay else original
    if output.exists(): parser.error("Output exists; preserve the registered original")
    context={"batch_id":batch["batch_id"],"batch_sha256":digest(batch),"config_sha256":digest(cfg),"code_hashes":code_manifest()}
    if batch.get("reuse_from"):
        context["reuse_from"]=batch["reuse_from"]
    runner=None
    try:
        if args.baseline:
            output.mkdir(parents=True)
            geometry=construct(reference["layout"],reference["designs"])
            accepted={"contract_version":VERSION,"prompt":reference["prompt"],"seed":41,"region_m":64,
                      "source":reference["source"],"plans":{"D":reference["layout"],"E":reference["designs"]}}
            write_json(output/"accepted.json",accepted)
            write_json(output/"style_geometry.json",geometry)
        else:
            if args.replay:
                saved=strict_json((original/"evaluation_context.json").read_bytes())
                if saved!=context: parser.error("Replay code/config/registration differs")
                provider=ReplayProvider(original)
            else:
                if not args.key_file: parser.error("Provide a local key file; never send the key in chat")
                with args.key_file.open("rb") as stream:
                    encoding="utf-16" if stream.read(2) in (b"\xff\xfe",b"\xfe\xff") else "utf-8-sig"
                with args.key_file.open("r",encoding=encoding) as stream: key=stream.readline().strip()
                provider=APIProvider(cfg,api_key=key)
                del key
                if batch.get("reuse_from"):
                    provider=RecordedPrefixProvider(ROOT/batch["reuse_from"],provider)
            runner=StyleSupervisor(provider,cfg,output,region_m=64,seed=41)
            write_json(output/"evaluation_context.json",context)
            accepted,geometry=runner.run(reference["prompt"])
        result=save_style_world(accepted,geometry,output)
        result.update(runner.usage() if runner else {"network_calls":0,"provider_calls":0})
        if runner and batch.get("reuse_from") and not args.replay:
            result["reused_recorded_calls"]=runner.calls-runner.network_calls
        result["mode"]="baseline" if args.baseline else "replay" if args.replay else "api"
        write_json(output/"result.json",result)
        if args.replay:
            names=["scene.worldpkg","unity/scene.glb","style_geometry.json"]
            checks={p:(original/p).read_bytes()==(output/p).read_bytes() for p in names}
            checks["zero_network"]=runner.network_calls==0
            write_json(original/"replay_validation.json",{"status":"pass" if all(checks.values()) else "fail","checks":checks})
            if not all(checks.values()): raise ValueError("Replay differs")
        print(canonical(result).decode("utf-8"))
        return 0
    except Exception as error:
        output.mkdir(parents=True,exist_ok=True)
        failure={"status":"failed","code":getattr(error,"code","execution.error"),"message":str(error)}
        if runner: failure.update(runner.usage())
        write_json(output/"result.json",failure)
        print(canonical(failure).decode("utf-8"))
        return 1


if __name__=="__main__": raise SystemExit(main())
