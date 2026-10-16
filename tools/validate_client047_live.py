"""Registered real HTTP/API client-profile check, then zero-network exact replay."""
import argparse
import hashlib
from http.client import HTTPConnection
from pathlib import Path
import sys
from threading import Thread
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from world_builder.agents.contracts import ROOT,canonical,digest,strict_json
from world_builder.agents.runtime import write_json
from world_builder.workbench.jobs import JobService,TERMINAL
from world_builder.workbench.server import WorkbenchServer
from world_builder.workbench import nature

PROMPT=nature.PROMPT+' 西部/北部/东部山丘参数分别48/78/42米，树木400棵；河道宽22米，弯曲幅度34米，相位28度，河谷过渡118米。四个聚落中心依次西南(190,210)、西北(180,465)、东南(575,245)、东北(565,490)，半径分别108、106、110、104米，住宅权重分别52、48、56、46，朝向偏转分别20、24、18、26度。城堡中心(615,665)、旋转-8度。仅要求本周已支持的能力。'
FILES=['src/world_builder/workbench/'+n+'.py' for n in ('nature','jobs','runner','server')]
FILES+=['src/world_builder/agents/'+n+'.py' for n in ('nature_scene','nature_mesh','nature_export','runtime','providers')]
FILES+=['src/world_builder/planning/catalogue.py','skills/world-client-047/A.md','examples/nature047_reference.json','examples/nature046_recipes.json']


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--register',action='store_true');parser.add_argument('--key-file',type=Path)
    args=parser.parse_args();cfg=nature.effective_config(nature.metadata()['default_config'])
    context={'profile':nature.generation_context(),'prompt':PROMPT,'config':cfg,
             'code_hashes':{p:'sha256:'+hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FILES}}
    registration=ROOT/'benchmarks/client047_live_v1.json'
    if args.register:
        if registration.exists():parser.error('Registration exists; preserve history')
        write_json(registration,{'context':context,'max_new_network_calls':6,'max_accounted_tokens':150000,'sample_count':1})
        print('Registered client047_live_v1');return 0
    if not registration.exists() or strict_json(registration.read_bytes())['context']!=context:parser.error('Freeze matching context first')
    if not args.key_file:parser.error('Use local --key-file; never send credentials to chat')
    root=ROOT/'artifacts/client047/live-http-v1'
    if root.exists():parser.error('Run exists; preserve historical evidence')
    with args.key_file.open('rb') as stream:encoding='utf-16' if stream.read(2) in (b'\xff\xfe',b'\xfe\xff') else 'utf-8-sig'
    with args.key_file.open(encoding=encoding) as stream:key=stream.readline().strip()
    service=JobService(root,cfg);server=WorkbenchServer(('127.0.0.1',0),service)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    def call(path,body=None):
        connection=HTTPConnection('127.0.0.1',server.server_port,timeout=30)
        connection.request('GET' if body is None else 'POST','/api/v1/'+path,
                           body=None if body is None else canonical(body),headers={'Content-Type':'application/json','X-Workbench-Token':server.token,'Origin':server.origin})
        response=connection.getresponse();data=strict_json(response.read());status=response.status;connection.close()
        if status>=400:raise RuntimeError(data['error']['code'])
        return data
    def wait(id):
        last=None;deadline=time.monotonic()+1800
        while time.monotonic()<deadline:
            job=call('jobs/'+id)
            if job['phase']!=last:print(id[:8],job['phase'],flush=True);last=job['phase']
            if job['status'] in TERMINAL:
                if job['status']!='succeeded':raise RuntimeError(job['error']['code'])
                return job
            time.sleep(2)
        service.cancel(id);raise RuntimeError('Test timeout; cancellation requested')
    try:
        first=call('jobs',{'pipeline':'nature047','mode':'api','prompt':PROMPT,'config':cfg,'api_key':key});del key
        first=wait(first['id'])
        second=wait(call('jobs',{'mode':'replay','replay_id':first['id']})['id'])
        checks=strict_json((root/second['id']/'output/replay_validation.json').read_bytes())
        report={'status':checks['status'],'api_run':first['id'],'api_result':first['result'],'replay_run':second['id'],
                'replay_result':second['result'],'replay_validation':checks,'registration_sha256':digest(context)}
        write_json(root/'validation.json',report);print(canonical(report).decode('utf-8'));return 0
    finally:
        server.shutdown();server.server_close();thread.join(3);service.close()


if __name__=='__main__':raise SystemExit(main())
