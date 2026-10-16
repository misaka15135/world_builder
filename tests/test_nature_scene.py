"""046 geometry tests are independent of the frozen 045 real run."""
from copy import deepcopy
import json
import math
import struct
from types import SimpleNamespace
import pytest
from world_builder.agents.contracts import AgentError, ROOT, validate_schema
from world_builder.agents.nature_mesh import transform, cuboid, glb
from world_builder.agents.nature_scene import (
    BASE, LAYOUT, NatureSupervisor, Terrain, synthetic_parameters, scatter,
    source_routes, river_x, natural_height,
)
from world_builder.agents.nature_export import PALETTE
from world_builder.agents.providers import load_config
from world_builder.agents.style_scene import box


def test_scatter_is_separated_and_not_lattice():
    params=synthetic_parameters();sites=scatter(params)
    assert len(sites)==64 and sites==scatter(params)
    assert len({round(s['yaw']/5) for s in sites})>20
    for i,s in enumerate(sites):
        assert abs(s['x']-river_x(params['B'],s['y']))>s['radius']+params['B']['river_width']/2+20
        assert all(math.dist((s['x'],s['y']),(t['x'],t['y']))>=s['radius']+t['radius']+3 for t in sites[:i])


def test_duplicate_district_rejected():
    params=synthetic_parameters();params['D']['districts'][0]=deepcopy(params['D']['districts'][1])
    with pytest.raises(AgentError,match='unique districts'):scatter(params)


def test_parameter_schemas_and_bounds():
    params=synthetic_parameters();validate_schema(params['B'],BASE);validate_schema(params['D'],LAYOUT)
    params['D']['districts'][0]['x']=600
    with pytest.raises(AgentError,match='west_low'):scatter(params)


def test_grading_is_continuous_between_pad_influences():
    base=synthetic_parameters()['B']
    pads=[{'x':100,'y':210,'radius':8,'blend':14,'height':12},
          {'x':140,'y':210,'radius':8,'blend':14,'height':17}]
    terrain=Terrain(base,pads)
    assert terrain.sample(100,210)==12 and terrain.sample(140,210)==17
    assert abs(terrain.height(120-.0001,210)-terrain.height(120+.0001,210))<.001
    for y in range(0,769,16):
        assert terrain.height(river_x(base,y),y)==pytest.approx(2)


def test_yaw_mesh_and_gltf_float32_bounds():
    pose={'x':100,'y':200,'yaw':37,'ox':0,'oy':0,'dz':10}
    p=cuboid(box('test',[0,0,4,3],0,2,'minecraft:stone_bricks','test'),pose)
    assert len(p['indices'])==36
    assert p['bounds_wir_m'][0][0]<100
    assert transform([0,0,0],pose)==[100,200,10]
    encoded,_=glb([p],PALETTE)
    assert encoded[:4]==b'glTF' and struct.unpack_from('<I',encoded,8)[0]==len(encoded)
    size=struct.unpack_from('<I',encoded,12)[0];document=json.loads(encoded[20:20+size])
    assert document['accessors'][2]['componentType']==5125
    for i in range(0,len(p['indices']),3):
        a,b,c=(p['vertices'][p['indices'][i+j]] for j in range(3))
        cross=[(b[1]-a[1])*(c[2]-a[2])-(b[2]-a[2])*(c[1]-a[1]),
               (b[2]-a[2])*(c[0]-a[0])-(b[0]-a[0])*(c[2]-a[2]),
               (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])]
        assert sum(x*y for x,y in zip(cross,p['normals'][p['indices'][i]]))>0


def test_water_requires_bridge():
    base=synthetic_parameters()['B'];x=river_x(base,288)
    planner=SimpleNamespace(terrain=SimpleNamespace(base=base,sample=lambda x,y:5),routes=[{'id':'bad','points':[[x-20,288],[x+20,288]]}])
    with pytest.raises(AgentError,match='unsupported water'):source_routes(planner,[])


def test_flat_longitudinal_route_still_rejects_steep_cross_slope():
    base=synthetic_parameters()['B']
    planner=SimpleNamespace(terrain=SimpleNamespace(base=base,sample=lambda x,y:5,grade=lambda x,y:1.3),
                            routes=[{'id':'bad_cross_slope','points':[[100,200],[100,204]]}])
    with pytest.raises(AgentError,match='full triangle grade'):source_routes(planner,[])


def test_new_region_is_version_isolated(tmp_path):
    config=load_config(ROOT/'config/agents.deepseek-nature046.json')
    supervisor=NatureSupervisor(None,config,tmp_path/'new',region_m=768,seed=46)
    assert supervisor.region_m==768
    assert supervisor.request_schema()['properties']['region_m']['minimum']==768
    with pytest.raises(AgentError,match='exactly 768'):NatureSupervisor(None,config,tmp_path/'bad',region_m=512)
