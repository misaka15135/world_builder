"""046 rolling landscape and seeded non-lattice settlements, stored as source meshes."""
from collections import defaultdict
from copy import deepcopy
import heapq
import math
from pathlib import Path
import random

from .contracts import HASH, ID, REQUEST_SCHEMA, arr, digest, enum, integer, obj, string, validate_schema
from .runtime import Supervisor, write_json
from .validation import require
from .style_scene import raw_building, box, disjoint_parts, REVIEW
from .city_routes import walking_routes
from .city_scene import RECIPE_IDS, castle_parts
from .nature_mesh import mesh, cuboid, cone, transform

VERSION="0.1.0-nature046"
BUILDER="organic-terrain-046.2"
SIZE=768
GRID=2
N=SIZE//GRID
BASE=obj(west_height=integer(30,70),north_height=integer(45,95),east_height=integer(25,65),
         river_bend=integer(24,46),river_width=integer(18,28),river_phase_deg=integer(0,90),
         valley_width=integer(96,144),trees=integer(300,440),rationale=string(600))
DISTRICTS=("west_low","west_high","east_low","east_high")
LAYOUT=obj(title=string(120),concept=string(600),
           districts=arr(obj(id=enum(*DISTRICTS),x=integer(140,610),y=integer(180,520),radius=integer(98,112),
                             home_percent=integer(40,60),yaw_jitter=integer(12,28)),4,4),
           castle=obj(x=integer(580,650),y=integer(650,680),yaw=integer(-22,22)))
LIMITS={"west_low":(160,220,180,240),"west_high":(140,220,430,500),
        "east_low":(540,610,210,280),"east_high":(530,600,460,520)}


def synthetic_parameters():
    return {"B":{"west_height":58,"north_height":82,"east_height":46,"river_bend":36,"river_width":24,
                  "river_phase_deg":30,"valley_width":120,"trees":340,"rationale":"Explicit offline fixture"},
            "D":{"title":"Rolling valley comparison","concept":"Synthetic parameters, not API output",
                 "districts":[{"id":rid,"x":x,"y":y,"radius":106,"home_percent":50,"yaw_jitter":22}
                              for rid,x,y in (("west_low",190,210),("west_high",175,475),("east_low",580,245),("east_high",565,490))],
                 "castle":{"x":620,"y":670,"yaw":-12}}}


def river_x(base,y):
    phase=math.radians(base["river_phase_deg"])
    return 384+base["river_bend"]*(math.sin(y/143+phase)+.3*math.sin(y/69+.4))


def smooth(t):
    t=max(0,min(1,t));return t*t*(3-2*t)


def natural_height(base,x,y):
    dx=abs(x-river_x(base,y));half=base["river_width"]/2
    if dx<=half:return 2+2.8*(dx/half)**2
    hills=(base["west_height"]*math.exp(-((x-70)/128)**2-((y-500)/230)**2)
           +base["north_height"]*math.exp(-((x-390)/180)**2-((y-760)/123)**2)
           +base["east_height"]*math.exp(-((x-720)/155)**2-((y-570)/205)**2)
           +5+2.2*math.sin(x/69)*math.sin(y/93))
    return 4.8+smooth((dx-half)/base["valley_width"])*hills


def check_parameters(parameters):
    validate_schema(parameters["B"],BASE);layout=parameters["D"];validate_schema(layout,LAYOUT)
    require({d["id"] for d in layout["districts"]}==set(DISTRICTS),"nature.districts","Exactly four unique districts required")
    for d in layout["districts"]:
        x0,x1,y0,y1=LIMITS[d["id"]]
        require(x0<=d["x"]<=x1 and y0<=d["y"]<=y1,"nature.district_bounds",f"{d['id']}: x={x0}..{x1}, y={y0}..{y1}")


def scatter(parameters):
    check_parameters(parameters);base,layout=parameters["B"],parameters["D"]
    rng=random.Random(46);sites=[];castle=layout["castle"]
    for district in sorted(layout["districts"],key=lambda d:d["id"]):
        assigned=list(RECIPE_IDS)
        for _ in range(8):
            kind="home" if rng.random()*100<district["home_percent"] else "shop"
            assigned.append(kind+"_"+rng.choice("abcd"))
        rng.shuffle(assigned)
        for i in range(16):
            width,depth=rng.randint(14,22),rng.randint(12,18)
            radius=math.hypot(width/2,depth/2)+3
            for attempt in range(12000):
                # Rejection sampling: no rows, rings or fixed angular slots.
                dx,dy=rng.uniform(-district["radius"],district["radius"]),rng.uniform(-district["radius"],district["radius"])
                if not 34<math.hypot(dx,dy)<district["radius"]:continue
                x,y=district["x"]+dx,district["y"]+dy
                if math.dist((x,y),(castle["x"],castle["y"]))<radius+85:continue
                if abs(x-river_x(base,y))<base["river_width"]/2+radius+20:continue
                if any(math.dist((x,y),(s["x"],s["y"]))<radius+s["radius"]+3 for s in sites):continue
                # Keep the open square/hub in every settlement clear.
                yaw=math.degrees(math.atan2(-dx,dy))+rng.uniform(-district["yaw_jitter"],district["yaw_jitter"])
                sites.append({"id":f"{district['id']}_{i:02}","district":district["id"],"recipe_id":assigned[i],
                              "x":round(x,4),"y":round(y,4),"yaw":round(yaw,4),"width":width,"depth":depth,
                              "radius":radius,"height":natural_height(base,x,y)})
                break
            else:require(False,"nature.capacity",f"Cannot fit 16 dry, separated sites in {district['id']}; no silent deletion")
    require(len(sites)==64,"nature.coverage","64 ordinary buildings required")
    return sites


class Terrain:
    """Source sampled height field; interpolation matches the exported triangle diagonal."""
    def __init__(self,base,pads):
        self.base=base;self.pads=pads;self.index=defaultdict(list)
        for pad in pads:
            r=pad["radius"]+pad.get("blend",14)
            for ix in range(math.floor((pad["x"]-r)/32),math.ceil((pad["x"]+r)/32)+1):
                for iy in range(math.floor((pad["y"]-r)/32),math.ceil((pad["y"]+r)/32)+1):self.index[(ix,iy)].append(pad)
        self.heights=[[self.height(x*GRID,y*GRID) for y in range(N+1)] for x in range(N+1)]
    def height(self,x,y):
        value=natural_height(self.base,x,y)
        candidates=self.index[(math.floor(x/32),math.floor(y/32))]
        weighted=value;total=1
        for pad in candidates:
            distance=math.hypot(x-pad["x"],y-pad["y"])-pad["radius"]
            if distance<=0:
                value=pad["height"];break
            factor=1-smooth(distance/pad.get("blend",14))
            weight=factor/max(1e-10,1-factor)
            weighted+=pad["height"]*weight;total+=weight
        else:value=weighted/total
        # The channel is never filled by a nearby building/bridge grading pad.
        if abs(x-river_x(self.base,y))<self.base["river_width"]/2:return natural_height(self.base,x,y)
        return value
    def sample(self,x,y):
        ix,iy=min(N-1,max(0,math.floor(x/GRID))),min(N-1,max(0,math.floor(y/GRID)))
        tx,ty=(x-ix*GRID)/GRID,(y-iy*GRID)/GRID
        a,b,c,d=self.heights[ix][iy],self.heights[ix+1][iy],self.heights[ix][iy+1],self.heights[ix+1][iy+1]
        return a+(b-a)*tx+(c-a)*ty if tx+ty<=1 else d+(c-d)*(1-tx)+(b-d)*(1-ty)
    def normal(self,ix,iy):
        lx,hx=max(0,ix-1),min(N,ix+1);ly,hy=max(0,iy-1),min(N,iy+1)
        dx=(self.heights[hx][iy]-self.heights[lx][iy])/((hx-lx)*GRID)
        dy=(self.heights[ix][hy]-self.heights[ix][ly])/((hy-ly)*GRID)
        length=math.sqrt(1+dx*dx+dy*dy);return [-dx/length,-dy/length,1/length]
    def cell_grade(self,ix,iy):
        if not 0<=ix<N or not 0<=iy<N:return float("inf")
        a,b,c,d=self.heights[ix][iy],self.heights[ix+1][iy],self.heights[ix][iy+1],self.heights[ix+1][iy+1]
        return max(math.hypot(b-a,c-a),math.hypot(d-c,d-b))/GRID
    def grade(self,x,y):
        return self.cell_grade(min(N-1,max(0,math.floor(x/GRID))),min(N-1,max(0,math.floor(y/GRID))))


def bridge_specs(base):
    result=[]
    for i,y in enumerate((288,548)):
        x=river_x(base,y);span=base["river_width"]/2+16
        result.append({"id":f"bridge_{i}","x":x,"y":y,"span":span,"width":8,"height":8,
                       "west":[x-span+2,y],"east":[x+span-2,y]})
    return result


def make_pose(site):
    return {"x":site["x"],"y":site["y"],"yaw":site["yaw"],"ox":site["width"]/2,"oy":site["depth"]/2,"dz":site["height"]-1.1}


def inside_site(x,y,site,padding=0):
    dx,dy=x-site["x"],y-site["y"];a=math.radians(site["yaw"])
    lx=math.cos(a)*dx+math.sin(a)*dy;ly=-math.sin(a)*dx+math.cos(a)*dy
    return abs(lx)<site["width"]/2+padding and abs(ly)<site["depth"]/2+padding


class RoadPlanner:
    def __init__(self,terrain,sites,castle):
        self.terrain,self.sites,self.castle=terrain,sites,castle;self.blocked_cache={};self.paint=set();self.routes=[]
    def blocked(self,node):
        if node in self.blocked_cache:return self.blocked_cache[node]
        x,y=node[0]*GRID,node[1]*GRID
        value=(not 1<=node[0]<N or not 1<=node[1]<N or abs(x-river_x(self.terrain.base,y))<self.terrain.base["river_width"]/2+2
               or any(inside_site(x,y,s,1.8) for s in self.sites)
               or inside_site(x,y,self.castle,4)
               # Longitudinal grade alone misses steep cross-slopes: a path
               # along a contour can still exceed the capsule's slope limit.
               or any(self.terrain.cell_grade(node[0]+dx,node[1]+dy)>1.05 for dx in (-1,0) for dy in (-1,0)))
        self.blocked_cache[node]=value;return value
    def path(self,start,end):
        first=tuple(round(v/GRID) for v in start);last=tuple(round(v/GRID) for v in end)
        queue=[(0,0,first)];cost={first:0};previous={first:None}
        while queue:
            _,g,node=heapq.heappop(queue)
            if node==last:break
            if g>cost[node]:continue
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                nxt=(node[0]+dx,node[1]+dy)
                if nxt!=last and self.blocked(nxt):continue
                if dx and dy and (self.blocked((node[0]+dx,node[1])) or self.blocked((node[0],node[1]+dy))):continue
                distance=GRID*math.hypot(dx,dy)
                slope=abs(self.terrain.sample(nxt[0]*GRID,nxt[1]*GRID)-self.terrain.sample(node[0]*GRID,node[1]*GRID))/distance
                if slope>.58:continue
                ng=g+distance*(1+3*slope*slope)
                if ng<cost.get(nxt,float("inf")):
                    cost[nxt]=ng;previous[nxt]=node
                    heapq.heappush(queue,(ng+GRID*math.hypot(nxt[0]-last[0],nxt[1]-last[1]),ng,nxt))
            require(len(previous)<120000,"nature.road_budget","Road search budget exceeded")
        require(last in previous,"nature.road",f"No dry, graded road to requested building/hub: {start} -> {end}")
        nodes=[];p=last
        while p is not None:nodes.append([p[0]*GRID,p[1]*GRID]);p=previous[p]
        nodes=list(reversed(nodes));nodes[0]=list(start);nodes[-1]=list(end)
        return nodes
    def add(self,name,nodes,width=5):
        for a,b in zip(nodes,nodes[1:]):
            steps=max(1,math.ceil(math.dist(a,b)))
            for i in range(steps+1):
                x=a[0]+(b[0]-a[0])*i/steps;y=a[1]+(b[1]-a[1])*i/steps
                ix,iy=math.floor(x/GRID),math.floor(y/GRID)
                for dx in range(-2,3):
                    for dy in range(-2,3):
                        if math.dist(((ix+dx+.5)*GRID,(iy+dy+.5)*GRID),(x,y))<=width/2+1:self.paint.add((ix+dx,iy+dy))
        self.routes.append({"id":name,"points":nodes})


def build_terrain_meshes(terrain,road_mask,castle=None,hubs=()):
    result=[]
    for tx in range(0,N,32):
        for ty in range(0,N,32):
            groups=defaultdict(list)
            vertices=[];normals=[]
            for ix in range(tx,tx+33):
                for iy in range(ty,ty+33):vertices.append([ix*GRID,iy*GRID,terrain.heights[ix][iy]]);normals.append(terrain.normal(ix,iy))
            for ix in range(tx,tx+32):
                for iy in range(ty,ty+32):
                    if castle and inside_site((ix+.5)*GRID,(iy+.5)*GRID,castle,-2):continue
                    high=terrain.heights[ix][iy];normal=terrain.normal(ix,iy)
                    material="terrain_rock" if high>62 or normal[2]<.84 else "terrain_grass_dark" if math.sin(ix/17)*math.cos(iy/19)>.4 else "terrain_grass"
                    if (ix,iy) in road_mask:material="road_earth"
                    if any(math.dist(((ix+.5)*GRID,(iy+.5)*GRID),(h[0],h[1]))<14 for h in hubs):material="plaza_stone"
                    a=(ix-tx)*33+(iy-ty);b=a+33;c=a+1;d=b+1
                    groups[material].extend([a,b,c,d,c,b])
            for material,indices in sorted(groups.items()):
                # Keep only referenced vertices: source bounds must equal renderer bounds.
                used=sorted(set(indices));remap={old:i for i,old in enumerate(used)}
                result.append(mesh(f"terrain_{tx}_{ty}_{material}","terrain",material,[vertices[i] for i in used],
                                   [remap[i] for i in indices],[normals[i] for i in used]))
    return result


def source_routes(planner,bridges):
    result=[];max_grade=0;max_surface_grade=0
    for route in planner.routes:
        dense=[];route_grade=0
        for a,b in zip(route["points"],route["points"][1:]):
            steps=max(1,math.ceil(math.dist(a,b)/.5))
            for i in range(steps+1):
                x=a[0]+(b[0]-a[0])*i/steps;y=a[1]+(b[1]-a[1])*i/steps
                bridge=next((br for br in bridges if abs(x-br["x"])<=br["span"] and abs(y-br["y"])<=br["width"]/2-.3),None)
                wet=abs(x-river_x(planner.terrain.base,y))<planner.terrain.base["river_width"]/2
                require(not wet or bridge is not None,"nature.missing_bridge",f"{route['id']}: road crosses unsupported water")
                z=bridge["height"] if bridge else planner.terrain.sample(x,y)
                if not bridge and hasattr(planner.terrain,"grade"):
                    surface_grade=planner.terrain.grade(x,y)
                    require(surface_grade<1.1,"nature.cross_slope",f"{route['id']}: full triangle grade {surface_grade} exceeds safe slope")
                    max_surface_grade=max(max_surface_grade,surface_grade)
                require(not any(inside_site(x,y,s,.35) for s in getattr(planner,"sites",[])),
                        "nature.road_obstacle",f"{route['id']}: outdoor capsule overlaps a building/fountain footprint")
                point=[round(x,5),round(y,5),round(z,5)]
                if dense and point!=dense[-1]:
                    distance=math.dist(point[:2],dense[-1][:2])
                    if distance>1e-5:route_grade=max(route_grade,abs(point[2]-dense[-1][2])/distance)
                if not dense or point!=dense[-1]:dense.append(point)
        require(len(dense)>1,"nature.route_empty","Route has no supported movement")
        require(route_grade<.85,"nature.slope",f"{route['id']}: route grade exceeds allowance: {route_grade}")
        max_grade=max(max_grade,route_grade)
        result.append({"id":route["id"],"cells":dense})
    require(max_grade<.85,"nature.slope",f"Route grade exceeds capsule target allowance: {max_grade}")
    return {"status":"pass","method":"terrain_triangle_interpolation_full_slope_and_explicit_bridge_decks","max_grade":round(max_grade,5),
            "max_surface_grade":round(max_surface_grade,5),"routes":result}


def build_nature(parameters,recipes,*,rooms=True):
    sites=scatter(parameters);base=parameters["B"];castle=parameters["D"]["castle"]
    castle_site={**castle,"width":128,"depth":64,"height":natural_height(base,castle["x"],castle["y"]),"radius":74,"blend":26}
    bridges=bridge_specs(base)
    hubs={d["id"]:[d["x"],d["y"]] for d in parameters["D"]["districts"]}
    hub_pads=[{"x":x,"y":y,"height":natural_height(base,x,y),"radius":16,"blend":12} for x,y in hubs.values()]
    fountain_sites=[{"x":x-9,"y":y+8,"yaw":0,"width":5,"depth":5} for x,y in hubs.values()]
    pads=[{**s,"blend":14} for s in sites]+[castle_site]+hub_pads
    for b in bridges:
        pads.extend({"x":p[0],"y":p[1],"radius":16,"blend":18,"height":8} for p in (b["west"],b["east"]))
    terrain=Terrain(base,pads)
    planner=RoadPlanner(terrain,sites+fountain_sites,castle_site)
    for i,(a,b) in enumerate((("west_low","west_high"),("east_low","east_high"))):
        planner.add(f"hillside_avenue_{i}",planner.path(hubs[a],hubs[b]),6)
    for i,bridge in enumerate(bridges):
        side="low" if i==0 else "high"
        west=planner.path(hubs["west_"+side],bridge["west"])
        east=planner.path(bridge["east"],hubs["east_"+side])
        planner.add(f"river_crossing_{i}",west+[bridge["east"]]+east[1:],6)
    locals_={};poses={};parts=[];room_routes=[]
    for site in sites:
        sid=site["id"];recipe=recipes[site["recipe_id"]]
        local_site={"id":sid,"type":"residence" if site["recipe_id"].startswith("home") else "shop",
                    "rect":[0,0,site["width"],site["depth"]],"entry_side":"south"}
        raw,semantic=raw_building(local_site,{**recipe,"site_id":sid});local=disjoint_parts(raw)
        pose=make_pose(site);poses[sid]=pose;locals_[sid]={"parts":local,"semantic":semantic,"recipe_id":site["recipe_id"]}
        parts.extend(cuboid(p,pose) for p in local)
        entry=semantic["entry"];ex=entry["offset_m"]+entry["width_m"]/2
        anchor=transform([ex,-5,1.1],pose)[:2];near=transform([ex,-1.4,1.1],pose)[:2]
        planner.add("entry_"+sid,planner.path(hubs[site["district"]],anchor)+[near],4)
        require(abs(terrain.sample(*near)-site["height"])<.025,"nature.entry_grade",f"{sid}: entrance terrain does not match graded floor")
        if rooms:
            proxy=local+[box("local_terrain",[-3,-4,site["width"]+3,site["depth"]+3],0,1,"minecraft:grass_block","validation"),
                         box("local_entry_context",[-3,-4,site["width"]+3,0],1,1.1,"minecraft:stone_bricks","validation")]
            routes=walking_routes({"parts":proxy,"buildings":{sid:semantic}})["routes"]
            room_routes.extend({**r,"local_cells":r["cells"],"cells":[transform(p,pose) for p in r["cells"]]} for r in routes)
    raw,semantic,keep_site,keep_design=castle_parts(0,recipes["castle"])
    pose={"x":castle["x"],"y":castle["y"],"yaw":castle["yaw"],"ox":64,"oy":464,"dz":castle_site["height"]-1.1}
    poses["castle_keep"]=pose;local=disjoint_parts(raw)
    parts.extend(cuboid(p,pose) for p in local)
    locals_["castle_keep"]={"parts":local,"semantic":semantic,"recipe_id":"castle"}
    outside=transform([64,426,1.1],pose)[:2]
    e=semantic["entry"];ex=keep_site["rect"][0]+e["offset_m"]+e["width_m"]/2
    approach=[transform(p,pose)[:2] for p in ([64,431,1.1],[64,440,1.1],[ex,440,1.1],[ex,keep_site["rect"][1]-1.4,1.1])]
    planner.add("castle_approach",planner.path(hubs["east_high"],outside)+approach,6)
    if rooms:
        routes=walking_routes({"parts":local,"buildings":{"castle_keep":semantic}})["routes"]
        room_routes.extend({**r,"local_cells":r["cells"],"cells":[transform(p,pose) for p in r["cells"]]} for r in routes)
    # Terrain is a true triangle surface; roads are material regions, not coplanar overlay boxes.
    parts=build_terrain_meshes(terrain,planner.paint,castle_site,list(hubs.values()))+parts
    identity={"x":0,"y":0,"yaw":0,"ox":0,"oy":0,"dz":0}
    for i,fountain in enumerate(fountain_sites):
        x,y=fountain["x"],fountain["y"];z=terrain.sample(x,y)
        parts.extend(cuboid(p,identity) for p in (
            box(f"square_{i}_basin",[x-2,y-2,x+2,y+2],z-.1,z+.45,"minecraft:stone_bricks","squares"),
            box(f"square_{i}_water",[x-1.6,y-1.6,x+1.6,y+1.6],z+.45,z+.55,"minecraft:water","squares"),
            box(f"square_{i}_column",[x-.25,y-.25,x+.25,y+.25],z+.55,z+2.8,"minecraft:smooth_stone","squares")))
    for b in bridges:
        x,y,s=b["x"],b["y"],b["span"]
        parts.append(cuboid(box(b["id"]+"_deck",[x-s,y-4,x+s,y+4],7.65,8,"minecraft:stone_bricks","bridges"),identity))
        for side in (y-4,y+3.7):parts.append(cuboid(box(b["id"]+f"_rail_{side}",[x-s,side,x+s,side+.3],8,9,"minecraft:smooth_stone","bridges"),identity))
    water=[]
    for y in range(0,SIZE+1,2):
        x=river_x(base,y);water.extend([[x-base["river_width"]/2,y,4.8],[x+base["river_width"]/2,y,4.8]])
    indices=[j for i in range(SIZE//2) for j in (2*i,2*i+1,2*i+2,2*i+3,2*i+2,2*i+1)]
    parts.append(mesh("winding_river","river","minecraft:water",water,indices,[[0,0,1]]*len(water),solid=False))
    rng=random.Random(460)
    trees=0;tries=0
    while trees<base["trees"]:
        tries+=1;require(tries<20000,"nature.forest_capacity","No safe forest placement")
        x,y=rng.uniform(12,756),rng.uniform(12,756)
        if abs(x-river_x(base,y))<base["river_width"]/2+10:continue
        if any(math.dist((x,y),(s["x"],s["y"]))<s["radius"]+5 for s in sites+[castle_site]+hub_pads):continue
        if any((math.floor(x/2)+dx,math.floor(y/2)+dy) in planner.paint for dx in range(-2,3) for dy in range(-2,3)):continue
        z=terrain.sample(x,y);h=rng.uniform(5,11);radius=rng.uniform(2.2,3.8);trees+=1
        parts.append(cuboid(box(f"tree_{trees}_trunk",[x-.25,y-.25,x+.25,y+.25],z-.5,z+h*.72,"minecraft:oak_log","forest"),identity))
        for layer in range(2):parts.append(cone(f"tree_{trees}_leaf{layer}","forest","forest_pine" if trees%3 else "forest_sage",x,y,z+h*.3+layer*h*.25,radius*(1-layer*.27),h*.65))
    network=source_routes(planner,bridges)
    for i,p in enumerate(parts):p["name"]=f"nature_{i:05}"
    maxh=max(max(row) for row in terrain.heights);minh=min(min(row) for row in terrain.heights)
    require(maxh-minh>40,"nature.relief","Terrain has insufficient real relief")
    require(len(parts)<16000,"nature.parts","Component budget exceeded")
    require(len({round(s["yaw"]/5)*5 for s in sites})>20,"nature.orientation","Buildings remain too uniformly aligned")
    report={"status":"pass","region_m":768,"ordinary_buildings":64,"castle_keeps":1,"bridges":2,"terrain_vertices":(N+1)**2,
            "height_min_m":round(minh,3),"height_max_m":round(maxh,3),"terrain_relief_m":round(maxh-minh,3),
            "river_lateral_range_m":round(max(river_x(base,y) for y in range(SIZE))-min(river_x(base,y) for y in range(SIZE)),3),
            "part_count":len(parts),"trees":trees,"source_room_routes":len(room_routes),"network_routes":len(network["routes"]),
            "max_road_grade":network["max_grade"],"max_road_surface_grade":network["max_surface_grade"],
            "unique_yaw_bins_5deg":len({round(s["yaw"]/5)*5 for s in sites}),
            "placement_policy":"seeded separated irregular clusters, inward facade with angular jitter; A* roads avoid footprints",
            "source_room_validation":"pass" if rooms else "not_run"}
    return {"version":VERSION,"builder":BUILDER,"parts":parts,"sites":sites,"poses":poses,"local_buildings":locals_,
            "terrain":{"cell_m":2,"size_m":768,"heights":terrain.heights,"pads":pads},"bridges":bridges,
            "walking":{"status":"pass" if rooms else "not_run","routes":room_routes},"network":network,"report":report,
            "view":{"spawn":[*hubs["west_low"],terrain.sample(*hubs["west_low"])],"castle":[castle["x"],castle["y"],castle_site["height"]],
                    "river":[river_x(base,288),288,8],"village":[*hubs["east_high"],terrain.sample(*hubs["east_high"])]}}


class NatureSupervisor(Supervisor):
    contract_version=VERSION
    geometry="terrain_mesh_and_rotated_recipes_v1"
    def __init__(self,*args,**kwargs):
        require(kwargs.pop("region_m",768)==768,"nature.region","046 supports exactly 768 metres")
        # Keep the frozen 0.1.0 supervisor's public 512m limit unchanged. This
        # version owns its larger request schema and independent constructor.
        super().__init__(*args,region_m=512,**kwargs)
        self.region_m=768
        for stage in ("B","D","F"):self.skills[stage]=(Path(__file__).resolve().parents[3]/"skills/world-nature-046"/f"{stage}.md").read_text("utf-8")
    def request_schema(self):
        schema=deepcopy(REQUEST_SCHEMA);schema["properties"]["contract_version"]={"const":VERSION};schema["properties"]["geometry"]={"const":self.geometry}
        schema["properties"]["region_m"]=integer(768,768)
        schema["properties"]["dependencies"]=arr(obj(stage=enum("B","D","E"),sha256=HASH,data={"type":"object"}),0,3)
        return schema
    def response_contract(self,stage,plans,request_id=None,scope_id=None):
        return obj(contract_version={"const":VERSION},stage={"const":stage},request_id={"const":request_id} if request_id else HASH,
                   scope_id={"const":scope_id} if scope_id else ID,payload={"B":BASE,"D":LAYOUT,"F":REVIEW}[stage])
    def validate_payload(self,stage,payload,plans,scope_id):
        if stage=="D":
            parameters={"B":plans["B"],"D":payload}
            scatter(parameters)
            # Reject unserviceable terrain/layout before accepting D. A failed
            # proposal can use the normal bounded retry, not a silent local fix.
            if hasattr(self,"reuse"):build_nature(parameters,self.reuse["recipes"],rooms=False)
        elif stage=="F":require(payload["verdict"]!="accept" or not payload["issues"],"nature.review","Accept cannot contain issues")
    def run(self,prompt,reuse):
        self.prompt=prompt;self.reuse=reuse;self.event("started",prompt=prompt,source_e_reuse_sha256=digest(reuse))
        base=self.ask("B",{})
        layout=self.ask("D",{"B":base})
        parameters={"B":base,"D":layout}
        write_json(self.root/"accepted_parameters.json",parameters)
        self.event("construction_started")
        geometry=build_nature(parameters,reuse["recipes"])
        review=self.ask("F",{"B":geometry["report"],"E":{"reuse_source":reuse["source_contract"],"recipe_ids":list(reuse["recipes"])}})
        require(review["verdict"]=="accept","nature.review_pending","Review requested changes; do not publish")
        accepted={"contract_version":VERSION,"prompt":prompt,"region_m":768,"seed":46,"plans":{**parameters,"E":reuse["recipes"],"F":review},
                  "reused_E_provenance":{k:v for k,v in reuse.items() if k!="recipes"},"accepted_responses":self.accepted,
                  "skill_hashes":{s:digest(self.skills[s]) for s in ("B","D","F")}}
        write_json(self.root/"accepted.json",accepted);write_json(self.root/"nature_geometry.json",geometry)
        return accepted,geometry
