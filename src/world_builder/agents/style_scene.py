"""042: bounded model layout/design parameters compiled with legacy detail.

Independent contract; no fallback to the legacy scene planner. Construction
policy is explicit, versioned, and compiled into the source WIR before export.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import replace
import hashlib
import math
from pathlib import Path

from .contracts import ID, HASH, REQUEST_SCHEMA, arr, canonical, digest, enum, integer, obj, string, strict_json, validate_schema
from .geometry_normalization import _subtract
from .runtime import Supervisor, write_json
from .validation import require
from .compiler import STAMP, record_entity
from world_builder.planning.catalogue import load_setting_pack
from world_builder.planning.designer import load_designs, design_building, validate_design
from world_builder.planning.siting import Site
from world_builder.planning.assembler import _stair_void_local
from world_builder.adapters.minecraft.city import _building_shell
from world_builder.adapters.unity.sample import _glb, _box
from world_builder.storage.repository import Repository
from world_builder.storage.worldpkg import export_worldpkg, read_worldpkg
from world_builder.wir.validator import validate_package

VERSION = "0.1.1-style042"
BUILDER = "legacy-detail-042.1"
NUMBER = {"type": "number", "minimum": 0, "maximum": 128}
RECT = arr(integer(2, 62), 4, 4)
LAYOUT = obj(title=string(120), concept=string(800), ground_height_m={"const": 1},
             road=obj(id=ID, rect=RECT),
             sites=arr(obj(id=ID, type=enum("residence", "shop", "plaza"), rect=RECT,
                           entry_side=enum("north", "south")), 5, 5))
LAYOUT_PARAMETERS = obj(title=string(120),concept=string(800),
                        road_y=integer(20,34),road_width=integer(4,8),
                        sites=arr(obj(id=ID,type=enum("residence","shop","plaza"),
                                      bank=enum("north","south"),x=integer(2,50),
                                      width=integer(12,20),depth=integer(10,18)),5,5))
BUILDING = obj(site_id=ID, concept=string(800), storeys=integer(1, 2),
               storey_height_m={"type": "number", "minimum": 3.4, "maximum": 4},
               roof=enum("flat", "gable", "spire"),
               roof_height_m={"type": "number", "minimum": 1, "maximum": 2.5},
               wall_material=enum("stone", "plaster"), roof_material=enum("wood", "slate"),
               room_uses=arr(arr(enum("hearth", "bed", "store", "counter", "stall", "kitchen"), 2, 2), 1, 2))
PLAZA = obj(site_id=ID, concept=string(800), benches=integer(2, 4), lamps=integer(2, 4),
            trees=integer(2, 4), fountain={"const": True})
REVIEW = obj(verdict=enum("accept", "revise"), evidence=string(1200),
             issues=arr(obj(site_id=ID, reason=string(600)), 0, 5), limitations=arr(string(600), 0, 12))


def rect_box(rect, z0=1, z1=12):
    return {"min": [rect[0], rect[1], z0], "max": [rect[2], rect[3], z1]}


def response_contract(stage, plans, request_id=None, scope_id=None):
    schema = LAYOUT_PARAMETERS if stage == "D" else REVIEW if stage == "F" else (
        PLAZA if next(s for s in plans["D"]["sites"] if s["id"] == scope_id)["type"] == "plaza" else BUILDING)
    return obj(contract_version={"const": VERSION}, stage={"const": stage},
               request_id={"const": request_id} if request_id else HASH,
               scope_id={"const": scope_id} if scope_id else ID, payload=schema)


def check_layout(layout):
    validate_schema(layout, LAYOUT)
    require(Counter(s["type"] for s in layout["sites"]) == {"residence": 2, "shop": 2, "plaza": 1},
            "style.coverage", "Exactly two residences, two shops, one plaza required")
    require(len({s["id"] for s in layout["sites"]}) == 5, "style.ids", "Duplicate site IDs")
    road = layout["road"]["rect"]
    require(road[2] - road[0] >= 50 and 4 <= road[3] - road[1] <= 8,
            "style.road", "Road must run east-west, length >=50, width 4..8 m")
    for i, site in enumerate(layout["sites"]):
        x0, y0, x1, y1 = site["rect"]
        require(12 <= x1-x0 <= 20 and 10 <= y1-y0 <= 18,
                "style.size", f"{site['id']}: width 12..20, depth 10..18 required")
        edge = y0 == road[3] if site["entry_side"] == "south" else y1 == road[1]
        require(edge and road[0] <= x0 and x1 <= road[2], "style.frontage",
                f"{site['id']}: selected entry facade must touch and lie within the road frontage")
        for other in layout["sites"][:i]:
            a, b, c, d = other["rect"]
            require(x1+2 <= a or c+2 <= x0 or y1+2 <= b or d+2 <= y0,
                    "style.clearance", "Site rectangles must leave >=2 m gap")


def project_layout(parameters):
    validate_schema(parameters,LAYOUT_PARAMETERS)
    y,w=parameters["road_y"],parameters["road_width"]
    sites=[]
    for s in parameters["sites"]:
        y0=y+w if s["bank"]=="north" else y-s["depth"]
        sites.append({"id":s["id"],"type":s["type"],"rect":[s["x"],y0,s["x"]+s["width"],y0+s["depth"]],
                      "entry_side":"south" if s["bank"]=="north" else "north"})
    layout={"title":parameters["title"],"concept":parameters["concept"],"ground_height_m":1,
            "road":{"id":"main_street","rect":[2,y,62,y+w]},"sites":sites}
    check_layout(layout)
    return layout


def raw_building(site, params):
    """Invoke the old single-building executor with only accepted parameters."""
    validate_schema(params, BUILDING)
    require(params["site_id"] == site["id"], "style.scope", "Wrong site_id")
    require(len(params["room_uses"]) == params["storeys"], "style.rooms", "One room-use pair per storey")
    pack = load_setting_pack("arcane_medieval")
    template = replace(load_designs(pack.id)[site["type"]], storeys=(params["storeys"], params["storeys"]),
                       storey_height_m=params["storey_height_m"], roof=params["roof"],
                       roof_height_m=params["roof_height_m"], setback_m=0,
                       stair="straight", room_uses=tuple(tuple(r) for r in params["room_uses"]))
    entry = replace(pack.entries[site["type"]], height_m_range=None)
    x0, y0, x1, y1 = site["rect"]
    envelope = Site(site["id"], site["type"], entry.role, "implemented", "block", "district",
                    x0, y0, x1, y1, 12, params["storeys"], (), ())
    design = design_building(envelope, entry, pack, template, entry_side=site["entry_side"],
                             seed=41, storeys=params["storeys"])
    report = validate_design(design, envelope, entry)
    require(report["state"] == "pass", "style.design", str([c for c in report["checks"] if c["state"] != "pass"]))
    require(design.entry_side == site["entry_side"] and len(design.storeys) == params["storeys"],
            "style.changed_design", "Builder changed a model-selected entry or floor count")
    base, floor = 1, .3
    building = {"id": site["id"], "kind":"building", "parent_id":None, "bounds": rect_box(site["rect"], base, base+design.height_m),
                "attributes": {"storeys": params["storeys"], "interior_state": "generated"},
                "geometry": {"representation": "parametric_building", "storey_height_m": design.storey_height_m,
                             "wall_thickness_m": .3, "floor_thickness_m": floor,
                             "roof_height_m": design.roof_height_m, "roof_style": design.roof,
                             "storey_insets_local_m": [[0,0,0,0] for _ in design.storeys],
                             "entry": {"side": design.entry_side, "offset_m": design.entry_offset_m,
                                       "width_m": 2, "height_m": 2.4},
                             "stair_void_local_m": _stair_void_local(design), "assignment": "scene_pipeline_stage_e"}}
    records = {building["id"]: building}
    rooms = []
    for level in design.storeys:
        sid = f"{site['id']}_storey_{level.index}"
        z = base+level.z_m
        records[sid] = {"id": sid, "kind": "storey", "parent_id": site["id"],
                        "bounds": rect_box([level.x0,level.y0,level.x1,level.y1], z, z+design.storey_height_m)}
        for room in level.rooms:
            bounds = rect_box([room.x0,room.y0,room.x1,room.y1], z+floor, z+design.storey_height_m-.3)
            records[room.id] = {"id": room.id, "kind": "room", "parent_id": sid, "bounds": bounds}
            rooms.append({"id": room.id, "bounds": bounds, "level": level.index, "use": room.use})
        left,right = level.rooms
        pid = sid+"_partition"
        records[pid] = {"id":pid,"kind":"partition","parent_id":sid,
                        "bounds":rect_box([left.x0,left.y1,left.x1,right.y0],z+floor,z+design.storey_height_m-.3),
                        "attributes":{"opening":{"side":"west","width_m":2,"height_m":2}}}
    for item in design.furniture:
        room = next(r for r in rooms if r["id"] == item.room_id)
        records[item.id] = {"id":item.id,"kind":"furniture","parent_id":item.room_id,
                            "bounds":rect_box([item.x0,item.y0,item.x0+1,item.y0+1], room["bounds"]["min"][2],
                                               room["bounds"]["min"][2]+item.height_m),"attributes":{"use":item.use}}
    if design.stair:
        s = design.stair
        sid=site["id"]+"_stair"
        records[sid]={"id":sid,"kind":"stair","parent_id":site["id"],
                      "bounds":rect_box([s["x0"],s["y0"],s["x0"]+s["width_m"],s["y0"]+s["run_m"]+s["landing_m"]],1.3,1.3+s["rise_m"]),
                      "geometry":{"representation":"straight_stair","steps":s["steps"],"run_m":s["run_m"],"rise_m":s["rise_m"],"clear_width_m":s["width_m"],
                                  "floor_levels_m":[1.3,1.3+s["rise_m"]]}}
    raw = _building_shell(building, records, with_interior=True, style="arcane_medieval")
    for part in raw:
        part["group"] = site["id"]
        part["bounds_wir_m"]=[[part["x0"],-part["z1"],part["y0"]],[part["x1"],-part["z0"],part["y1"]]]
        if "roof" in part["source_id"]:
            part["block"] = "minecraft:dark_oak_planks" if params["roof_material"] == "slate" else "minecraft:oak_planks"
        elif part["block"] == "minecraft:smooth_stone" and params["wall_material"] == "plaster":
            part["block"] = "minecraft:white_concrete"
    return raw, {"design": design.to_dict(), "rooms": rooms, "entry": building["geometry"]["entry"],
                 "source_design_validation": report, "wall_material": params["wall_material"],
                 "roof_material": params["roof_material"]}


def box(name, rect, z0, z1, material, group):
    return {"source_id": name, "bounds_wir_m": [[rect[0],rect[1],z0],[rect[2],rect[3],z1]],
            "block":material,"group":group}


def decorate_plaza(site, params):
    validate_schema(params, PLAZA)
    require(params["site_id"] == site["id"], "style.scope", "Wrong plaza site_id")
    x0,y0,x1,y1=site["rect"]
    cx,cy=(x0+x1)/2,(y0+y1)/2
    g=site["id"]
    parts=[box(g+"_paving",site["rect"],1,1.15,"minecraft:stone_bricks",g)]
    parts += [box(g+"_fountain_base",[cx-2,cy-2,cx+2,cy+2],1.15,1.5,"minecraft:smooth_stone",g),
              box(g+"_fountain_water",[cx-1.5,cy-1.5,cx+1.5,cy+1.5],1.5,1.65,"minecraft:water",g),
              box(g+"_fountain_column",[cx-.35,cy-.35,cx+.35,cy+.35],1.15,3.4,"minecraft:stone_bricks",g)]
    for kind,count in (("bench",params["benches"]),("lamp",params["lamps"]),("tree",params["trees"])):
        for i in range(count):
            x=x0+2+(x1-x0-4)*(i+.5)/count
            y=y0+2 if kind=="bench" else y1-2 if kind=="tree" else cy
            name=f"{g}_{kind}_{i}"
            if kind=="bench":
                parts += [box(name+"_seat",[x-1,y-.35,x+1,y+.35],1.5,1.8,"minecraft:oak_planks",g),
                          box(name+"_back",[x-1,y+.25,x+1,y+.4],1.8,2.4,"minecraft:dark_oak_planks",g)]
                for dx in (-.7,.7):
                    parts.append(box(name+f"_leg_{dx}",[x+dx-.1,y-.2,x+dx+.1,y+.2],1.15,1.5,"minecraft:dark_oak_planks",g))
            elif kind=="lamp":
                parts += [box(name+"_post",[x-.12,y-.12,x+.12,y+.12],1.15,4,"minecraft:dark_oak_planks",g),
                          box(name+"_light",[x-.3,y-.3,x+.3,y+.3],4,4.6,"minecraft:glowstone",g)]
            else:
                parts += [box(name+"_trunk",[x-.25,y-.25,x+.25,y+.25],1.15,3.4,"minecraft:oak_log",g),
                          box(name+"_crown",[x-1,y-1,x+1,y+1],3.4,5.3,"minecraft:oak_leaves",g)]
    return parts


def disjoint_parts(raw):
    """Preserve legacy last-painted solid material while eliminating z-fighting."""
    result=[]
    for part in reversed(raw):
        fragments=[{"min":part["bounds_wir_m"][0],"max":part["bounds_wir_m"][1]}]
        for later in result:
            b={"min":later["bounds_wir_m"][0],"max":later["bounds_wir_m"][1]}
            fragments=[cut for f in fragments for cut in _subtract(f,b)]
        for i,f in enumerate(fragments):
            fresh={**part,"bounds_wir_m":[f["min"],f["max"]],"name":part["source_id"]+f"_piece{i}"}
            result.append(fresh)
        require(len(result)<=8000,"style.parts","Detail split budget exceeded")
    return list(reversed(result))


def construct(layout, designs):
    check_layout(layout)
    require(set(designs)=={s["id"] for s in layout["sites"]},"style.coverage","Missing site design")
    raw=[box("terrain",[0,0,64,64],0,1,"minecraft:grass_block","terrain"),
         box("road",layout["road"]["rect"],.8,1.1,"minecraft:stone_bricks","road")]
    buildings={}
    for site in layout["sites"]:
        if site["type"]=="plaza":
            raw += decorate_plaza(site,designs[site["id"]])
        else:
            parts,semantic=raw_building(site,designs[site["id"]])
            raw+=parts
            buildings[site["id"]]=semantic
    parts=disjoint_parts(raw)
    report={"status":"pass","builder":BUILDER,"decision_fields":"layout + per-site parameters",
            "building_count":len(buildings),"part_count":len(parts),"sites":{}}
    for site in layout["sites"]:
        g=site["id"]
        pieces=[p for p in parts if p["group"]==g]
        if site["type"]=="plaza":
            report["sites"][g]={"type":"plaza","fountain":True,"benches":designs[g]["benches"],
                                 "lamps":designs[g]["lamps"],"trees":designs[g]["trees"]}
        else:
            counts={tag:sum(tag in p["source_id"] for p in pieces) for tag in ("window","porch","stair","roof")}
            require(counts["window"]>0 and counts["porch"]>0 and counts["roof"]>0,"style.features",f"{g}: missing detail")
            require(designs[g]["storeys"]==1 or counts["stair"]>0,"style.stair",f"{g}: missing stair")
            report["sites"][g]={"type":site["type"],"storeys":designs[g]["storeys"],"features":counts}
    geometry={"version":VERSION,"builder":BUILDER,"parts":parts,"buildings":buildings,"report":report}
    from .style_routes import walking_routes
    geometry["walking"]=walking_routes(geometry)
    report["source_room_routes"]=len(geometry["walking"]["routes"])
    report["source_route_status"]="pass"
    return geometry


class StyleSupervisor(Supervisor):
    contract_version=VERSION
    geometry="parametric_style_v1"

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for stage in ("D","E","F"):
            self.skills[stage]=(Path(__file__).resolve().parents[3]/"skills"/"world-style-042"/f"{stage}.md").read_text("utf-8")

    def request_schema(self):
        schema=deepcopy(REQUEST_SCHEMA)
        schema["properties"]["contract_version"]={"const":VERSION}
        schema["properties"]["geometry"]={"const":self.geometry}
        schema["properties"]["dependencies"]=arr(obj(stage=enum("D","E","B"),sha256=HASH,data={"type":"object"}),0,3)
        return schema

    def response_contract(self,stage,plans,request_id=None,scope_id=None):
        # Unbound E schema still depends on the current site's type.
        return response_contract(stage,plans,request_id,scope_id or self._scope)

    def ask(self,stage,plans,*,scope_id="scene",**kwargs):
        # Style tasks are sequential: avoid mutable per-site schema state in workers.
        self._scope=scope_id
        return super().ask(stage,plans,scope_id=scope_id,**kwargs)

    def validate_payload(self,stage,payload,plans,scope_id):
        if stage=="D":
            projected=project_layout(payload)
            write_json(self.root/"layout_projection.json",{"version":VERSION,"raw_parameters":payload,
                       "raw_sha256":digest(payload),"projected_sha256":digest(projected),"projected":projected})
            return projected
        elif stage=="E":
            site=next(s for s in plans["D"]["sites"] if s["id"]==scope_id)
            require(site["type"]!="shop" or payload["storeys"]==2,"style.programme","Shop requires two storeys")
            decorate_plaza(site,payload) if site["type"]=="plaza" else raw_building(site,payload)
        else:
            require(payload["verdict"]!="accept" or not payload["issues"],"style.review","Accept cannot contain issues")

    def run(self,prompt):
        self.prompt=prompt
        self.event("started",prompt=prompt,provider_mode="api" if self.provider.network else "replay")
        layout=self.ask("D",{})
        designs={s["id"]:self.ask("E",{"D":layout},scope_id=s["id"]) for s in sorted(layout["sites"],key=lambda s:s["id"])}
        geometry=construct(layout,designs)
        review=self.ask("F",{"D":layout,"E":designs,"B":geometry["report"]})
        require(review["verdict"]=="accept","style.review_pending","Model requested review; no unvalidated publication")
        accepted={"contract_version":VERSION,"prompt":prompt,"region_m":64,"seed":self.seed,
                  "plans":{"D":layout,"E":designs,"F":review},"accepted_responses":self.accepted,
                  "skill_hashes":{s:digest(self.skills[s]) for s in ("D","E","F")}}
        write_json(self.root/"accepted.json",accepted)
        write_json(self.root/"style_geometry.json",geometry)
        return accepted,geometry


COLORS={"minecraft:smooth_stone":(.68,.67,.62,1),"minecraft:stone_bricks":(.48,.48,.46,1),
        "minecraft:oak_planks":(.54,.36,.18,1),"minecraft:dark_oak_planks":(.23,.14,.085,1),
        "minecraft:white_concrete":(.87,.81,.65,1),"minecraft:grass_block":(.32,.49,.22,1),
        "minecraft:glass":(.55,.78,.85,.32),"minecraft:water":(.16,.49,.69,.65),
        "minecraft:oak_leaves":(.19,.39,.17,1),"minecraft:oak_log":(.36,.24,.12,1),
        "minecraft:glowstone":(1,.73,.24,1)}


def entity(id,kind,parent,bounds,origin=(0,0,0),material=None,**attrs):
    integral={"min":[math.floor(v) for v in bounds["min"]],"max":[math.ceil(v) for v in bounds["max"]]}
    record=record_entity(id,kind,parent,integral,material=material,**attrs)
    record["bounds"]=deepcopy(bounds)
    record["transform"]["translation"]=[bounds["min"][i]-origin[i] for i in range(3)]
    if material:
        record["geometry"]["size_m"]=[bounds["max"][i]-bounds["min"][i] for i in range(3)]
    record["provenance"]["created_by"]=BUILDER
    return record


def save_style_world(accepted,geometry,root):
    """Store actual detailed geometry in WIR; GLB is only its serialization."""
    root=Path(root)
    identity=digest({"accepted":accepted,"geometry":geometry})[7:31]
    wid,rid="world_"+identity,"revision_"+identity
    region={"min":[0,0,0],"max":[64,64,24]}
    records=[{"record_type":"world_spec","id":"spec_style042","source_prompt":accepted["prompt"],
              "world_seed":f"0x{accepted['seed']:016x}","region_bounds":region,
              "style_profile":"arcane_medieval","target_profile_ids":[],"fantasy_exceptions":[],
              "extensions":{"contract_version":VERSION,"builder_version":BUILDER,"plans_sha256":digest(accepted)}},
             entity(wid,"world",None,region)]
    groups={}
    for part in geometry["parts"]:
        low,high=part["bounds_wir_m"]
        if part["group"] not in groups:
            groups[part["group"]]={"min":low[:],"max":high[:]}
        else:
            g=groups[part["group"]]
            g["min"]=[min(g["min"][i],low[i]) for i in range(3)]
            g["max"]=[max(g["max"][i],high[i]) for i in range(3)]
    for g,bounds in groups.items():
        records.append(entity("group_"+g,"building" if g in geometry["buildings"] else "open_space",wid,bounds,
                              model_parameters=accepted["plans"]["E"].get(g,{}),construction_policy=BUILDER))
    materials=sorted({p["block"] for p in geometry["parts"]})
    pieces=[]
    exported=[]
    for index,part in enumerate(geometry["parts"]):
        low,high=part["bounds_wir_m"]
        name=f"part_{index:04}"
        group="group_"+part["group"]
        record=entity(name,"component",group,{"min":low,"max":high},origin=groups[part["group"]]["min"],
                      material=part["block"],legacy_component=part["source_id"],rgba=COLORS.get(part["block"],(.52,.34,.19,1)))
        records.append(record)
        piece=_box(name,name,low[0],high[0],low[1],high[1],low[2],high[2],materials.index(part["block"]))
        pieces.append(piece)
        exported.append({**piece,"group":part["group"],"component":part["source_id"],
                         "solid":part["block"]!="minecraft:water"})
    payload=canonical({"accepted":accepted,"geometry":geometry})
    asset_hash="sha256:"+hashlib.sha256(payload).hexdigest()
    records.append({"record_type":"asset","id":"asset_style042","content_hash":asset_hash,
                    "uri":"assets/sha256/"+asset_hash[7:],"media_type":"application/json",
                    "length_unit":"m","axis":"RH_Z_up","bounds":region,
                    "license":{"spdx":"LicenseRef-UserModelOutput","source":"local-construction-and-configured-model"}})
    manifest={"package_format":"worldpkg-json-snapshot","schema_version":"0.1.0","package_id":"package_"+identity,
              "world_id":wid,"revision_id":rid,"required_capabilities":["wir.core/0.1","wir.constraints/0.1","wir.revisions/0.1"],
              "units":{"length":"m","angle":"rad"},"coordinate_system":{"handedness":"right","x_axis":"east", "y_axis":"north",
              "z_axis":"up","transform_convention":"column_vector_parent_times_local","quaternion_order":"xyzw","storage_precision":"float64"},
              "tolerances":{"regional_m":.1,"building_m":.01,"interior_m":.005,"angle_rad":.0001},
              "package_mode":"self_contained","created_at":STAMP,"optional_extensions":{"style042":VERSION,"builder":BUILDER}}
    records.append({"record_type":"revision","id":rid,"world_id":wid,"parent_revision_ids":[],"created_at":STAMP,
                    "author":"api-style042","change_set_hash":digest(records),"validation_summary":{"hard_failures":0,"unknown_checks":0},
                    "committed":True,"extensions":{"snapshot_manifest":manifest}})
    package=strict_json(canonical({"manifest":manifest,"records":records}))
    next(r for r in package["records"] if r["record_type"]=="revision")["change_set_hash"]=digest(
        [r for r in package["records"] if r["record_type"]!="revision"])
    validate_package(package)
    directory=root/"unity"
    directory.mkdir(parents=True,exist_ok=True)
    glb=_glb(pieces,[(m,COLORS.get(m,(.52,.34,.19,1))) for m in materials])
    (directory/"scene.glb").write_bytes(glb)
    glbhash="sha256:"+hashlib.sha256(glb).hexdigest()
    export={"version":VERSION,"source_id":wid,"source_revision_id":rid,"piece_count":len(pieces),
            "glb_sha256":glbhash,"pieces":exported,"target_load":"not_run","walkthrough":"not_run"}
    write_json(directory/"manifest.json",export)
    write_json(directory/"routes.json",geometry["walking"])
    repository=Repository(root/"repository")
    repository.publish(payload)
    repository.commit(package,None)
    archive=export_worldpkg(repository,wid,root/"scene.worldpkg")
    require(read_worldpkg(root/"scene.worldpkg")[0]==package,"style.archive","Archive differs from source")
    write_json(root/"repository"/"scene.world.json",package)
    result={"world_id":wid,"revision_id":rid,"worldpkg_sha256":archive,"source_geometry_validation":"pass",
            "exports":{"unity":{"mesh_count":len(pieces),"sha256":glbhash}},"target_load":"not_run","walkthrough":"not_run"}
    write_json(root/"result.json",result)
    return result
