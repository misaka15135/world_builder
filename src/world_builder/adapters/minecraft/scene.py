"""Project a scene-pipeline package into the Minecraft adapter's vocabulary.

The scene pipeline keeps its source data honest: a road is a polyline with a
width, a wall is a corridor, water is a channel or a coastline. The Minecraft
adapter predates that and reads boxes with a `city_spec` style. This module is
the translation layer between the two, so neither side has to lie:

* every polyline entity becomes a chain of segment boxes, which is also what
  lets a non-orthogonal arterial reach the game;
* the world spec gains a `city_spec` block carrying the style, so the existing
  material lookup works unchanged.

Still missing before an export can run (work order 018): a water policy for the
channel network, and an entrance on any side rather than east only.
"""
from __future__ import annotations

import copy

BOX_KINDS = {"road", "rail", "wall", "pier", "quay", "work"}
SETTING_STYLES = {"arcane_medieval": "arcane_medieval", "modern_metropolis": "modern_grid",
                  "industrial_park": "modern_grid", "harbour": "modern_grid"}


def project_for_minecraft(package: dict) -> dict:
    """Return a copy of the package with polylines flattened into boxes."""
    projected = copy.deepcopy(package)
    spec = next(record for record in projected["records"] if record["record_type"] == "world_spec")
    scene = spec["extensions"].get("scene_spec")
    if scene is None:
        raise ValueError("scene.project_scope: package has no scene_spec")
    # The adapter looks the material style up in `city_spec`; the projection
    # supplies it rather than teaching the source to carry a legacy field.
    style = SETTING_STYLES.get(scene["setting"])
    if style is None:
        raise ValueError(f"scene.project_style: {scene['setting']!r} has no target style")
    spec["extensions"]["city_spec"] = {
        "region_size_m": scene["brief"]["scale"]["region_m"],
        "style_profile": style,
        "building_count": len([r for r in projected["records"]
                               if r["record_type"] == "entity" and r["kind"] == "building"]),
        "interior_count": 0,
        "plan_profile": "district_v4",
    }
    flattened = []
    for record in projected["records"]:
        geometry = record.get("geometry") or {}
        if (record["record_type"] == "entity" and record["kind"] in BOX_KINDS
                and geometry.get("representation") == "polyline"):
            points = geometry.get("points_m") or []
            if len(points) < 2:
                raise ValueError(f"scene.project_polyline: {record['id']} has fewer than two points")
            width = float(geometry.get("width_m", 4.0))
            for index in range(len(points) - 1):
                x0, y0 = points[index]
                x1, y1 = points[index + 1]
                segment = copy.deepcopy(record)
                segment["id"] = f"{record['id']}_seg{index:03d}"
                segment["bounds"] = {
                    "min": [min(x0, x1) - width / 2, min(y0, y1) - width / 2, record["bounds"]["min"][2]],
                    "max": [max(x0, x1) + width / 2, max(y0, y1) + width / 2, record["bounds"]["max"][2]],
                }
                segment["geometry"] = {"representation": "box",
                                       "size_m": [segment["bounds"]["max"][0] - segment["bounds"]["min"][0],
                                                  segment["bounds"]["max"][1] - segment["bounds"]["min"][1],
                                                  max(segment["bounds"]["max"][2] - segment["bounds"]["min"][2], 0.4)]}
                segment["extensions"] = {**record.get("extensions", {}),
                                         "projected_from": record["id"], "segment": index}
                flattened.append(segment)
            continue
        flattened.append(record)
    projected["records"] = flattened
    projected["manifest"]["extensions"] = {**projected["manifest"].get("optional_extensions", {}),
                                           "projection": "minecraft-city-0.1"}
    return projected
