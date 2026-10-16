"""Isolated packaged HTTP credential save/reopen/check. Synthetic key only."""
import argparse
import hashlib
from http.client import HTTPConnection
from pathlib import Path
import sys
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from world_builder.agents.contracts import ROOT,canonical,strict_json
from world_builder.agents.runtime import write_json
from world_builder.agents.providers import load_config

ENDPOINT='https://example.test/v1/chat/completions'
KEY='synthetic-packaged-client048-check'

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('phase',choices=['save','reopened','clear'])
    args=parser.parse_args();root=ROOT/'artifacts/client048/ui-check';session=strict_json((root/'session.json').read_bytes())
    url=urlsplit(session['origin'])
    if url.hostname!='127.0.0.1' or session['version']!='0.1.2-client048':raise RuntimeError('Expected own isolated 048 process')
    def call(path,body=None,token=None):
        connection=HTTPConnection(url.hostname,url.port,timeout=10)
        headers={'Content-Type':'application/json','Origin':session['origin']}
        if token:headers['X-Workbench-Token']=token
        connection.request('GET' if body is None else 'POST','/api/v1/'+path,None if body is None else canonical(body),headers)
        response=connection.getresponse();raw=response.read();status=response.status;connection.close()
        if KEY.encode() in raw:raise RuntimeError('Credential unexpectedly returned')
        data=strict_json(raw)
        if status>=400:raise RuntimeError(data['error']['code'])
        return data
    boot=call('bootstrap');token=boot['session_token'];checks={}
    if args.phase=='save':
        config=load_config(ROOT/'config/agents.deepseek-nature046.json');config.update(endpoint=ENDPOINT,model='synthetic-client048-test')
        call('preferences',config,token);saved=call('credentials/save',{'endpoint':ENDPOINT,'api_key':KEY},token)
        checks['saved_by_packaged_backend']=saved['saved'] and saved['supported']
        encrypted=root/'credentials'/(hashlib.sha256(ENDPOINT.encode()).hexdigest()+'.dpapi')
        checks['ciphertext_not_plaintext']=encrypted.exists() and KEY.encode() not in encrypted.read_bytes()
    elif args.phase=='reopened':
        checks['config_restored']=boot['config']['endpoint']==ENDPOINT
        checks['key_restored_by_new_process']=call('credentials/status',{'endpoint':ENDPOINT},token)['saved']
        prior=strict_json((root.parent/'save.json').read_bytes())
        checks['separate_process']=prior['pid']!=session['pid']
        checks['other_endpoint_not_reused']=not call('credentials/status',{'endpoint':ENDPOINT+'/other'},token)['saved']
        checks['no_txt_control']='key-file' not in (ROOT/'dist/WorldBuilder048/_internal/web/index.html').read_text('utf-8')
    else:
        checks['synthetic_key_cleared']=not call('credentials/clear',{'endpoint':ENDPOINT},token)['saved']
        call('preferences',load_config(ROOT/'config/agents.deepseek-nature046.json'),token)
    checks['no_key_in_preferences_or_jobs']=all(KEY.encode() not in path.read_bytes() for path in [root/'preferences.json',*root.glob('runs/*/*.json')])
    report={'phase':args.phase,'pid':session['pid'],'status':'pass' if all(checks.values()) else 'fail','checks':checks,'network_calls':0,'credential_kind':'synthetic, never a real API key'}
    target=root.parent/(args.phase+'.json')
    if target.exists():raise RuntimeError('Keep existing evidence; do not overwrite')
    write_json(target,report);print(canonical(report).decode('utf-8'))
    return 0 if all(checks.values()) else 1

if __name__=='__main__':raise SystemExit(main())
