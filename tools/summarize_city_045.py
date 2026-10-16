"""Cross-check immutable 045 source/replay and actual Unity delivery evidence."""
import argparse
import hashlib
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from world_builder.agents.contracts import ROOT, strict_json
from world_builder.agents.runtime import write_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,default=ROOT/"artifacts/city045/live-v1")
    parser.add_argument("--replay",type=Path,default=ROOT/"artifacts/city045/live-v1-replay")
    args=parser.parse_args();source=args.source.resolve()
    def read(path):return strict_json(Path(path).read_bytes())
    result=read(source/"result.json");geometry=read(source/"city_geometry.json");manifest=read(source/"unity/manifest.json")
    evidence=source/"unity-evidence"
    loaded=read(evidence/"target_validation.json");reopened=read(evidence/"target_reopen.json");walk=read(evidence/"walk_validation.json")
    replay=read(args.replay/"replay_validation.json")
    selected=read(ROOT/"adapters/unity/style042_project/Assets/Generated/City/unity_paths.json")
    expected={p["room"] for p in selected["paths"]};meshes=manifest["piece_count"];solid=sum(p["solid"] for p in manifest["pieces"])
    def target_ok(report):
        return report["status"]=="pass" and report["source_revision_id"]==result["revision_id"] and report["glb_sha256"]==manifest["glb_sha256"] and all(
            report[key]==meshes for key in ("expected_pieces","mapped_pieces","bounds_checked","batched_source_meshes")) and report["mesh_colliders"]==solid and 0<report["render_batches"]<meshes
    checks={"source_geometry":result["source_geometry_validation"]=="pass" and geometry["walking"]["status"]=="pass" and geometry["network"]["status"]=="pass",
            "worldpkg_hash":"sha256:"+hashlib.sha256((source/"scene.worldpkg").read_bytes()).hexdigest()==result["worldpkg_sha256"],
            "glb_hash":"sha256:"+hashlib.sha256((source/"unity/scene.glb").read_bytes()).hexdigest()==manifest["glb_sha256"],
            "exact_replay":replay["status"]=="pass" and all(replay["checks"].values()),
            "unity_load":target_ok(loaded),"unity_saved_reopen":target_ok(reopened),
            "selected_physical_routes":walk["status"]=="pass" and walk["expected_routes"]==walk["completed_routes"]==len(expected) and set(walk["completed_rooms"])==expected and walk["grounded_frames"]>0}
    summary={"machine_status":"pass" if all(checks.values()) else "fail","checks":checks,"appearance_user_review":"pending",
             "region_m":512,"ordinary_buildings":geometry["report"]["ordinary_buildings"],"castle_keeps":1,"castle_towers":4,"plazas":4,"bridges":4,
             "revision_id":result["revision_id"],"source_meshes":meshes,"solid_colliders":solid,"render_batches":loaded["render_batches"],
             "source_room_routes":len(geometry["walking"]["routes"]),"physical_routes":len(expected),"physical_frames":walk["frames"],
             "network_calls":result["network_calls"],"accounted_tokens":result["accounted_tokens"],"generation_elapsed_s":result["elapsed_s"],
             "api_map_samples":1,"scene":"Assets/Generated/City/ArcaneCity.unity",
             "physical_scope":selected["scope"],"limitations":["solid colours and stepped geometry","flat land, straight roads and river, constrained parcels",
             "representative target room tests, not all instance rooms","no tower stairs, gameplay, dynamic water or Minecraft delivery"]}
    write_json(source/"delivery_summary.json",summary)
    print(summary["machine_status"],"meshes",meshes,"source rooms",summary["source_room_routes"],"physical routes",len(expected))
    return 0 if all(checks.values()) else 1


if __name__=="__main__":raise SystemExit(main())
