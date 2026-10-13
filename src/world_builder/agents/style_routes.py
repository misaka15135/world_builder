"""Small bounded clearance/support graph for detailed 042 source geometry."""
from collections import deque
import math
from .validation import require

STEP=.1
RADIUS=.30
HEIGHT=1.8


def walking_routes(geometry):
    result=[]
    all_boxes=[(p["bounds_wir_m"][0],p["bounds_wir_m"][1]) for p in geometry["parts"] if p["block"]!="minecraft:water"]
    for group,semantic in geometry["buildings"].items():
        design=semantic["design"]
        x0,y0,x1,y1=design["outline"]
        boxes=[(a,b) for a,b in all_boxes if a[0]<x1+2 and b[0]>x0-2 and a[1]<y1+2 and b[1]>y0-2]
        levels={}
        for ix in range(math.floor((x0-1.75)/STEP),math.ceil((x1+1.75)/STEP)):
            for iy in range(math.floor((y0-1.75)/STEP),math.ceil((y1+1.75)/STEP)):
                x,y=ix*STEP,iy*STEP
                near=[(a,b) for a,b in boxes if a[0]<x+RADIUS and b[0]>x-RADIUS and a[1]<y+RADIUS and b[1]>y-RADIUS]
                # A capsule can be supported on a ledge within its footprint
                # before its centre crosses the riser; target physics is checked separately.
                tops={round(b[2],4) for a,b in near
                      if b[2]<=1.3+(len(design["storeys"])-1)*design["storey_height_m"]+.01}
                free=[z for z in tops if not any(a[2]<z+HEIGHT and b[2]>z+.035 for a,b in near)]
                if free: levels[(ix,iy)]=sorted(free)
        e=semantic["entry"]
        x=x0+e["offset_m"]+e["width_m"]/2
        y=y0-1.3 if e["side"]=="south" else y1+1.3
        candidates=[(abs(ix*STEP-x)+abs(iy*STEP-y)+abs(z-1.1)*10,(ix,iy,z))
                    for (ix,iy),zs in levels.items() for z in zs if abs(ix*STEP-x)<1 and abs(iy*STEP-y)<1]
        require(bool(candidates),"style.route_entry",f"{group}: no supported entry start")
        start=min(candidates)[1]
        previous={start:None}
        queue=deque([start])
        while queue:
            ix,iy,z=queue.popleft()
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                for nz in levels.get((ix+dx,iy+dy),[]):
                    node=(ix+dx,iy+dy,nz)
                    if abs(nz-z)<=.251 and node not in previous:
                        previous[node]=(ix,iy,z)
                        queue.append(node)
        for room in semantic["rooms"]:
            a,b=room["bounds"]["min"],room["bounds"]["max"]
            target=[(abs(ix*STEP-(a[0]+b[0])/2)+abs(iy*STEP-(a[1]+b[1])/2), (ix,iy,z))
                    for (ix,iy,z) in previous if a[0]+RADIUS<ix*STEP<b[0]-RADIUS and a[1]+RADIUS<iy*STEP<b[1]-RADIUS
                    and abs(z-a[2])<.05]
            require(bool(target),"style.route_room",f"{group}: no route from road into {room['id']}")
            node=min(target)[1]
            path=[]
            while node is not None:
                path.append([node[0]*STEP,node[1]*STEP,node[2]])
                node=previous[node]
            result.append({"group":group,"room":room["id"],"level":room["level"],"cells":list(reversed(path))})
    return {"status":"pass","method":"tenth_metre_supported_clearance_graph",
            "character_radius_m":RADIUS,"character_height_m":HEIGHT,"max_step_m":.251,
            "target_walk":"not_run","routes":result}
