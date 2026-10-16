"""Same 0.1m support/clearance graph as 042, with exact local XY broad phase."""
from collections import defaultdict, deque
import math
from .validation import require

STEP=.1
RADIUS=.30
HEIGHT=1.8
BUCKET=.5


def walking_routes(geometry):
    result=[]
    all_boxes=[(p["bounds_wir_m"][0],p["bounds_wir_m"][1]) for p in geometry["parts"] if p["block"]!="minecraft:water"]
    for group,semantic in geometry["buildings"].items():
        design=semantic["design"];x0,y0,x1,y1=design["outline"]
        boxes=[(a,b) for a,b in all_boxes if a[0]<x1+2 and b[0]>x0-2 and a[1]<y1+2 and b[1]>y0-2]
        spatial=defaultdict(list)
        for a,b in boxes:
            for ix in range(math.floor(max(a[0]-RADIUS,x0-2)/BUCKET),math.floor(min(b[0]+RADIUS,x1+2)/BUCKET)+1):
                for iy in range(math.floor(max(a[1]-RADIUS,y0-2)/BUCKET),math.floor(min(b[1]+RADIUS,y1+2)/BUCKET)+1):
                    spatial[(ix,iy)].append((a,b))
        levels={}
        for ix in range(math.floor((x0-1.75)/STEP),math.ceil((x1+1.75)/STEP)):
            for iy in range(math.floor((y0-1.75)/STEP),math.ceil((y1+1.75)/STEP)):
                x,y=ix*STEP,iy*STEP
                near=[(a,b) for a,b in spatial[(math.floor(x/BUCKET),math.floor(y/BUCKET))]
                      if a[0]<x+RADIUS and b[0]>x-RADIUS and a[1]<y+RADIUS and b[1]>y-RADIUS]
                tops={round(b[2],4) for a,b in near if b[2]<=1.3+(len(design["storeys"])-1)*design["storey_height_m"]+.01}
                free=[z for z in tops if not any(a[2]<z+HEIGHT and b[2]>z+.035 for a,b in near)]
                if free:levels[(ix,iy)]=sorted(free)
        e=semantic["entry"];x=x0+e["offset_m"]+e["width_m"]/2;y=y0-1.3 if e["side"]=="south" else y1+1.3
        candidates=[(abs(ix*STEP-x)+abs(iy*STEP-y)+abs(z-1.1)*10,(ix,iy,z))
                    for (ix,iy),zs in levels.items() for z in zs if abs(ix*STEP-x)<1 and abs(iy*STEP-y)<1]
        require(bool(candidates),"city.route_entry",f"{group}: no supported entry start")
        start=min(candidates)[1];previous={start:None};queue=deque([start])
        while queue:
            ix,iy,z=queue.popleft()
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                for nz in levels.get((ix+dx,iy+dy),[]):
                    node=(ix+dx,iy+dy,nz)
                    if abs(nz-z)<=.251 and node not in previous:previous[node]=(ix,iy,z);queue.append(node)
        for room in semantic["rooms"]:
            a,b=room["bounds"]["min"],room["bounds"]["max"]
            targets=[(abs(ix*STEP-(a[0]+b[0])/2)+abs(iy*STEP-(a[1]+b[1])/2),(ix,iy,z)) for ix,iy,z in previous
                     if a[0]+RADIUS<ix*STEP<b[0]-RADIUS and a[1]+RADIUS<iy*STEP<b[1]-RADIUS and abs(z-a[2])<.05]
            require(bool(targets),"city.route_room",f"{group}: no route into {room['id']}")
            node=min(targets)[1];path=[]
            while node is not None:path.append([node[0]*STEP,node[1]*STEP,node[2]]);node=previous[node]
            result.append({"group":group,"room":room["id"],"level":room["level"],"cells":list(reversed(path))})
    return {"status":"pass","method":"tenth_metre_supported_clearance_graph_xy_index",
            "character_radius_m":RADIUS,"character_height_m":HEIGHT,"max_step_m":.251,"target_walk":"not_run","routes":result}
