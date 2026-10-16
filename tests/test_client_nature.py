"""047 transport/contract checks. Stubbed jobs are not geometry evidence."""
from copy import deepcopy
import json
from pathlib import Path
import time
import pytest
from world_builder.agents.contracts import AgentError,ROOT,canonical
from world_builder.agents.providers import Completion,load_config
from world_builder.agents.runtime import write_json
from world_builder.workbench import nature
from world_builder.workbench.jobs import JobService,ServiceError,TERMINAL


def config():return load_config(ROOT/'config/agents.deepseek-nature046.json')
def wait(service,id):
    for _ in range(100):
        job=service.detail(id)
        if job['status'] in TERMINAL:return job
        time.sleep(.01)
    raise AssertionError('stub job did not finish')


def stub(spec,cfg,provider,output,cancelled,phase):
    output=Path(output);output.mkdir(parents=True)
    write_json(output/'accepted_parameters.json',spec.get('parameters',nature.reference()['parameters']))
    return {'network_calls':0,'stub':True}


@pytest.fixture
def service(tmp_path):
    svc=JobService(tmp_path,config(),execute=stub)
    yield svc
    svc.close()


def test_reference_and_31_declared_fields():
    p=nature.reference()['parameters'];nature.check_parameters(p)
    assert len(nature.fields())==31
    for f in nature.fields():assert f['min']<=f['max']


def test_only_declared_changes_are_applied():
    original=nature.reference()['parameters'];saved=deepcopy(original)
    updated,actual=nature.change_parameters(original,{'B.trees':400,'D.castle.yaw':-4})
    assert original==saved and updated['B']['trees']==400 and updated['D']['castle']['yaw']==-4
    assert set(actual)=={'B.trees','D.castle.yaw'}


@pytest.mark.parametrize('changes',[{},None,{'B.trees':True},{'B.trees':299},{'B.trees':441},{'B.trees':300.5},
    {'B.trees':'400'},{'B.rationale':1},{'D.districts.west_low.x':600},{'unknown':1}])
def test_bad_changes_rejected(changes):
    with pytest.raises(AgentError):nature.change_parameters(nature.reference()['parameters'],changes)


def test_noop_rejected():
    p=nature.reference()['parameters']
    with pytest.raises(AgentError,match='相同'):nature.change_parameters(p,{'B.trees':p['B']['trees']})


def test_fixture_adjust_replay_and_history(service):
    first=wait(service,service.create({'pipeline':'nature047','mode':'fixture'})['id'])
    assert first['status']=='succeeded' and first['region_m']==768 and first['parameters']
    original=deepcopy(first['parameters'])
    second=wait(service,service.create({'pipeline':'nature047','mode':'adjust','source_id':first['id'],'changes':{'B.trees':400}})['id'])
    assert second['source_id']==first['id'] and second['parameters']['B']['trees']==400
    assert service.detail(first['id'])['parameters']==original
    replay=wait(service,service.create({'mode':'replay','replay_id':second['id']})['id'])
    # No model records are needed for deterministic adjustments or fixtures.
    assert replay['status']=='succeeded' and replay['source_id']==first['id']
    assert replay['parameters']==second['parameters']


@pytest.mark.parametrize('patch',[{'region_m':512},{'seed':47},{'minecraft':True},{'unity':False},{'region_m':True}])
def test_nature_fixed_profile_rejects_incompatible_inputs(service,patch):
    with pytest.raises(ServiceError):service.create({'pipeline':'nature047','mode':'fixture',**patch})
    assert not service.list()


def test_legacy_cannot_invoke_adjustments(service):
    with pytest.raises(ServiceError):service.create({'mode':'adjust','changes':{'B.trees':400}})


def test_config_cap_does_not_mutate_preferences():
    old=config();new=nature.effective_config(old)
    assert old['limits']['max_calls']==10 and new['limits']['max_calls']==6


def test_unsupported_scope_stops_before_geometry_or_other_calls(tmp_path):
    class Provider:
        network=False
        def complete(self,request,**kwargs):
            assert request['stage']=='A'
            return Completion(canonical({**{k:request[k] for k in ('contract_version','stage','request_id','scope_id')},
                       'payload':{'supported':False,'reason':'本周不支持现代机场。'}}),'test',0,0,'synthetic')
    run=nature.ClientNatureSupervisor(Provider(),config(),tmp_path/'run',cancelled=lambda:False,on_phase=lambda phase:None)
    with pytest.raises(AgentError,match='超出本周'):run.run('生成现代机场',nature.recipes())
    assert run.calls==1 and run.network_calls==0 and not (run.root/'nature_geometry.json').exists()


def test_cancel_before_construction(tmp_path):
    with pytest.raises(AgentError,match='取消'):
        nature.execute({'mode':'fixture'},config(),None,tmp_path/'run',lambda:True,lambda phase:None)


def test_replay_rejects_changed_context_without_touching_source(service):
    first=wait(service,service.create({'pipeline':'nature047','mode':'fixture'})['id'])
    path=service.root/first['id']/'input.json'
    spec=json.loads(path.read_text('utf-8'));spec['generation_context']['builder']='different-version'
    write_json(path,spec)
    original=path.read_bytes()
    with pytest.raises(ServiceError) as error:service.create({'mode':'replay','replay_id':first['id']})
    assert error.value.code=='replay.context' and len(service.list())==1 and path.read_bytes()==original


def test_failed_adjustment_preserves_source(tmp_path):
    def execute(spec,cfg,provider,output,cancelled,phase):
        if spec['mode']=='adjust':raise AgentError('nature.test_infeasible','Synthetic infeasible combination')
        return stub(spec,cfg,provider,output,cancelled,phase)
    service=JobService(tmp_path,config(),execute=execute)
    try:
        first=wait(service,service.create({'pipeline':'nature047','mode':'fixture'})['id'])
        before=(tmp_path/first['id']/'output/accepted_parameters.json').read_bytes()
        second=wait(service,service.create({'pipeline':'nature047','mode':'adjust','source_id':first['id'],'changes':{'B.trees':400}})['id'])
        assert second['status']=='failed' and second['error']['code']=='nature.test_infeasible'
        assert service.detail(first['id'])['status']=='succeeded'
        assert (tmp_path/first['id']/'output/accepted_parameters.json').read_bytes()==before
    finally:service.close()


def test_nature_credentials_not_persisted_or_retained(tmp_path):
    class Provider:key=''
    provider=Provider()
    def factory(mode,cfg,api_key,replay_path):provider.key=api_key;return provider
    service=JobService(tmp_path,config(),execute=stub,provider_factory=factory)
    try:
        job=wait(service,service.create({'pipeline':'nature047','mode':'api','api_key':'synthetic-client-secret'})['id'])
        assert job['status']=='succeeded' and provider.key==''
        for path in tmp_path.rglob('*.json'):assert b'synthetic-client-secret' not in path.read_bytes()
    finally:service.close()
