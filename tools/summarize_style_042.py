"""Merge immutable source and independent Unity evidence for user handoff."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from world_builder.agents.contracts import ROOT,strict_json
from world_builder.agents.runtime import write_json


def main():
    folder=ROOT/"artifacts/style042/arcane-v3"
    read=lambda p:strict_json(p.read_bytes())
    source=read(folder/"result.json")
    geometry=read(folder/"style_geometry.json")
    accepted=read(folder/"accepted.json")
    target=read(folder/"unity-evidence/target_validation.json")
    reopened=read(folder/"unity-evidence/target_reopen.json")
    walk=read(folder/"unity-evidence/walk_validation.json")
    replay=read(folder/"replay_validation.json")
    expected=source["exports"]["unity"]["mesh_count"]
    checks={"source_geometry":source["source_geometry_validation"]=="pass",
            "exact_replay":replay["status"]=="pass",
            "unity_load_bounds":target["status"]=="pass" and target["bounds_checked"]==expected,
            "unity_reopen_bounds":reopened["status"]=="pass" and reopened["bounds_checked"]==expected,
            "all_room_walks":walk["status"]=="pass" and walk["completed_routes"]==geometry["report"]["source_room_routes"]}
    designs=[p for p in accepted["plans"]["E"].values() if "storeys" in p]
    summary={"machine_status":"pass" if all(checks.values()) else "fail","checks":checks,
             "revision_id":source["revision_id"],"mesh_count":expected,"solid_colliders":target["mesh_colliders"],
             "source_report":geometry["report"],"walk_completed_rooms":walk["completed_rooms"],
             "recorded_calls":source["provider_calls"],"new_network_calls_in_resumed_run":source["network_calls"],
             "reused_api_calls":source["reused_recorded_calls"],"is_independent_reliability_sample":False,
             "actual_design_choices":{"roof_styles":sorted({d["roof"] for d in designs}),
                                      "roof_materials":sorted({d["roof_material"] for d in designs}),
                                      "wall_materials":sorted({d["wall_material"] for d in designs})},
             "appearance_user_review":"pending","scope":"64m magic street, not complete city",
             "limitations":["solid colours, no textures","stepped roofs","simple vegetation",
                            "model narrative may misname bank/material; explicit parameters and target evidence are authoritative"],
             "unity_project":"adapters/unity/style042_project","scene":"Assets/Generated/API/ArcaneAPI.unity"}
    write_json(folder/"delivery_summary.json",summary)
    print(summary["machine_status"],"meshes",expected,"room walks",walk["completed_routes"])
    return 0 if all(checks.values()) else 1


if __name__=="__main__":raise SystemExit(main())
