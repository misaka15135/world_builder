"""045 bounded city recipes: model proposals, local projection and construction.

This is not the default A--F contract. Fixed 512 m brief, 48 serviced parcels,
eight model-authored recipes and one castle; no legacy whole-city planner.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import math
from pathlib import Path
import random

from .contracts import HASH, ID, REQUEST_SCHEMA, arr, digest, enum, integer, obj, string, validate_schema
from .geometry_normalization import _subtract
from .runtime import Supervisor, write_json
from .city_routes import walking_routes
from .style_scene import BUILDING, REVIEW, box, decorate_plaza, raw_building
from .validation import require

VERSION = "0.1.0-city045"
BUILDER = "city-detail-045.1"
RECIPE_IDS = tuple(f"{kind}_{letter}" for kind in ("home", "shop") for letter in "abcd")
COL_X = (24, 100, 176, 280, 356, 432)
SLOTS = tuple(f"row{r}_col{c}_{side}" for r in range(4) for c in range(6) for side in ("south", "north"))
BASE = obj(river_x=enum(248, 256, 264), river_width=enum(12, 16, 20),
           street_y=arr(integer(70, 384), 4, 4), street_width=integer(6, 10), rationale=string(600))
CATALOGUE = obj(archetypes=arr(obj(id=enum(*RECIPE_IDS), type=enum("residence", "shop"),
                                name=string(80), intent=string(300)), 8, 8),
                trees=integer(80, 140), lamps=integer(20, 36), concept=string(600))
LAYOUT = obj(title=string(120), concept=string(600), castle_x=enum(336, 352),
             sites=arr(obj(slot=enum(*SLOTS), recipe_id=enum(*RECIPE_IDS), width=integer(16, 24),
                           depth=integer(14, 20), x_shift=integer(-4, 4)), 48, 48))
CASTLE = obj(site_id={"const": "castle"}, concept=string(600), tower_height_m=integer(18, 26),
             tower_roof_m=integer(4, 7), wall_height_m=integer(6, 8), gate_width_m=integer(6, 10),
             keep_width_m=integer(26, 38), keep_depth_m=integer(18, 24),
             keep_roof=enum("gable", "spire"), roof_material=enum("wood", "slate"))
SCHEMAS = {"B": BASE, "C": CATALOGUE, "D": LAYOUT}


def synthetic_plans():
    """Explicit offline fixture, never used as an API fallback."""
    base={"river_x":256,"river_width":16,"street_y":[80,176,272,368],"street_width":8,"rationale":"Synthetic fixture only"}
    catalogue={"archetypes":[{"id":rid,"type":"residence" if rid.startswith("home") else "shop","name":rid,"intent":"Synthetic design"} for rid in RECIPE_IDS],
               "trees":96,"lamps":24,"concept":"Synthetic fixed comparison, not model output"}
    layout={"title":"Synthetic city fixture","concept":"Offline only","castle_x":352,
            "sites":[{"slot":slot,"recipe_id":RECIPE_IDS[i%8],"width":18+i%4,"depth":16+i%3,"x_shift":i%3-1} for i,slot in enumerate(SLOTS)]}
    designs={}
    for i,rid in enumerate(RECIPE_IDS):
        floors=1 if i==0 else 2
        designs[rid]={"site_id":rid,"concept":"Synthetic recipe only","storeys":floors,"storey_height_m":3.6,
                      "roof":("gable","spire","flat")[i%3],"roof_height_m":2,"wall_material":"stone" if i%2 else "plaster",
                      "roof_material":"slate" if i%2 else "wood","room_uses":[["hearth","kitchen"]] if floors==1 else [["stall","counter"],["bed","store"]]}
    designs["castle"]={"site_id":"castle","concept":"Synthetic castle only","tower_height_m":23,"tower_roof_m":6,
                       "wall_height_m":7,"gate_width_m":8,"keep_width_m":32,"keep_depth_m":22,"keep_roof":"spire","roof_material":"slate"}
    return {"B":base,"C":catalogue,"D":layout,"E":designs}


def check_base(base):
    validate_schema(base, BASE)
    for i, y in enumerate(base["street_y"]):
        require(abs(y - (80 + i * 96)) <= 6, "city.street", f"street_y[{i}] must be {80+i*96} +/-6")
    return base


def check_catalogue(catalogue):
    validate_schema(catalogue, CATALOGUE)
    require({a["id"] for a in catalogue["archetypes"]} == set(RECIPE_IDS), "city.recipes", "Exactly the eight recipe IDs required")
    for a in catalogue["archetypes"]:
        expected = "residence" if a["id"].startswith("home_") else "shop"
        require(a["type"] == expected, "city.recipe_type", f"{a['id']} requires {expected}")
    return catalogue


def project_sites(base, layout, catalogue):
    check_base(base)
    check_catalogue(catalogue)
    validate_schema(layout, LAYOUT)
    require({s["slot"] for s in layout["sites"]} == set(SLOTS), "city.slots", "Each of the 48 slots must appear exactly once")
    used = Counter(s["recipe_id"] for s in layout["sites"])
    require(set(used) == set(RECIPE_IDS), "city.recipe_coverage", "All eight recipes must be used")
    require(sum(v for k, v in used.items() if k.startswith("shop")) >= 16, "city.programme", "At least 16 shops required")
    require(sum(v for k, v in used.items() if k.startswith("home")) >= 16, "city.programme", "At least 16 residences required")
    types = {a["id"]: a["type"] for a in catalogue["archetypes"]}
    result = []
    for item in sorted(layout["sites"], key=lambda s: s["slot"]):
        row, col, side = item["slot"].split("_")
        r, c = int(row[3:]), int(col[3:])
        x = COL_X[c] + item["x_shift"]
        road_y = base["street_y"][r]
        y = road_y + base["street_width"] if side == "north" else road_y - item["depth"]
        site = {"id": item["slot"], "type": types[item["recipe_id"]], "recipe_id": item["recipe_id"],
                "rect": [x, y, x + item["width"], y + item["depth"]],
                "entry_side": "south" if side == "north" else "north", "street": r}
        left, right = base["river_x"] - base["river_width"]/2, base["river_x"] + base["river_width"]/2
        require(site["rect"][2] < left-3 or site["rect"][0] > right+3,
                "city.dry", "A building enters the river clearance")
        for other in result:
            a, b, cc, d = other["rect"]
            x0, y0, x1, y1 = site["rect"]
            require(x1+3 <= a or cc+3 <= x0 or y1+3 <= b or d+3 <= y0,
                    "city.site_overlap", "Building parcels need 3 m clearance")
        result.append(site)
    return result


def buckets(bounds, step=16):
    a, b = bounds
    for ix in range(math.floor(a[0]/step), math.ceil(b[0]/step)):
        for iy in range(math.floor(a[1]/step), math.ceil(b[1]/step)):
            yield ix, iy


def disjoint(raw, limit=16000):
    """Stable legacy paint priority, accelerated by XY buckets (not whole-city O(n²))."""
    result = []
    index = defaultdict(list)
    for part in reversed(raw):
        candidates = sorted({i for key in buckets(part["bounds_wir_m"]) for i in index[key]})
        fragments = [{"min": part["bounds_wir_m"][0], "max": part["bounds_wir_m"][1]}]
        for i in candidates:
            a, b = result[i]["bounds_wir_m"]
            fragments = [cut for fragment in fragments for cut in _subtract(fragment, {"min": a, "max": b})]
        for i, fragment in enumerate(fragments):
            fresh = {**part, "bounds_wir_m": [fragment["min"], fragment["max"]], "name": part["source_id"]+f"_piece{i}"}
            for key in buckets(fresh["bounds_wir_m"]):
                index[key].append(len(result))
            result.append(fresh)
        require(len(result) <= limit, "city.parts", "City detail budget exceeded")
    return list(reversed(result))


def check_no_overlap(parts):
    index = defaultdict(list)
    for position, p in enumerate(parts):
        a, b = p["bounds_wir_m"]
        require(all(math.isfinite(v) for v in a+b) and all(a[i] < b[i] for i in range(3)), "city.bounds", "Invalid box")
        require(0 <= a[0] < b[0] <= 512 and 0 <= a[1] < b[1] <= 512 and 0 <= a[2] < b[2] <= 48,
                "city.bounds", "City box outside region")
        for i in {i for key in buckets([a, b]) for i in index[key]}:
            c, d = parts[i]["bounds_wir_m"]
            require(not all(min(b[j], d[j])-max(a[j], c[j]) > 1e-7 for j in range(3)),
                    "city.overlap", f"Overlapping components: {p['source_id']}, {parts[i]['source_id']}")
        for key in buckets([a, b]):
            index[key].append(position)


def infrastructure(base):
    rx, rw, width = base["river_x"], base["river_width"], base["street_width"]
    left, right = rx-rw/2, rx+rw/2
    parts = [box("west_land", [0, 0, left, 512], 0, 1, "minecraft:grass_block", "terrain"),
             box("east_land", [right, 0, 512, 512], 0, 1, "minecraft:grass_block", "terrain"),
             box("river_bed", [left, 0, right, 512], 0, .35, "minecraft:gravel", "river"),
             box("river_water", [left, 0, right, 512], .35, .85, "minecraft:water", "river")]
    roads = []
    bridges = []
    for row, y in enumerate(base["street_y"]):
        for bank, a, b in (("west", 8, left), ("east", right, 504)):
            rect = [a, y, b, y+width]
            roads.append(rect)
            parts.append(box(f"street_{row}_{bank}", rect, 1, 1.1, "minecraft:stone_bricks", "roads"))
        deck = [left-1, y, right+1, y+width]
        bridges.append(deck)
        roads.append(deck)
        parts.append(box(f"bridge_{row}_deck", deck, .9, 1.1, "minecraft:stone_bricks", "bridges"))
        for side_y in (y, y+width-.3):
            parts.append(box(f"bridge_{row}_rail_{side_y}", [left, side_y, right, side_y+.3], 1.1, 2.1,
                             "minecraft:smooth_stone", "bridges"))
    for x in (72, 328):
        rect = [x-4, 0, x+4, 512]
        roads.append(rect)
        parts.append(box(f"avenue_{x}", rect, 1, 1.1, "minecraft:stone_bricks", "roads"))
    for x in (left-6, right+2):
        rect = [x, 16, x+4, 496]
        roads.append(rect)
        parts.append(box(f"river_walk_{x}", rect, 1, 1.1, "minecraft:stone_bricks", "roads"))
    return parts, roads, bridges


def castle_parts(x0, params):
    validate_schema(params, CASTLE)
    x1, y0, y1, cx = x0+128, 432, 496, x0+64
    group = "castle"
    parts = [box("castle_court", [x0, y0, x1, y1], 1, 1.1, "minecraft:stone_bricks", group)]
    gate = params["gate_width_m"]
    wall_top = 1+params["wall_height_m"]
    walls = [[x0, y0, cx-gate/2, y0+2], [cx+gate/2, y0, x1, y0+2],
             [x0, y1-2, x1, y1], [x0, y0, x0+2, y1], [x1-2, y0, x1, y1]]
    for i, rect in enumerate(walls):
        parts.append(box(f"castle_wall_{i}", rect, 1.1, wall_top, "minecraft:smooth_stone", group))
    parts.append(box("castle_gate_lintel", [cx-gate/2, y0, cx+gate/2, y0+2], 5, wall_top+2,
                     "minecraft:smooth_stone", group))
    for x in range(x0, x1, 4):
        for y in (y0, y1-2):
            if y == y0 and abs(x+1-cx) < gate/2+2:
                continue
            parts.append(box(f"castle_merlon_{x}_{y}", [x, y, x+2, y+2], wall_top, wall_top+1.2,
                             "minecraft:stone_bricks", group))
    for tx in (x0, x1-12):
        for ty in (y0, y1-12):
            top = 1+params["tower_height_m"]
            for i, rect in enumerate(([tx,ty,tx+12,ty+1.2], [tx,ty+10.8,tx+12,ty+12],
                                      [tx,ty+1.2,tx+1.2,ty+10.8], [tx+10.8,ty+1.2,tx+12,ty+10.8])):
                parts.append(box(f"tower_{tx}_{ty}_wall_{i}", rect, 1.1, top, "minecraft:smooth_stone", group))
            for step in range(6):
                inset=step*.9
                parts.append(box(f"tower_{tx}_{ty}_roof_{step}", [tx-.5+inset,ty-.5+inset,tx+12.5-inset,ty+12.5-inset],
                                 top+step*params["tower_roof_m"]/6, top+(step+1)*params["tower_roof_m"]/6,
                                 "minecraft:dark_oak_planks" if params["roof_material"]=="slate" else "minecraft:oak_planks", group))
    kw, kd = params["keep_width_m"], params["keep_depth_m"]
    site = {"id":"castle_keep", "type":"residence", "rect":[cx-kw/2, y1-10-kd, cx+kw/2, y1-10], "entry_side":"south"}
    design = {"site_id":"castle_keep", "concept":params["concept"], "storeys":2, "storey_height_m":4,
              "roof":params["keep_roof"], "roof_height_m":2.5, "wall_material":"stone", "roof_material":params["roof_material"],
              "room_uses":[["hearth","counter"],["bed","store"]]}
    keep, semantic = raw_building(site, design)
    parts += keep
    return parts, semantic, site, design


def city_walls(base):
    """Perimeter with explicit, road-aligned gates and open river mouths."""
    parts=[]
    holes=[(y-1, y+base["street_width"]+1) for y in base["street_y"]]
    for x in (8, 502):
        cursor=8
        for low, high in holes+[(504,504)]:
            if low>cursor:
                parts.append(box(f"city_wall_{x}_{cursor}",[x,cursor,x+2,low],1,5.5,"minecraft:stone_bricks","city_walls"))
                for y in range(math.ceil(cursor), math.floor(low-1), 6):
                    parts.append(box(f"city_tooth_{x}_{y}",[x,y,x+2,y+2],5.5,6.5,"minecraft:smooth_stone","city_walls"))
            cursor=high
    left=base["river_x"]-base["river_width"]/2
    right=base["river_x"]+base["river_width"]/2
    for y in (8,502):
        cursor=8
        for low,high in ((66,78),(left-1,right+1),(322,334),(504,504)):
            if low>cursor:
                parts.append(box(f"city_wall_{y}_{cursor}",[cursor,y,low,y+2],1,5.5,"minecraft:stone_bricks","city_walls"))
                for x in range(math.ceil(cursor),math.floor(low-1),6):
                    parts.append(box(f"city_tooth_{y}_{x}",[x,y,x+2,y+2],5.5,6.5,"minecraft:smooth_stone","city_walls"))
            cursor=high
    return parts


def landscape(base, catalogue, reserved, roads):
    rng=random.Random(45)
    parts=[]
    forbidden=reserved+roads+[[base["river_x"]-base["river_width"]/2-8,0,base["river_x"]+base["river_width"]/2+8,512]]
    selected=[]
    attempts=0
    while len(selected)<catalogue["trees"]:
        attempts+=1
        require(attempts<10000,"city.vegetation","No safe vegetation capacity")
        x,y=rng.randint(18,494),rng.randint(18,494)
        if any(a-5<x<c+5 and b-5<y<d+5 for a,b,c,d in forbidden):continue
        if any(abs(x-xx)<6 and abs(y-yy)<6 for xx,yy in selected):continue
        selected.append((x,y))
        name=f"tree_{len(selected)}"
        h=rng.randint(5,8)
        parts.append(box(name+"_trunk",[x-.35,y-.35,x+.35,y+.35],1,1+h,"minecraft:oak_log","landscape"))
        for tier in range(3):
            radius=2.8-tier*.65
            parts.append(box(name+f"_crown{tier}",[x-radius,y-radius,x+radius,y+radius],h-2+tier*1.4,h+.2+tier*1.4,
                             "minecraft:oak_leaves" if len(selected)%3 else "minecraft:spruce_leaves","landscape"))
    for i in range(catalogue["lamps"]):
        row=i%4; y=base["street_y"][row]
        x=16+((i//4)*52)%216
        # Lamps sit beyond the travelled lane, outside plot and entry footprints.
        y+=base["street_width"]+24
        parts += [box(f"lamp_{i}_post",[x-.12,y-.12,x+.12,y+.12],1,5,"minecraft:dark_oak_planks","landscape"),
                  box(f"lamp_{i}_light",[x-.35,y-.35,x+.35,y+.35],5,5.7,"minecraft:glowstone","landscape")]
    return parts


def check_network(geometry, base, castle_site):
    """Check continuous supported clearance on actual road/bridge/castle geometry."""
    parts=[p for p in geometry["parts"] if p["block"]!="minecraft:water"]
    index=defaultdict(list)
    for part in parts:
        for key in buckets(part["bounds_wir_m"]):index[key].append(part["bounds_wir_m"])
    paths=[]
    for i,y in enumerate(base["street_y"]):
        paths.append({"id":f"cross_river_{i}","points":[[16,y+base["street_width"]/2,1.1],[496,y+base["street_width"]/2,1.1]]})
    for x in (72,328):
        paths.append({"id":f"north_south_{x}","points":[[x,4,1.1],[x,508,1.1]]})
    entry=geometry["buildings"]["castle_keep"]["entry"]
    x=castle_site["rect"][0]+entry["offset_m"]+entry["width_m"]/2
    cx=geometry["castle_x"]+64
    y=base["street_y"][-1]+base["street_width"]/2
    paths.append({"id":"castle_gate", "points":[[cx,y,1.1],[cx,442,1.1],[x,442,1.1],[x,castle_site["rect"][1]-1.3,1.1]]})
    for route in paths:
        dense=[]
        for a,b in zip(route["points"],route["points"][1:]):
            length=math.dist(a,b);steps=max(1,math.ceil(length/.25))
            for i in range(steps+1):
                p=[a[j]+(b[j]-a[j])*i/steps for j in range(3)]
                candidates={}
                for key in buckets([[p[0]-.28,p[1]-.28,0],[p[0]+.28,p[1]+.28,48]]):
                    for bounds in index[key]:candidates[id(bounds)]=bounds
                near=[(lo,hi) for lo,hi in candidates.values() if lo[0]<p[0]+.28 and hi[0]>p[0]-.28 and lo[1]<p[1]+.28 and hi[1]>p[1]-.28]
                support=any(lo[0]<=p[0]<hi[0] and lo[1]<=p[1]<hi[1] and abs(hi[2]-p[2])<.03 for lo,hi in near)
                clear=not any(lo[2]<p[2]+1.8 and hi[2]>p[2]+.035 for lo,hi in near)
                require(support and clear,"city.network",f"{route['id']}: unsupported or blocked at {p}")
                if not dense or dense[-1]!=p:dense.append(p)
        route["cells"]=dense
    return {"status":"pass","method":"quarter_metre_supported_clearance","routes":paths}


def construct_city(plans, *, routes=True):
    base,catalogue,layout,recipes=plans["B"],plans["C"],plans["D"],plans["E"]
    sites=project_sites(base,layout,catalogue)
    require(set(recipes)==set(RECIPE_IDS)|{"castle"},"city.design_coverage","Missing recipe/castle design")
    raw,roads,bridges=infrastructure(base)
    buildings={}
    for site in sites:
        params={**recipes[site["recipe_id"]],"site_id":site["id"]}
        require(site["type"]!="shop" or params["storeys"]==2,"city.shop_storeys","All shops need two floors")
        parts,semantic=raw_building(site,params)
        semantic["recipe_id"]=site["recipe_id"]
        raw+=parts;buildings[site["id"]]=semantic
    plazas=[]
    for i,y in enumerate(base["street_y"]):
        rect=[base["river_x"]-48,y+base["street_width"]+28,base["river_x"]-24,y+base["street_width"]+52]
        site={"id":f"plaza_{i}","rect":rect}
        plazas.append(rect)
        raw+=decorate_plaza(site,{"site_id":site["id"],"concept":"Fixed public square construction policy", "benches":4,"lamps":4,"trees":4,"fountain":True})
        # Link the plaza to the same row, not an isolated paved island.
        link=[rect[0]+10,y+base["street_width"],rect[0]+14,rect[1]]
        roads.append(link);raw.append(box(f"plaza_{i}_access",link,1,1.1,"minecraft:stone_bricks","roads"))
    castle,semantic,castle_site,keep_design=castle_parts(layout["castle_x"],recipes["castle"])
    raw+=castle;buildings["castle_keep"]=semantic
    buildings["castle_keep"]["recipe_id"]="castle"
    cx=layout["castle_x"]+64
    access=[cx-4,base["street_y"][-1],cx+4,434]
    roads.append(access);raw.append(box("castle_access",access,1,1.1,"minecraft:stone_bricks","roads"))
    raw+=city_walls(base)
    raw+=landscape(base,catalogue,[s["rect"] for s in sites]+plazas+[[layout["castle_x"],430,layout["castle_x"]+128,498]],roads)
    parts=disjoint(raw)
    check_no_overlap(parts)
    report={"status":"pass","builder":BUILDER,"region_m":512,"ordinary_buildings":48,"castle_keeps":1,
            "castle_towers":4,"plazas":4,"bridges":4,"trees_outside_plazas":catalogue["trees"],
            "part_count":len(parts),"recipe_instances":dict(Counter(s["recipe_id"] for s in sites)),
            "roof_styles":sorted({r["roof"] for k,r in recipes.items() if k!="castle"}),
            "wall_materials":sorted({r["wall_material"] for k,r in recipes.items() if k!="castle"})}
    require(len(report["roof_styles"])>=2 and len(report["wall_materials"])==2,"city.variety","At least two roof forms and both wall materials required")
    for group in buildings:
        pieces=[p for p in parts if p["group"]==group]
        for feature in ("window","porch","stair","roof"):
            if feature=="stair" and len(buildings[group]["design"]["storeys"])==1:continue
            require(any(feature in p["source_id"] for p in pieces),"city.features",f"{group}: missing {feature}")
    geometry={"version":VERSION,"builder":BUILDER,"parts":parts,"buildings":buildings,"sites":sites,
              "castle_x":layout["castle_x"],"castle_site":castle_site,"keep_design":keep_design,"report":report}
    geometry["network"]=check_network(geometry,base,castle_site)
    report["source_network_status"]="pass"
    if routes:
        geometry["walking"]=walking_routes(geometry)
        report["source_room_routes"]=len(geometry["walking"]["routes"])
        report["source_route_status"]="pass"
    else:
        geometry["walking"]={"status":"not_run","routes":[]}
    return geometry


class CitySupervisor(Supervisor):
    contract_version=VERSION
    geometry="bounded_city_recipes_v1"

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for stage in ("B","C","D","E","F"):
            self.skills[stage]=(Path(__file__).resolve().parents[3]/"skills"/"world-city-045"/f"{stage}.md").read_text("utf-8")

    def request_schema(self):
        schema=deepcopy(REQUEST_SCHEMA)
        schema["properties"]["contract_version"]={"const":VERSION}
        schema["properties"]["geometry"]={"const":self.geometry}
        schema["properties"]["dependencies"]=arr(obj(stage=enum("B","C","D","E"),sha256=HASH,data={"type":"object"}),0,4)
        return schema

    def response_contract(self,stage,plans,request_id=None,scope_id=None):
        scope=scope_id or getattr(self,"_scope","scene")
        payload=SCHEMAS.get(stage, REVIEW if stage=="F" else CASTLE if scope=="castle" else BUILDING)
        if stage=="E" and scope!="castle":
            payload=deepcopy(payload);payload["properties"]["site_id"]={"const":scope}
        return obj(contract_version={"const":VERSION},stage={"const":stage},
                   request_id={"const":request_id} if request_id else HASH,
                   scope_id={"const":scope} if scope_id else ID,payload=payload)

    def ask(self,stage,plans,*,scope_id="scene",**kwargs):
        self._scope=scope_id
        return super().ask(stage,plans,scope_id=scope_id,**kwargs)

    def validate_payload(self,stage,payload,plans,scope_id):
        if stage=="B":check_base(payload)
        elif stage=="C":check_catalogue(payload)
        elif stage=="D":project_sites(plans["B"],payload,plans["C"])
        elif stage=="E":
            if scope_id=="castle":castle_parts(plans["D"]["castle_x"],payload)
            else:
                require(scope_id.startswith("home") or payload["storeys"]==2,"city.shop_storeys","Shop recipes require two storeys")
                # Validate each actual dimension to which this recipe is assigned.
                for site in project_sites(plans["B"],plans["D"],plans["C"]):
                    if site["recipe_id"]==scope_id:raw_building(site,{**payload,"site_id":site["id"]})
        else:require(payload["verdict"]!="accept" or not payload["issues"],"city.review","Accept cannot contain issues")

    def run(self,prompt):
        self.prompt=prompt
        self.event("started",prompt=prompt,provider_mode="api" if self.provider.network else "replay")
        plans={}
        plans["B"]=self.ask("B",{})
        plans["C"]=self.ask("C",{"B":plans["B"]})
        plans["D"]=self.ask("D",{k:plans[k] for k in ("B","C")})
        plans["E"]={}
        for rid in (*RECIPE_IDS,"castle"):
            plans["E"][rid]=self.ask("E",{k:plans[k] for k in ("B","C","D")},scope_id=rid)
        write_json(self.root/"accepted_parameters.json",plans)
        self.event("construction_started")
        geometry=construct_city(plans)
        self.checkpoint()
        plans["F"]=self.ask("F",{"B":geometry["report"],"C":plans["C"]})
        require(plans["F"]["verdict"]=="accept","city.review_pending","F requested revision; no unvalidated publication")
        accepted={"contract_version":VERSION,"prompt":prompt,"seed":self.seed,"region_m":512,"plans":plans,
                  "accepted_responses":self.accepted,"skill_hashes":{s:digest(self.skills[s]) for s in ("B","C","D","E","F")},
                  "policy":"Model B/C/D and nine E recipes; local parcel, road, bridge, wall, vegetation and component execution"}
        write_json(self.root/"accepted.json",accepted)
        write_json(self.root/"city_geometry.json",geometry)
        return accepted,geometry
