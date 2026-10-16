"""Read-only cross-checks of the local 047 delivery; writes a new evidence report.

Run after desktop adjustment/replay/download and close/reopen UI checks. This
does not call a model, overwrite runs, or claim target-engine validation.
"""
import argparse
import hashlib
from http.client import HTTPConnection
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from world_builder.agents.contracts import ROOT,strict_json
from world_builder.agents.runtime import write_json


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return strict_json(path.read_bytes())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key-file',type=Path,required=True,help='Local rotated key, used only to detect accidental persistence')
    args=parser.parse_args()
    root=ROOT/'artifacts/client047';report_path=root/'validation.json'
    if report_path.exists():parser.error('Evidence exists; preserve previous report')
    checks={}
    for label,registration in [('045','city045_arcane_v1.json'),('046','nature046_organic_v3.json'),('047','client047_live_v1.json')]:
        context=read(ROOT/'benchmarks'/registration)['context']
        checks['frozen_'+label+'_context_unchanged']=all(sha(ROOT/p)==expected for p,expected in context['code_hashes'].items())
    checks['bundled_web_matches_source']=all(p.read_bytes()==(ROOT/'dist/WorldBuilder047v2/_internal/web'/p.relative_to(ROOT/'web')).read_bytes()
                                               for p in (ROOT/'web').rglob('*') if p.is_file())
    build=read(ROOT/'dist/build-info-WorldBuilder047v2.json')
    checks['zip_hash_matches_build_report']=sha(ROOT/'dist'/build['archive'])=='sha256:'+build['sha256']
    checks['legacy_v2_bundled_fixture_replay']=read(root/'v2-legacy-selftest/self-test.json')['status']=='pass'
    baseline='8f7ec437bf4b4fbca9ab6804dcacedb5';adjusted='c97dde2244e941ab8c0310e57a74bec0';replayed='51776628c70f4db39d4a63644e86c54b'
    runs=root/'packaged-data/runs'
    jobs={label:read(runs/id/'job.json') for label,id in [('baseline',baseline),('adjusted',adjusted),('replayed',replayed)]}
    checks['desktop_runs_succeeded']=all(job['status']=='succeeded' for job in jobs.values())
    checks['desktop_runs_zero_network']=all(job['result']['network_calls']==0 for job in jobs.values())
    checks['desktop_adjustment_preserves_parent']=jobs['adjusted']['source_id']==baseline and jobs['baseline']['result']['source_report']['trees']==388
    change=read(runs/adjusted/'input.json')['changes']
    checks['desktop_only_declared_parameter_changed']=change=={'B.trees':{'before':388,'after':410}}
    a=read(runs/baseline/'output/nature_geometry.json');b=read(runs/adjusted/'output/nature_geometry.json')
    checks['desktop_poses_unchanged']=a['poses']==b['poses']
    checks['desktop_nonforest_geometry_unchanged']=[p for p in a['parts'] if p['group']!='forest']==[p for p in b['parts'] if p['group']!='forest']
    checks['desktop_adjustment_trees_410']=b['report']['trees']==410
    replay=read(runs/replayed/'output/replay_validation.json')
    checks['desktop_adjustment_exact_replay']=replay['status']=='pass' and all(replay['checks'].values())
    checks['native_download_matches_export']=sha(root/'download-native-410.glb')==sha(runs/adjusted/'output/unity/scene.glb')
    live=read(root/'live-http-v1/validation.json')
    checks['registered_real_api_and_exact_replay']=live['status']=='pass' and live['api_result']['network_calls']==4 and live['replay_result']['network_calls']==0
    checks['new_targets_not_falsely_marked_tested']=all(job['result']['target_load']=='not_run' and job['result']['walkthrough']=='not_run' for job in jobs.values())
    session=read(root/'packaged-data/session.json');origin=urlsplit(session['origin'])
    if origin.hostname!='127.0.0.1':raise RuntimeError('Not a loopback desktop test session')
    def get(path):
        connection=HTTPConnection(origin.hostname,origin.port,timeout=30)
        connection.request('GET','/api/v1/'+path);response=connection.getresponse();raw=response.read();headers=dict(response.getheaders());connection.close()
        return response.status,headers,raw
    bootstrap=get('bootstrap');metadata=strict_json(bootstrap[2])
    checks['reopened_profile_metadata']=bootstrap[0]==200 and metadata['nature']['id']=='nature047' and len(metadata['nature']['fields'])==31
    history=get('jobs');ids={j['id'] for j in strict_json(history[2])['jobs']}
    checks['reopened_history_all_three']=history[0]==200 and {baseline,adjusted,replayed}<=ids
    status,headers,payload=get(f'jobs/{adjusted}/file?path=scene.worldpkg')
    checks['worldpkg_download_http_hash']=status==200 and 'attachment' in headers['Content-Disposition'] and 'sha256:'+hashlib.sha256(payload).hexdigest()==jobs['adjusted']['result']['worldpkg_sha256']
    checks['download_path_traversal_rejected']=get(f'jobs/{adjusted}/file?path=../../preferences.json')[0]==404
    with args.key_file.open('rb') as stream:encoding='utf-16' if stream.read(2) in (b'\xff\xfe',b'\xfe\xff') else 'utf-8-sig'
    with args.key_file.open(encoding=encoding) as stream:key=stream.readline().strip()
    if not key or len(key)<16:raise RuntimeError('Key file cannot support a meaningful persistence check')
    needles=[key.encode('utf-8'),key.encode('utf-16-le')];del key
    tracked=subprocess.run(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT,stdout=subprocess.PIPE,check=True).stdout
    paths={ROOT/p.decode('utf-8') for p in tracked.split(b'\0') if p}
    paths.update(p for p in root.rglob('*') if p.is_file() and p.suffix in ('.json','.jsonl','.log','.glb','.worldpkg'))
    paths.update(p for p in (ROOT/'dist/WorldBuilder047v2').rglob('*') if p.is_file())
    leaked=[str(p.relative_to(ROOT)) for p in paths if p.is_file() and any(needle in p.read_bytes() for needle in needles)]
    del needles
    checks['current_key_not_persisted_in_scanned_delivery_or_runs']=not leaked
    report={'status':'pass' if all(checks.values()) else 'fail','checks':checks,'scan_file_count':len(paths),'credential_leak_paths':leaked,
            'desktop_runs':{label:job['id'] for label,job in jobs.items()},'desktop_adjustment_result':jobs['adjusted']['result'],
            'live_api_summary':{k:live['api_result'][k] for k in ('network_calls','accounted_tokens','elapsed_s','source_report')},
            'build':build,'target_validation':'New 047 variants not loaded or walked in Unity; source/client evidence only',
            'automated_tests':'153 passed; recorded separately in work order','ui_evidence':'Manual sky desktop checks recorded in 047 work order and screenshots'}
    write_json(report_path,report);print(json.dumps({'status':report['status'],'checks':checks,'scan_file_count':len(paths)},ensure_ascii=False))
    return 0 if report['status']=='pass' else 1


if __name__=='__main__':raise SystemExit(main())
