"""Read-only evidence aggregation, with explicit source/target/appearance scope."""
import argparse
import hashlib
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from world_builder.agents.contracts import strict_json, canonical
from world_builder.agents.runtime import write_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True);parser.add_argument('--replay',type=Path,required=True)
    args=parser.parse_args();source=args.source;read=lambda p:strict_json(p.read_bytes())
    result=read(source/'result.json');geometry=read(source/'nature_geometry.json');accepted=read(source/'accepted.json')
    manifest=read(source/'unity/manifest.json');target=read(source/'unity-evidence/target_validation.json')
    reopen=read(source/'unity-evidence/target_reopen.json');walk=read(source/'unity-evidence/walk_validation.json')
    replay=read(args.replay/'replay_validation.json');ctx=read(source/'evaluation_context.json')
    expected=len(manifest['pieces']);solid=sum(p['solid'] for p in manifest['pieces'])
    checks={
        'source_rooms_and_roads':geometry['walking']['status']==geometry['network']['status']=='pass',
        'actual_relief_irregular_layout':geometry['report']['terrain_relief_m']>40 and geometry['report']['unique_yaw_bins_5deg']>20 and len(geometry['sites'])==64,
        'unity_source_hash_identity':target['source_revision_id']==reopen['source_revision_id']==result['revision_id'] and target['glb_sha256']==manifest['glb_sha256'],
        'all_source_meshes_load_and_reopen':all(r['status']=='pass' and r['mapped_pieces']==r['bounds_checked']==r['batched_source_meshes']==expected and r['mesh_colliders']==solid for r in (target,reopen)),
        'continuous_target_walk':walk['status']=='pass' and walk['completed_routes']==walk['expected_routes'],
        'archive_hash':'sha256:'+hashlib.sha256((source/'scene.worldpkg').read_bytes()).hexdigest()==result['worldpkg_sha256'],
        'exact_zero_network_replay':replay['status']=='pass' and all(replay['checks'].values()),
        'new_api_and_recorded_E':result['mode']=='api' and result['network_calls']>0 and accepted['reused_E_provenance']['source_contract']=='0.1.0-city045',
    }
    previous=ctx.get('predecessor') or {}
    summary={'status':'pass' if all(checks.values()) else 'fail','checks':checks,'world_id':result['world_id'],'revision_id':result['revision_id'],
             'report':geometry['report'],'real_model_scope':'B,D,F; exact request reuse of prior B/D; nine recorded 045 E recipes',
             'network_calls_this_run':result['network_calls'],'network_calls_including_failed_predecessor':previous.get('cumulative_network_calls',previous.get('failure',{}).get('network_calls',0))+result['network_calls'],
             'accounted_tokens_this_run_including_reused_responses':result['accounted_tokens'],
             'target_routes':walk['completed_routes'],'target_frames':walk['frames'],'target_grounded_frames':walk['grounded_frames'],
             'appearance':'actual Unity screenshots; user review pending',
             'limitations':['Single registered map, not a general natural-scene benchmark or four-scene completion',
                            'Representative physical routes, not every room of all 64 houses',
                            'Low-poly flat materials; no water simulation, gameplay or Minecraft target validation']}
    write_json(source/'delivery_summary.json',summary);print(canonical(summary).decode('utf-8'))
    return 0 if all(checks.values()) else 1


if __name__=='__main__':raise SystemExit(main())
