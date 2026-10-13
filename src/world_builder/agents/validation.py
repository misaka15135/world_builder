"""Immutable acceptance rules for model plans, independent of model reviews.

Version 0.1 compiles integer cuboids in RH (east, north, up) metres. Routes
are a two-block-high, one-cell-wide discrete traversal with at most a one-block
jump. This is a source geometry check, not target-engine play testing.
"""
from __future__ import annotations

from collections import Counter
from itertools import combinations

from .contracts import AgentError, PAYLOADS, validate_schema


def require(condition, code, message):
    if not condition:
        raise AgentError(code, message)


def unique(items, label):
    ids = [item["id"] for item in items]
    require(len(ids) == len(set(ids)), "identity.duplicate", f"Duplicate {label} ID")
    return {item["id"]: item for item in items}


def inside(inner, outer):
    return all(outer["min"][i] <= inner["min"][i] < inner["max"][i] <= outer["max"][i]
               for i in range(3))


def overlaps(a, b):
    return all(min(a["max"][i], b["max"][i]) > max(a["min"][i], b["min"][i]) for i in range(3))


def cell_in(cell, box):
    return all(box["min"][i] <= cell[i] < box["max"][i] for i in range(3))


def bounds_valid(box):
    require(all(a < b for a, b in zip(box["min"], box["max"])), "geometry.bounds", "Degenerate bounds")


def tiles_under(box, terrain):
    step = terrain["cell_m"]
    for row in range(box["min"][1] // step, (box["max"][1] - 1) // step + 1):
        for col in range(box["min"][0] // step, (box["max"][0] - 1) // step + 1):
            yield col, row, terrain["heights"][row][col]


def connected(a, b):
    # One full metre of shared edge (or overlapping area), at equal walk level.
    if a["max"][2] != b["max"][2]:
        return False
    dx = min(a["max"][0], b["max"][0]) - max(a["min"][0], b["min"][0])
    dy = min(a["max"][1], b["max"][1]) - max(a["min"][1], b["min"][1])
    return (dx >= 1 and dy >= 0) or (dy >= 1 and dx >= 0)


def check_plan(stage, payload, plans, *, region_m, limits, scope_id="scene"):
    validate_schema(payload, PAYLOADS[stage])
    region = {"min": [0, 0, 0], "max": [region_m, region_m, 80]}
    if stage == "A":
        require(payload["region_m"] == region_m, "brief.region", "Region is fixed by the caller")
        unique(payload["requirements"], "requirement")
        for item in payload["requirements"]:
            require(item["min_count"] <= item["max_count"], "brief.count", "Reversed requirement count")
        require(sum(x["min_count"] for x in payload["requirements"]) <= limits["max_sites"],
                "brief.site_budget",
                "A requirements imply too many sites; keep roads, entrances and rooms as site/scene criteria")
    elif stage == "B":
        step, grid = payload["cell_m"], payload["heights"]
        require(region_m % step == 0 and len(grid) == region_m // step
                and all(len(row) == len(grid) for row in grid),
                "terrain.grid", "Cell grid must exactly tile the caller's region")
        unique(payload["water"], "water")
        for water in payload["water"]:
            require(inside(water["bounds"], region), "terrain.water", "Water outside region")
            require(all(water["bounds"]["min"][2] >= h for _, _, h in tiles_under(water["bounds"], payload)),
                    "terrain.water", "Water must be above authored terrain cells, not buried inside them")
        for a, b in combinations(payload["water"], 2):
            require(not overlaps(a["bounds"], b["bounds"]), "terrain.water", "Overlapping water volumes")
    elif stage == "C":
        unique(payload["types"], "type")
        requirements = {r["id"]: r for r in plans["A"]["requirements"]}
        counts = Counter()
        for item in payload["types"]:
            require(item["requirement_id"] in requirements, "catalogue.reference", "Unknown requirement")
            counts[item["requirement_id"]] += item["count"]
        for key, req in requirements.items():
            require(req["min_count"] <= counts[key] <= req["max_count"], "catalogue.coverage",
                    f"{key}: catalogue count {counts[key]} outside required range")
        require(sum(counts.values()) <= limits["max_sites"], "budget.sites", "Catalogue exceeds max_sites")
    elif stage == "D":
        districts = unique(payload["districts"], "district")
        unique(payload["sites"] + payload["roads"] + payload["districts"], "scene")
        types = {t["id"]: t for t in plans["C"]["types"]}
        rects = []
        for district in districts.values():
            x0, y0, x1, y1 = district["rect"]
            b = {"min": [x0, y0, 0], "max": [x1, y1, 80]}
            require(inside(b, region), "siting.district", "Invalid district rectangle")
            rects.append(b)
        require(not any(overlaps(a, b) for a, b in combinations(rects, 2)),
                "siting.district_overlap", "Districts overlap")
        counts = Counter()
        for site in payload["sites"]:
            b = site["bounds"]
            require(site["type_id"] in types and site["district_id"] in districts,
                    "siting.reference", "Unknown site type or district")
            counts[site["type_id"]] += 1
            t = types[site["type_id"]]
            rect = districts[site["district_id"]]["rect"]
            require(inside(b, {"min": [rect[0], rect[1], 0], "max": [rect[2], rect[3], 80]}),
                    "siting.containment", f"{site['id']} outside district")
            size = [b["max"][i] - b["min"][i] for i in range(3)]
            require(all(4 <= size[i] <= t["size_m"][i] for i in (0, 1))
                    and 3 <= size[2] <= t["max_height_m"], "siting.size", f"{site['id']} exceeds type envelope")
            ground = [h for _, _, h in tiles_under(b, plans["B"])]
            require(b["min"][2] >= max(ground), "siting.ground", f"{site['id']} buried in terrain")
            require(site["foundation"] or all(h == b["min"][2] for h in ground),
                    "siting.foundation", f"{site['id']} needs an explicit raised foundation")
            require(not any(overlaps({"min": [*b["min"][:2], 0], "max": b["max"]}, w["bounds"])
                            for w in plans["B"]["water"]), "siting.water", f"{site['id']} occupies water")
        require(counts == Counter({t["id"]: t["count"] for t in types.values()}),
                "siting.coverage", "Sites must fulfil every catalogue count exactly")
        for a, b in combinations(payload["sites"], 2):
            aa = {"min": [*a["bounds"]["min"][:2], 0], "max": a["bounds"]["max"]}
            bb = {"min": [*b["bounds"]["min"][:2], 0], "max": b["bounds"]["max"]}
            require(not overlaps(aa, bb), "siting.overlap", "Site footprints overlap")
        for road in payload["roads"]:
            b = road["bounds"]
            require(inside(b, region) and b["max"][2] - b["min"][2] == 1,
                    "siting.road", "Roads must be one-metre-thick boxes inside the region")
            require(min(b["max"][i] - b["min"][i] for i in (0, 1)) >= 2,
                    "siting.road", "Road is narrower than two metres")
            ground = [h for _, _, h in tiles_under(b, plans["B"])]
            require(all(h <= b["min"][2] for h in ground), "siting.road", "Road buried in terrain")
            if road["kind"] == "road":
                require(all(h == b["min"][2] for h in ground), "siting.road_support", "Road floats above terrain")
                require(not any(overlaps(b, w["bounds"]) for w in plans["B"]["water"]),
                        "siting.road_water", "Road intersects water; model must design a bridge")
            require(not any(overlaps(b, s["bounds"]) for s in payload["sites"]),
                    "siting.road_site", "Road crosses a site envelope")
        roads = payload["roads"]
        require(any(r["kind"] == "road" for r in roads), "siting.network_ground",
                "Network must include a terrain-supported road")
        for road in roads:
            require(not any(overlaps(road["bounds"], w["bounds"]) for w in plans["B"]["water"]),
                    "siting.bridge_water", "Road/bridge deck intersects water")
        reached = {0}
        while True:
            added = {i for i, r in enumerate(roads) if any(connected(r["bounds"], roads[j]["bounds"]) for j in reached)}
            if added <= reached:
                break
            reached |= added
        require(len(reached) == len(roads), "siting.network", "Road/bridge walk surfaces are disconnected")
        for site in payload["sites"]:
            ground_floor = {"min": site["bounds"]["min"],
                            "max": [*site["bounds"]["max"][:2], site["bounds"]["min"][2] + 1]}
            require(any(connected(ground_floor, r["bounds"]) for r in roads),
                    "siting.access", f"{site['id']} must touch a road at its ground-floor walk level")
    elif stage == "E":
        validate_design(payload, plans, scope_id)
    elif stage == "F":
        site_ids = {s["id"] for s in plans["D"]["sites"]}
        accepted = payload["accepted_sites"]
        require(len(accepted) == len(set(accepted)) and set(accepted) <= site_ids,
                "review.sites", "Review contains duplicate or unknown sites")
        reviews = payload["requirement_review"]
        reqs = {r["id"] for r in plans["A"]["requirements"]}
        require(len(reviews) == len(reqs) and {r["requirement_id"] for r in reviews} == reqs,
                "review.coverage", "Review must assess every requirement exactly once")
        if payload["verdict"] == "accept":
            require(not payload["fixes"] and set(accepted) == site_ids and all(r["satisfied"] for r in reviews),
                    "review.accept", "Accept requires all sites and requirements, with no pending fixes")
        else:
            require(bool(payload["fixes"]), "review.revise", "Revision needs an actionable scope")
        for fix in payload["fixes"]:
            require(fix["scope_id"] in site_ids if fix["stage"] == "E" else fix["scope_id"] == "scene",
                    "review.scope", "Fix must address a known site or the scene")


def validate_design(design, plans, scope_id):
    require(design["site_id"] == scope_id, "design.scope", "E cannot change another site")
    site = next(s for s in plans["D"]["sites"] if s["id"] == scope_id)
    origin = site["bounds"]["min"]
    size = [site["bounds"]["max"][i] - origin[i] for i in range(3)]
    envelope = {"min": [0, 0, 0], "max": size}
    parts = unique(design["parts"], "part")
    spaces = unique(design["spaces"], "space")
    require(not set(parts) & set(spaces), "identity.duplicate", "Part and space IDs collide")
    for p in parts.values():
        require(inside(p["bounds"], envelope), "design.envelope", f"{p['id']} outside local envelope")
    collisions = [(a["id"], b["id"]) for a, b in combinations(parts.values(), 2)
                  if overlaps(a["bounds"], b["bounds"])]
    require(not collisions, "design.overlap",
            "Overlapping solid parts (first 12): " + ", ".join(f"{a}/{b}" for a, b in collisions[:12]))
    for space in spaces.values():
        require(inside(space["bounds"], envelope), "design.space", "Space outside envelope")
        require(space["bounds"]["max"][2] - space["bounds"]["min"][2] >= 2,
                "design.headroom", "Space needs at least two metres of clear height")
        require(cell_in(space["access_cell"], space["bounds"]), "design.space_access", "Access cell outside space")
        require(space["access_cell"][2] + 2 <= space["bounds"]["max"][2],
                "design.space_access", "Access cell lacks headroom inside its declared space")
        occupied_by = [p["id"] for p in parts.values() if overlaps(space["bounds"], p["bounds"])]
        require(not occupied_by, "design.space_solid",
                f"Clear space {space['id']} intersects solid parts: {', '.join(occupied_by[:12])}")
    require(not any(overlaps(a["bounds"], b["bounds"]) for a, b in combinations(spaces.values(), 2)),
            "design.space_overlap", "Declared spaces overlap")
    t = next(t for t in plans["C"]["types"] if t["id"] == site["type_id"])
    req = next(r for r in plans["A"]["requirements"] if r["id"] == t["requirement_id"])
    if req["interior_required"]:
        require(bool(spaces) and {"floor", "wall", "roof"} <= {p["role"] for p in parts.values()},
                "design.interior", "Required interior needs usable spaces, floor, walls and roof")
    routes = design["routes"]
    require(len(routes) == len(spaces) and {r["space_id"] for r in routes} == set(spaces),
            "design.routes", "Exactly one route is required for each space")

    def solid(cell):
        if cell[2] == -1 and 0 <= cell[0] < size[0] and 0 <= cell[1] < size[1]:
            return True  # D has proved full ground/foundation support.
        return any(cell_in(cell, p["bounds"]) for p in parts.values())

    def walk_cell(cell):
        require(cell_in(cell, envelope) and cell[2] + 2 <= size[2], "design.path_bounds", "Route outside envelope")
        require(not solid(cell) and not solid([cell[0], cell[1], cell[2] + 1]),
                "design.path_blocked", f"Route has no two-block headroom at {cell}")
        require(solid([cell[0], cell[1], cell[2] - 1]), "design.path_support", f"Route floats at {cell}")

    entry = design["entry_cell"]
    walk_cell(entry)
    outside = []
    for axis in (0, 1):
        for edge, delta in ((0, -1), (size[axis] - 1, 1)):
            if entry[axis] == edge:
                p = [entry[i] + origin[i] for i in range(3)]
                p[axis] += delta
                outside.append(p)
    require(any(any(cell_in([p[0], p[1], p[2] - 1], road["bounds"])
                        and not cell_in(p, road["bounds"]) for road in plans["D"]["roads"]) for p in outside),
            "design.entry", "Entry must open directly onto D's adjacent road at the same level")
    for route in routes:
        cells = route["cells"]
        require(cells[0] == entry and cells[-1] == spaces[route["space_id"]]["access_cell"],
                "design.route_endpoints", "Route must start at entry and reach its space")
        for cell in cells:
            walk_cell(cell)
        for a, b in zip(cells, cells[1:]):
            require(abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1 and abs(a[2] - b[2]) <= 1,
                    "design.route_step", "Route must use adjacent cells with at most a one-block jump")
            # Clear upper sweep during a one-block ascent/descent.
            for point in (a, b):
                require(not solid([point[0], point[1], max(a[2], b[2]) + 1]),
                        "design.route_sweep", "Step/jump has a low ceiling")
    levels = {p["bounds"]["max"][2] for p in parts.values() if p["role"] == "floor"}
    if req["interior_required"]:
        require(levels <= {c[2] for r in routes for c in r["cells"]},
                "design.floor_access", "Every declared floor must be reached by a route")
