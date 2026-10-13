"""Prepare the isolated Unity project from immutable 042 source exports."""
from pathlib import Path
import sys
import shutil
from collections import deque
import math
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from world_builder.agents.contracts import ROOT,strict_json
from world_builder.agents.runtime import write_json


def target_path(route,geometry):
    """Climb the full stair centreline before routing across the upper floor."""
    cells=route["cells"]
    if route["level"]==0:
        return cells,[len(cells)-1]
    semantic=geometry["buildings"][route["group"]]
    design=semantic["design"]
    stair=design["stair"]
    cx=stair["x0"]+stair["width_m"]/2
    y0=stair["y0"]
    top=round(1.3+stair["rise_m"],4)
    prefix=[]
    for p in cells:
        if p[2]>1.35:break
        prefix.append(p)
    prefix.append([cx,y0-.4,1.3])
    for i in range(stair["steps"]):
        prefix.append([cx,y0+stair["run_m"]*(i+.5)/stair["steps"],1.3+stair["rise_m"]*(i+1)/stair["steps"]])
    landing=[cx,y0+stair["run_m"]+stair["landing_m"]*.5,top]
    prefix.append(landing)
    critical=len(prefix)-1
    boxes=[p["bounds_wir_m"] for p in geometry["parts"] if p["block"]!="minecraft:water"]
    x0,n0,x1,n1=design["outline"]
    free=set()
    for ix in range(math.floor(x0*10),math.ceil(x1*10)+1):
        for iy in range(math.floor(n0*10),math.ceil(n1*10)+1):
            x,y=ix/10,iy/10
            near=[(a,b) for a,b in boxes if a[0]<x+.28 and b[0]>x-.28 and a[1]<y+.28 and b[1]>y-.28]
            support=any(a[0]<=x<b[0] and a[1]<=y<b[1] and abs(b[2]-top)<.001 for a,b in near)
            if support and not any(a[2]<top+1.8 and b[2]>top+.035 for a,b in near):free.add((ix,iy))
    start=(round(landing[0]*10),round(landing[1]*10))
    target=(round(cells[-1][0]*10),round(cells[-1][1]*10))
    if start not in free or target not in free:raise ValueError("Upper landing/room has no source-supported floor: "+route["room"])
    previous={start:None};queue=deque([start])
    while queue and target not in previous:
        p=queue.popleft()
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            node=(p[0]+dx,p[1]+dy)
            if node in free and node not in previous:previous[node]=p;queue.append(node)
    if target not in previous:raise ValueError("No upper floor route from landing: "+route["room"])
    tail=[];p=target
    while p is not None:tail.append([p[0]/10,p[1]/10,top]);p=previous[p]
    path=prefix+list(reversed(tail))[1:]
    return path,[critical,len(path)-1]


def main():
    for case,folder in (("Baseline","baseline-v3"),("API","arcane-v3")):
        source=ROOT/"artifacts/style042"/folder/"unity"
        destination=ROOT/"adapters/unity/style042_project/Assets/Generated"/case
        destination.mkdir(parents=True,exist_ok=True)
        for name in ("scene.glb","manifest.json"):
            shutil.copyfile(source/name,destination/name)
        routes=strict_json((source/"routes.json").read_bytes())
        geometry=strict_json((source.parent/"style_geometry.json").read_bytes())
        paths=[]
        for r in routes["routes"]:
            path,critical=target_path(r,geometry)
            paths.append({"room":r["room"],"level":r["level"],"critical_indices":critical,
                          "points":[{"x":p[0],"y":p[2],"z":p[1]} for p in path]})
        converted={"method":"full_stair_centreline_and_supported_upper_floor_v1","paths":paths}
        write_json(destination/"unity_paths.json",converted)
        manifest=strict_json((source/"manifest.json").read_bytes())
        bounds={"pieces":[{"name":p["name"],"min":{"x":p["bounds_wir_m"][0][0],"y":p["bounds_wir_m"][0][2],"z":p["bounds_wir_m"][0][1]},
                           "max":{"x":p["bounds_wir_m"][1][0],"y":p["bounds_wir_m"][1][2],"z":p["bounds_wir_m"][1][1]}}
                          for p in manifest["pieces"]]}
        write_json(destination/"unity_bounds.json",bounds)
        print(case,manifest["piece_count"],"pieces",len(routes["routes"]),"routes")


if __name__=="__main__":main()
