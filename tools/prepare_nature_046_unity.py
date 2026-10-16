"""Prepare separate Nature046 scene data and representative physical routes."""
import argparse
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from world_builder.agents.contracts import ROOT, strict_json
from world_builder.agents.runtime import write_json
from world_builder.agents.nature_mesh import transform
from prepare_style_042_unity import target_path


def vector(p):return {'x':p[0],'y':p[2],'z':p[1]}
def offset(p,x,y,z):return [p[0]+x,p[1]+y,p[2]+z]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',type=Path,required=True)
    source=parser.parse_args().source.resolve()
    destination=ROOT/'adapters/unity/style042_project/Assets/Generated/Nature046'
    destination.mkdir(parents=True,exist_ok=True)
    for name in ('scene.glb','manifest.json'):shutil.copyfile(source/'unity'/name,destination/name)
    geometry=strict_json((source/'nature_geometry.json').read_bytes())
    manifest=strict_json((source/'unity/manifest.json').read_bytes())
    write_json(destination/'unity_bounds.json',{'pieces':[{'name':p['name'],'min':vector(p['bounds_wir_m'][0]),'max':vector(p['bounds_wir_m'][1])} for p in manifest['pieces']]})
    representatives={}
    for gid,local in sorted(geometry['local_buildings'].items()):representatives.setdefault(local['recipe_id'],gid)
    selected=set(representatives.values());paths=[]
    for r in geometry['walking']['routes']:
        gid=r['group']
        if gid not in selected:continue
        local=geometry['local_buildings'][gid]
        cells,critical=target_path({**r,'cells':r['local_cells']},{'parts':local['parts'],'buildings':{gid:local['semantic']}})
        cells=[transform(p,geometry['poses'][gid]) for p in cells]
        paths.append({'room':gid+':'+r['room'],'level':r['level'],'critical_indices':critical,'points':[vector(p) for p in cells]})
    # Entire main roads, not just bridge midspans; one doorway approach per recipe.
    for r in geometry['network']['routes']:
        if r['id'].startswith('entry_') and r['id'][6:] not in selected:continue
        cells=r['cells'];paths.append({'room':r['id'],'level':0,'critical_indices':[len(cells)-1],'points':[vector(p) for p in cells]})
    write_json(destination/'unity_paths.json',{'paths':paths,'representatives':representatives,
               'scope':'Every room of one representative per reused recipe + keep; two complete slope avenues, two complete river crossings, castle approach and eight entry roads'})
    view=geometry['view'];v,c,r=view['village'],view['castle'],view['river']
    write_json(destination/'city_view.json',{'region_m':768,'overviewPosition':vector([1080,-310,760]),'overviewTarget':vector([384,380,25]),
        'streetPosition':vector(offset(v,65,-80,58)),'streetTarget':vector(offset(v,0,0,2)),
        'riverPosition':vector(offset(r,75,-90,48)),'riverTarget':vector(offset(r,0,35,-2)),
        'castlePosition':vector(offset(c,100,-135,80)),'castleTarget':vector(offset(c,0,0,8)),
        'spawnPosition':vector(offset(view['spawn'],0,0,1.7))})
    print('Nature046',manifest['piece_count'],'source meshes;',len(paths),'target routes;',len(geometry['walking']['routes']),'source room routes')


if __name__=='__main__':main()
