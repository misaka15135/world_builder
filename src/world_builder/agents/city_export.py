"""Self-contained WIR and GLB publication of the validated 045 city geometry."""
from copy import deepcopy
import hashlib
from pathlib import Path

from .city_scene import VERSION, BUILDER
from .compiler import STAMP
from .contracts import canonical, digest, strict_json
from .runtime import write_json
from .style_scene import COLORS, entity
from .validation import require
from world_builder.adapters.unity.sample import _box, _glb
from world_builder.storage.repository import Repository
from world_builder.storage.worldpkg import export_worldpkg, read_worldpkg
from world_builder.wir.validator import validate_package

PALETTE={**COLORS,"minecraft:gravel":(.40,.39,.35,1),"minecraft:spruce_leaves":(.12,.29,.22,1)}


def save_city_world(accepted,geometry,root):
    require(geometry["walking"]["status"]=="pass","city.unvalidated","Source room routes must pass before publication")
    require(geometry["network"]["status"]=="pass","city.unvalidated","Road network must pass before publication")
    root=Path(root)
    identity=digest({"accepted":accepted,"geometry":geometry})[7:31]
    wid,rid="world_"+identity,"revision_"+identity
    region={"min":[0,0,0],"max":[512,512,48]}
    def make_entity(*args,**kwargs):
        record=entity(*args,**kwargs);record["provenance"]["created_by"]=BUILDER
        return record
    records=[{"record_type":"world_spec","id":"spec_city045","source_prompt":accepted["prompt"],
              "world_seed":f"0x{accepted['seed']:016x}","region_bounds":region,"style_profile":"arcane_medieval",
              "target_profile_ids":[],"fantasy_exceptions":[],"extensions":{"contract_version":VERSION,"builder_version":BUILDER,"plans_sha256":digest(accepted)}},
             make_entity(wid,"world",None,region)]
    groups={}
    for part in geometry["parts"]:
        low,high=part["bounds_wir_m"];group=part["group"]
        if group not in groups:groups[group]={"min":low[:],"max":high[:]}
        else:
            groups[group]["min"]=[min(groups[group]["min"][i],low[i]) for i in range(3)]
            groups[group]["max"]=[max(groups[group]["max"][i],high[i]) for i in range(3)]
    for group,bounds in groups.items():
        semantic=geometry["buildings"].get(group,{})
        recipe=semantic.get("recipe_id", "castle" if group=="castle" else None)
        records.append(make_entity("group_"+group,"building" if group in geometry["buildings"] or group=="castle" else "open_space",wid,bounds,
                                   construction_policy=BUILDER,recipe_id=recipe,model_parameters=accepted["plans"]["E"].get(recipe,{})))
    materials=sorted({p["block"] for p in geometry["parts"]})
    pieces=[];exported=[]
    for index,part in enumerate(geometry["parts"]):
        low,high=part["bounds_wir_m"];name=f"part_{index:05}";group=part["group"]
        records.append(make_entity(name,"component","group_"+group,{"min":low,"max":high},origin=groups[group]["min"],
                                   material=part["block"],legacy_component=part["source_id"],rgba=PALETTE.get(part["block"],(.52,.34,.19,1))))
        piece=_box(name,name,low[0],high[0],low[1],high[1],low[2],high[2],materials.index(part["block"]))
        pieces.append(piece)
        exported.append({**piece,"group":group,"component":part["source_id"],"solid":part["block"]!="minecraft:water"})
    payload=canonical({"accepted":accepted,"geometry":geometry})
    asset_hash="sha256:"+hashlib.sha256(payload).hexdigest()
    records.append({"record_type":"asset","id":"asset_city045","content_hash":asset_hash,"uri":"assets/sha256/"+asset_hash[7:],
                    "media_type":"application/json","length_unit":"m","axis":"RH_Z_up","bounds":region,
                    "license":{"spdx":"LicenseRef-UserModelOutput","source":"local-construction-and-configured-model"}})
    manifest={"package_format":"worldpkg-json-snapshot","schema_version":"0.1.0","package_id":"package_"+identity,
              "world_id":wid,"revision_id":rid,"required_capabilities":["wir.core/0.1","wir.constraints/0.1","wir.revisions/0.1"],
              "units":{"length":"m","angle":"rad"},"coordinate_system":{"handedness":"right","x_axis":"east","y_axis":"north","z_axis":"up",
              "transform_convention":"column_vector_parent_times_local","quaternion_order":"xyzw","storage_precision":"float64"},
              "tolerances":{"regional_m":.1,"building_m":.01,"interior_m":.005,"angle_rad":.0001},
              "package_mode":"self_contained","created_at":STAMP,"optional_extensions":{"city045":VERSION,"builder":BUILDER}}
    records.append({"record_type":"revision","id":rid,"world_id":wid,"parent_revision_ids":[],"created_at":STAMP,
                    "author":"api-city045","change_set_hash":digest(records),"validation_summary":{"hard_failures":0,"unknown_checks":0},
                    "committed":True,"extensions":{"snapshot_manifest":deepcopy(manifest)}})
    package=strict_json(canonical({"manifest":manifest,"records":records}))
    next(r for r in package["records"] if r["record_type"]=="revision")["change_set_hash"]=digest(
        [r for r in package["records"] if r["record_type"]!="revision"])
    validate_package(package)
    directory=root/"unity";directory.mkdir(parents=True,exist_ok=True)
    glb=_glb(pieces,[(m,PALETTE.get(m,(.52,.34,.19,1))) for m in materials]);(directory/"scene.glb").write_bytes(glb)
    glbhash="sha256:"+hashlib.sha256(glb).hexdigest()
    write_json(directory/"manifest.json",{"version":VERSION,"source_id":wid,"source_revision_id":rid,"piece_count":len(pieces),
               "glb_sha256":glbhash,"pieces":exported,"target_load":"not_run","walkthrough":"not_run"})
    write_json(directory/"routes.json",geometry["walking"])
    repo=Repository(root/"repository");repo.publish(payload);repo.commit(package,None)
    archive=export_worldpkg(repo,wid,root/"scene.worldpkg")
    require(read_worldpkg(root/"scene.worldpkg")[0]==package,"city.archive","World package differs from source")
    write_json(root/"repository/scene.world.json",package)
    result={"world_id":wid,"revision_id":rid,"worldpkg_sha256":archive,"source_geometry_validation":"pass",
            "region_m":512,"exports":{"unity":{"mesh_count":len(pieces),"sha256":glbhash}},
            "target_load":"not_run","walkthrough":"not_run","minecraft":"not_exported"}
    write_json(root/"result.json",result)
    return result
