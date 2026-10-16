"""046 WIR mesh-asset source snapshot and GLB derived from the exact same meshes."""
from copy import deepcopy
import hashlib
from pathlib import Path

from .compiler import STAMP
from .contracts import canonical, digest, strict_json
from .runtime import write_json
from .style_scene import COLORS, entity
from .nature_scene import VERSION, BUILDER
from .nature_mesh import glb
from .validation import require
from world_builder.storage.repository import Repository
from world_builder.storage.worldpkg import export_worldpkg

PALETTE={**COLORS,"terrain_grass":(.25,.39,.18,1),"terrain_grass_dark":(.20,.33,.16,1),
         "terrain_rock":(.43,.42,.38,1),"road_earth":(.38,.29,.18,1),"plaza_stone":(.46,.45,.40,1),
         "forest_pine":(.10,.23,.14,1),"forest_sage":(.20,.31,.18,1),
         "minecraft:barrel":(.52,.34,.19,1),"minecraft:furnace":(.42,.42,.41,1),
         "minecraft:oak_fence":(.52,.34,.19,1),"minecraft:red_bed":(.62,.18,.16,1)}


def save_nature_world(accepted,geometry,root):
    require(geometry["walking"]["status"]==geometry["network"]["status"]=="pass","nature.unvalidated","Source graph checks required")
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    identity=digest({"accepted":accepted,"geometry":geometry})[7:31];wid,rid="world_"+identity,"revision_"+identity
    region={"min":[0,0,0],"max":[768,768,192]}
    def record(*args,**kwargs):
        r=entity(*args,**kwargs);r["provenance"]["created_by"]=BUILDER;return r
    records=[{"record_type":"world_spec","id":"spec_nature046","source_prompt":accepted["prompt"],"world_seed":"0x000000000000002e",
              "region_bounds":region,"style_profile":"arcane_organic","target_profile_ids":[],"fantasy_exceptions":[],
              "extensions":{"contract_version":VERSION,"builder_version":BUILDER}},record(wid,"world",None,region)]
    groups={}
    for p in geometry["parts"]:
        low,high=p["bounds_wir_m"];g=p["group"]
        if g not in groups:groups[g]={"min":low[:],"max":high[:]}
        else:
            groups[g]["min"]=[min(groups[g]["min"][i],low[i]) for i in range(3)]
            groups[g]["max"]=[max(groups[g]["max"][i],high[i]) for i in range(3)]
    for g,bounds in groups.items():
        records.append(record("group_"+g,"building" if g in geometry["poses"] or g=="castle" else "landscape",wid,bounds,
                              local_pose=geometry["poses"].get(g),construction_policy=BUILDER))
    payload=canonical({"accepted":accepted,"geometry":geometry});asset_hash="sha256:"+hashlib.sha256(payload).hexdigest()
    assetid="asset_nature046"
    for i,p in enumerate(geometry["parts"]):
        low,high=p["bounds_wir_m"]
        require(all(0<=low[j]<=high[j]<=region["max"][j] for j in range(3)),"nature.bounds",f"Source mesh outside region: {p['source_id']}")
        r=record(p["name"],"terrain_mesh" if p["group"]=="terrain" else "mesh_component","group_"+p["group"],{"min":low,"max":high},
                 origin=groups[p["group"]]["min"],material=p["block"],component=p["source_id"],solid=p["solid"])
        r["geometry"]={"representation":"indexed_triangle_mesh_asset","asset_id":assetid,"mesh_index":i,"vertex_space":"world_RH_Z_up",
                       "vertex_count":len(p["vertices"]),"triangle_count":len(p["indices"])//3}
        records.append(r)
    records.append({"record_type":"asset","id":assetid,"content_hash":asset_hash,"uri":"assets/sha256/"+asset_hash[7:],
                    "media_type":"application/json","length_unit":"m","axis":"RH_Z_up","bounds":region,
                    "license":{"spdx":"LicenseRef-UserModelOutput","source":"local-terrain-construction-and-recorded-model-recipes"}})
    manifest={"package_format":"worldpkg-json-snapshot","schema_version":"0.1.0","package_id":"package_"+identity,"world_id":wid,"revision_id":rid,
              "required_capabilities":["wir.core/0.1","wir.constraints/0.1","wir.revisions/0.1"],"units":{"length":"m","angle":"rad"},
              "coordinate_system":{"handedness":"right","x_axis":"east","y_axis":"north","z_axis":"up","transform_convention":"column_vector_parent_times_local","quaternion_order":"xyzw","storage_precision":"float64"},
              "tolerances":{"regional_m":.1,"building_m":.01,"interior_m":.005,"angle_rad":.0001},"package_mode":"self_contained","created_at":STAMP,
              "optional_extensions":{"nature046":VERSION,"builder":BUILDER,"mesh_asset":"indexed_triangle_mesh_asset/1"}}
    records.append({"record_type":"revision","id":rid,"world_id":wid,"parent_revision_ids":[],"created_at":STAMP,"author":"api-nature046",
                    "change_set_hash":digest(records),"validation_summary":{"hard_failures":0,"unknown_checks":0},"committed":True,
                    "extensions":{"snapshot_manifest":deepcopy(manifest)}})
    package=strict_json(canonical({"manifest":manifest,"records":records}))
    next(r for r in package["records"] if r["record_type"]=="revision")["change_set_hash"]=digest([r for r in package["records"] if r["record_type"]!="revision"])
    # commit validates the package; export_worldpkg validates its loaded snapshot
    # and rereads the temporary archive before atomic publication.
    directory=root/"unity";directory.mkdir(parents=True,exist_ok=True)
    encoded,materials=glb(geometry["parts"],PALETTE);(directory/"scene.glb").write_bytes(encoded)
    glbhash="sha256:"+hashlib.sha256(encoded).hexdigest()
    pieces=[{"name":p["name"],"source_id":p["name"],"group":p["group"],"component":p["source_id"],"bounds_wir_m":p["bounds_wir_m"],"solid":p["solid"],"material":materials[p["block"]]} for p in geometry["parts"]]
    write_json(directory/"manifest.json",{"version":VERSION,"source_id":wid,"source_revision_id":rid,"piece_count":len(pieces),"glb_sha256":glbhash,"pieces":pieces,"target_load":"not_run"})
    repo=Repository(root/"repository");repo.publish(payload);repo.commit(package,None)
    archive=export_worldpkg(repo,wid,root/"scene.worldpkg")
    write_json(root/"repository/scene.world.json",package)
    result={"world_id":wid,"revision_id":rid,"region_m":768,"worldpkg_sha256":archive,"source_geometry_validation":"pass",
            "exports":{"unity":{"mesh_count":len(pieces),"sha256":glbhash}},"target_load":"not_run","walkthrough":"not_run"}
    write_json(root/"result.json",result);return result
