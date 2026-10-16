"""047 bounded client profile; frozen 046 geometry is reused, never rewritten."""
from copy import deepcopy
import hashlib
import time
from pathlib import Path

from world_builder.agents.contracts import ROOT, AgentError, digest, strict_json, obj, string, canonical
from world_builder.agents.providers import load_config
from world_builder.agents.runtime import Supervisor, write_json
from world_builder.agents.nature_scene import NatureSupervisor, BASE, LAYOUT, LIMITS, BUILDER, build_nature, check_parameters
from world_builder.agents.nature_export import save_nature_world

PROFILE='nature047'
VERSION='0.1.0-client047'
PROMPT='生成768米魔法山谷聚落，保留四个聚落共64栋住宅商铺、东北城堡与两座桥。山势起伏，河道弯曲，房屋错落，入口和道路可通行。'


def reference():return strict_json((ROOT/'examples/nature047_reference.json').read_bytes())
def recipes():return strict_json((ROOT/'examples/nature046_recipes.json').read_bytes())


def generation_context():
    return {'profile_version':VERSION,'builder':BUILDER,'recipes_sha256':digest(recipes()),'reference_sha256':digest(reference()),
            'skills':{s:digest((ROOT/(f'skills/world-client-047/{s}.md' if s=='A' else f'skills/world-nature-046/{s}.md')).read_text('utf-8')) for s in ('A','B','D','F')}}


def fields():
    names={'west_height':'西部山丘高度','north_height':'北部山丘高度','east_height':'东部山丘高度','river_bend':'河流弯曲幅度',
           'river_width':'河道宽度','river_phase_deg':'河流相位（度）','valley_width':'河谷过渡宽度','trees':'树木数量'}
    result=[{'path':'B.'+k,'label':v,'min':BASE['properties'][k]['minimum'],'max':BASE['properties'][k]['maximum'],'group':'地形与树林'} for k,v in names.items()]
    labels={'west_low':'西南聚落','west_high':'西北聚落','east_low':'东南聚落','east_high':'东北聚落'}
    for district,(x0,x1,y0,y1) in LIMITS.items():
        for name,label,lo,hi in [('x','东西位置',x0,x1),('y','南北位置',y0,y1),('radius','散布半径',98,112),
                                  ('home_percent','额外配方住宅权重（%）',40,60),('yaw_jitter','朝向偏转（度）',12,28)]:
            result.append({'path':f'D.districts.{district}.{name}','label':label,'min':lo,'max':hi,'group':labels[district]})
    for name,label,lo,hi in [('x','东西位置',580,650),('y','南北位置',650,680),('yaw','旋转角度（度）',-22,22)]:
        result.append({'path':'D.castle.'+name,'label':label,'min':lo,'max':hi,'group':'城堡'})
    return result


def metadata():
    return {'id':PROFILE,'version':VERSION,'prompt':PROMPT,'region_m':768,'seed':46,'fields':fields(),
            'reference':reference(),'default_config':load_config(ROOT/'config/agents.deepseek-nature046.json'),
            'scope':'固定768米、四聚落64栋、两桥、一城堡；E沿用045录制配方。参数组合仍须可行性验证。'}


def change_parameters(parameters,changes):
    if not isinstance(changes,dict) or not changes:raise AgentError('adjust.empty','请至少修改一个参数。')
    schema={f['path']:f for f in fields()};updated=deepcopy(parameters);actual={}
    for path,value in changes.items():
        field=schema.get(path)
        if not field:raise AgentError('adjust.field','未知或不可调整的参数。')
        if type(value) is not int or not field['min']<=value<=field['max']:
            raise AgentError('adjust.range',f"{field['group']} / {field['label']} 须为 {field['min']}—{field['max']} 的整数。")
        segments=path.split('.');target=updated[segments[0]]
        if segments[1]=='districts':target=next(d for d in target['districts'] if d['id']==segments[2])
        elif segments[1]=='castle':target=target['castle']
        key=segments[-1]
        if target[key]!=value:actual[path]={'before':target[key],'after':value}
        target[key]=value
    if not actual:raise AgentError('adjust.unchanged','参数与原版本相同，无需重新生成。')
    check_parameters(updated)
    return updated,actual


def effective_config(config):
    config=deepcopy(config)
    for key,cap in {'max_calls':6,'max_total_tokens':150000,'max_output_tokens':4000,'attempts':2,'workers':1}.items():
        config['limits'][key]=min(config['limits'][key],cap)
    return config


class ClientNatureSupervisor(NatureSupervisor):
    contract_version=VERSION
    def __init__(self,provider,config,output,*,cancelled,on_phase):
        # Resource paths work in both a checkout and the frozen desktop bundle.
        Supervisor.__init__(self,provider,config,output,region_m=512,seed=46,cancelled=cancelled)
        self.region_m=768;self.on_phase=on_phase
        for s in ('B','D','F'):self.skills[s]=(ROOT/f'skills/world-nature-046/{s}.md').read_text('utf-8')
        self.skills['A']=(ROOT/'skills/world-client-047/A.md').read_text('utf-8')
    def request_schema(self):
        schema=super().request_schema();schema['properties']['contract_version']={'const':VERSION};return schema
    def response_contract(self,stage,plans,request_id=None,scope_id=None):
        schema=super().response_contract('B' if stage=='A' else stage,plans,request_id,scope_id)
        schema['properties']['contract_version']={'const':VERSION};schema['properties']['stage']={'const':stage}
        if stage=='A':schema['properties']['payload']=obj(supported={'type':'boolean'},reason=string(300))
        return schema
    def run(self,prompt,reuse):
        self.prompt=prompt
        scope=self.ask('A',{})
        if not scope['supported']:raise AgentError('nature.scope_unsupported','超出本周山谷模式范围：'+scope['reason'])
        accepted,geometry=super().run(prompt,reuse)
        accepted['contract_version']=VERSION
        accepted['skill_hashes']['A']=digest(self.skills['A'])
        write_json(self.root/'accepted.json',accepted)
        return accepted,geometry
    def event(self,event,**data):
        super().event(event,**data)
        if event=='construction_started':self.on_phase('constructing')
        elif event=='request':self.on_phase('reviewing' if data.get('stage')=='F' else 'planning')


def execute(spec,config,provider,output,cancelled,on_phase):
    output=Path(output);started=time.monotonic();supervisor=None
    def checkpoint():
        if cancelled():raise AgentError('execution.cancelled','已取消；旧版本保留，未接受的产物不会标为完成。')
    try:
        checkpoint();reuse=recipes()
        if spec['mode']=='api' or (spec['mode']=='replay' and spec['source_mode']=='api'):
            supervisor=ClientNatureSupervisor(provider,config,output,cancelled=cancelled,on_phase=on_phase)
            accepted,geometry=supervisor.run(spec['prompt'],reuse)
        else:
            output.mkdir(parents=True,exist_ok=False)
            parameters=deepcopy(spec['parameters'])
            write_json(output/'accepted_parameters.json',parameters)
            with (output/'events.jsonl').open('ab') as stream:
                stream.write(canonical({'event':'construction_started','source_mode':spec.get('source_mode',spec['mode']),'network_calls':0})+b'\n')
            on_phase('constructing');geometry=build_nature(parameters,reuse['recipes'])
            accepted={'contract_version':VERSION,'prompt':spec['prompt'],'region_m':768,'seed':46,
                      'plans':{**parameters,'E':reuse['recipes']},'source':spec.get('source_mode',spec['mode']),
                      'source_job_id':spec.get('source_id'),'changes':spec.get('changes',{}),
                      'reference_provenance':spec.get('reference_provenance'),'reused_E_provenance':{k:v for k,v in reuse.items() if k!='recipes'},
                      'model_review':'not_run; local construction validation only'}
            write_json(output/'accepted.json',accepted);write_json(output/'nature_geometry.json',geometry)
        if len(geometry['sites'])>config['limits']['max_sites'] or len(geometry['parts'])>config['limits']['max_parts']:
            raise AgentError('nature.component_budget','案例构件或场地数量超出设置中的预算。')
        checkpoint();on_phase('compiling')
        result=save_nature_world(accepted,geometry,output)
        # Once a validated snapshot is committed, late cancellation does not
        # relabel that complete snapshot as a half-written world.
        result.update(supervisor.usage() if supervisor else {'network_calls':0,'provider_calls':0,'accounted_tokens':0,'elapsed_s':round(time.monotonic()-started,3)})
        result.update(mode=spec['mode'],profile=PROFILE,profile_version=VERSION,source_job_id=spec.get('source_id'),
                      source_report=geometry['report'],target_load='not_run',walkthrough='not_run',minecraft='not_supported_in_this_profile')
        if spec['mode']=='replay':
            original=output.parent.parent/spec['replay_id']/'output'
            checks={name:hashlib.sha256((original/name).read_bytes()).digest()==hashlib.sha256((output/name).read_bytes()).digest()
                    for name in ('scene.worldpkg','unity/scene.glb','nature_geometry.json')}
            checks['zero_network']=result['network_calls']==0
            write_json(output/'replay_validation.json',{'status':'pass' if all(checks.values()) else 'fail','checks':checks})
            if not all(checks.values()):raise AgentError('replay.different','回放与原版本的源几何或导出文件不一致。')
        write_json(output/'result.json',result)
        return result
    except Exception as error:
        write_json(output/'result.json',{'status':'failed','code':getattr(error,'code','execution.error'),'message':str(error),
                   **(supervisor.usage() if supervisor else {'network_calls':0,'provider_calls':0,'accounted_tokens':0})})
        raise
