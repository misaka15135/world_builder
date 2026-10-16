"""048 DPAPI/transport/provider checks use only synthetic keys, never paid APIs."""
from http.client import HTTPConnection
import json
from pathlib import Path
import subprocess
import sys
import time
import pytest
from world_builder.agents.contracts import ROOT,AgentError,canonical
from world_builder.agents.providers import load_config
from world_builder.agents.runtime import write_json
from world_builder.desktop.credentials import CredentialStore
from world_builder.desktop.app import DesktopSession
from world_builder.workbench.jobs import JobService,ServiceError,TERMINAL

pytestmark=pytest.mark.skipif(sys.platform!='win32',reason='Windows current-user DPAPI')
ENDPOINT='https://example.test/v1/chat/completions'
KEY='synthetic-dpapi-client048-secret'

def cfg():
    config=load_config(ROOT/'config/agents.deepseek-nature046.json')
    config.update(endpoint=ENDPOINT,model='synthetic-model');return config

def wait(service,id):
    for _ in range(200):
        job=service.detail(id)
        if job['status'] in TERMINAL:return job
        time.sleep(.01)
    raise AssertionError('Stub did not finish')

def test_encrypted_endpoint_bound_replace_clear_and_cross_process(tmp_path):
    store=CredentialStore(tmp_path/'credentials');assert store.get(ENDPOINT) is None
    store.save(ENDPOINT,KEY)
    assert store.status(ENDPOINT)=={'supported':True,'saved':True}
    assert KEY.encode() not in store.path(ENDPOINT).read_bytes() and ENDPOINT.encode() not in store.path(ENDPOINT).read_bytes()
    assert store.get(ENDPOINT+'/different') is None
    code='from world_builder.desktop.credentials import CredentialStore;import sys;assert CredentialStore(sys.argv[1]).get(sys.argv[2])==sys.argv[3];print("cross-process-ok")'
    result=subprocess.run([sys.executable,'-c',code,str(store.root),ENDPOINT,KEY],capture_output=True,text=True)
    assert result.returncode==0 and result.stdout.strip()=='cross-process-ok'
    store.save(ENDPOINT,KEY+'-replacement');assert CredentialStore(store.root).get(ENDPOINT)==KEY+'-replacement'
    store.clear(ENDPOINT);assert not store.status(ENDPOINT)['saved'] and not list(store.root.glob('pending-*'))

def test_corruption_is_not_silently_missing_or_plaintext(tmp_path):
    store=CredentialStore(tmp_path);store.save(ENDPOINT,KEY)
    store.path(ENDPOINT).write_bytes(b'invalid encrypted record')
    assert store.status(ENDPOINT)['error']
    with pytest.raises(AgentError,match='无法读取'):store.get(ENDPOINT)
    store.save(ENDPOINT,KEY+'-recovered');assert store.get(ENDPOINT)==KEY+'-recovered'

def test_desktop_close_reopen_preserves_but_bootstrap_never_returns_key(tmp_path):
    first=DesktopSession(tmp_path)
    try:
        first.service.save_preferences(cfg());first.service.credential_action('save',{'endpoint':ENDPOINT,'api_key':KEY})
    finally:first.close()
    second=DesktopSession(tmp_path)
    try:
        assert second.service.credential_action('status',{'endpoint':ENDPOINT})['saved']
        assert second.service.credential_store.get(ENDPOINT)==KEY
        connection=HTTPConnection('127.0.0.1',second.server.server_port)
        connection.request('GET','/api/v1/bootstrap');response=connection.getresponse();raw=response.read();connection.close()
        assert response.status==200 and KEY.encode() not in raw and json.loads(raw)['credential_storage']=='windows_dpapi'
        assert KEY not in (tmp_path/'preferences.json').read_text('utf-8')
    finally:second.close()

def test_provider_uses_exact_endpoint_only_and_one_time_key_overrides(tmp_path):
    captured=[]
    class Provider:key=''
    def factory(mode,config,api_key,replay_path):
        captured.append((mode,config['endpoint'],api_key));provider=Provider();provider.key=api_key;return provider
    def stub(spec,config,provider,output,cancelled,phase):
        (Path(output)/'calls').mkdir(parents=True);write_json(Path(output)/'accepted_parameters.json',{})
        return {'synthetic':True}
    store=CredentialStore(tmp_path/'credentials');store.save(ENDPOINT,KEY)
    service=JobService(tmp_path/'runs',cfg(),credential_store=store,execute=stub,provider_factory=factory)
    try:
        base={'pipeline':'nature047','mode':'api','config':cfg()}
        first=wait(service,service.create(base)['id']);assert first['status']=='succeeded' and captured[-1][2]==KEY
        wait(service,service.create({**base,'api_key':'one-time-override'})['id']);assert captured[-1][2]=='one-time-override'
        other=cfg();other['endpoint']=ENDPOINT+'/other'
        wait(service,service.create({**base,'config':other})['id']);assert captured[-1][2] is None
        wait(service,service.create({'mode':'replay','replay_id':first['id']})['id']);assert captured[-1][0]=='replay' and captured[-1][2] is None
        for path in (tmp_path/'runs').rglob('*.json'):assert KEY.encode() not in path.read_bytes()
    finally:service.close()

@pytest.mark.parametrize('action,body',[('save',{}),('save',{'endpoint':ENDPOINT,'api_key':''}),
    ('save',{'endpoint':ENDPOINT,'api_key':'a\nb'}),('save',{'endpoint':ENDPOINT,'api_key':True}),
    ('save',{'endpoint':'http://example.test','api_key':KEY}),('save',{'endpoint':'https://user:pass@example.test','api_key':KEY}),
    ('status',{'endpoint':ENDPOINT,'extra':KEY}),('save',{'endpoint':ENDPOINT+'/different','api_key':KEY})])
def test_reject_invalid_credential_without_writing(tmp_path,action,body):
    service=JobService(tmp_path/'runs',cfg(),credential_store=CredentialStore(tmp_path/'credentials'))
    try:
        with pytest.raises(ServiceError):service.credential_action(action,body)
        assert not list(tmp_path.rglob('*.dpapi'))
    finally:service.close()

def test_http_csrf_no_readback_and_no_public_credential_file(tmp_path):
    session=DesktopSession(tmp_path);session.service.save_preferences(cfg())
    def call(action,body,*,token=None,origin=None):
        connection=HTTPConnection('127.0.0.1',session.server.server_port,timeout=5)
        headers={'Content-Type':'application/json'}
        if token:headers['X-Workbench-Token']=token
        if origin:headers['Origin']=origin
        connection.request('POST','/api/v1/credentials/'+action,canonical(body),headers)
        response=connection.getresponse();raw=response.read();status=response.status;connection.close()
        assert KEY.encode() not in raw
        return status,json.loads(raw)
    try:
        body={'endpoint':ENDPOINT,'api_key':KEY}
        assert call('save',body)[0]==403
        assert call('save',body,token=session.server.token,origin='https://other.test')[0]==403
        assert call('save',body,token=session.server.token,origin=session.server.origin)==(200,{'supported':True,'saved':True})
        assert call('status',{'endpoint':ENDPOINT},token=session.server.token)[1]['saved']
        assert session.service.list()==[]
        connection=HTTPConnection('127.0.0.1',session.server.server_port)
        connection.request('GET','/credentials/'+session.service.credential_store.path(ENDPOINT).name)
        response=connection.getresponse();assert response.status==404;response.read();connection.close()
        assert call('clear',{'endpoint':ENDPOINT},token=session.server.token)[1]['saved'] is False
    finally:session.close()

def test_web_or_unsupported_store_never_falls_back_to_plaintext(tmp_path):
    service=JobService(tmp_path,cfg())
    try:
        assert service.credential_action('status',{'endpoint':ENDPOINT})=={'supported':False,'saved':False}
        with pytest.raises(ServiceError):service.credential_action('save',{'endpoint':ENDPOINT,'api_key':KEY})
    finally:service.close()

def test_txt_input_and_file_reader_removed():
    html=(ROOT/'web/index.html').read_text('utf-8');js=(ROOT/'web/features/settings.js').read_text('utf-8')
    assert 'key-file' not in html+js and 'TextDecoder' not in js
    assert 'remember-key' in html and 'clear-key' in html
