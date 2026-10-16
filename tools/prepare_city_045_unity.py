"""Copy a validated 045 GLB and prepare selected physical test routes for Unity."""
import argparse
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from world_builder.agents.contracts import ROOT, strict_json
from world_builder.agents.runtime import write_json
from prepare_style_042_unity import target_path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,required=True)
    args=parser.parse_args()
    source=args.source.resolve()
    destination=ROOT/"adapters/unity/style042_project/Assets/Generated/City"
    destination.mkdir(parents=True,exist_ok=True)
    for name in ("scene.glb","manifest.json"):shutil.copyfile(source/"unity"/name,destination/name)
    geometry=strict_json((source/"city_geometry.json").read_bytes())
    accepted=strict_json((source/"accepted.json").read_bytes())
    manifest=strict_json((source/"unity/manifest.json").read_bytes())
    bounds={"pieces":[{"name":p["name"],"min":{"x":p["bounds_wir_m"][0][0],"y":p["bounds_wir_m"][0][2],"z":p["bounds_wir_m"][0][1]},
                        "max":{"x":p["bounds_wir_m"][1][0],"y":p["bounds_wir_m"][1][2],"z":p["bounds_wir_m"][1][1]}} for p in manifest["pieces"]]}
    write_json(destination/"unity_bounds.json",bounds)
    representatives={}
    for gid,semantic in sorted(geometry["buildings"].items()):representatives.setdefault(semantic["recipe_id"],gid)
    selected=set(representatives.values());paths=[]
    for r in geometry["walking"]["routes"]:
        if r["group"] not in selected:continue
        nearby={**geometry,"parts":[p for p in geometry["parts"] if p["group"]==r["group"]]}
        cells,critical=target_path(r,nearby)
        paths.append({"room":r["room"],"level":r["level"],"critical_indices":critical,
                      "points":[{"x":p[0],"y":p[2],"z":p[1]} for p in cells]})
    for r in geometry["network"]["routes"]:
        cells=r["cells"]
        if r["id"].startswith("cross_river"):
            base=accepted["plans"]["B"];rx=base["river_x"];rw=base["river_width"]
            cells=[p for p in cells if rx-rw/2-12<=p[0]<=rx+rw/2+12]
        paths.append({"room":r["id"],"level":0,"critical_indices":[len(cells)-1],
                      "points":[{"x":p[0],"y":p[2],"z":p[1]} for p in cells]})
    write_json(destination/"unity_paths.json",{"paths":paths,"representatives":representatives,
               "scope":"Every room of one representative per recipe plus keep; four bridge crossings, two complete avenues/gates and castle approach"})
    base=accepted["plans"]["B"];y=base["street_y"][0]+base["street_width"]/2
    write_json(destination/"city_view.json",{"street_y":y,"river_x":base["river_x"],"castle_x":geometry["castle_x"]+64})
    print("City",manifest["piece_count"],"source meshes;",len(paths),"physical test routes;",len(geometry["walking"]["routes"]),"source room routes")


if __name__=="__main__":main()
