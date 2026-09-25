from __future__ import annotations

from itertools import combinations


def contains(outer: dict, inner: dict, tolerance: float = 1e-6) -> bool:
    return all(outer["min"][i] - tolerance <= inner["min"][i] <= inner["max"][i] <= outer["max"][i] + tolerance for i in range(3))


def overlaps(a: dict, b: dict, axes=(0, 1), tolerance=1e-6) -> bool:
    return all(min(a["max"][i], b["max"][i]) - max(a["min"][i], b["min"][i]) > tolerance for i in axes)


def touches(a: dict, b: dict) -> bool:
    return all(min(a["max"][i], b["max"][i]) >= max(a["min"][i], b["min"][i]) - 1e-6 for i in (0, 1))


def check_geometry(records: list[dict]) -> list[dict]:
    """Independent rules for the declared axis-aligned pilot template only.

    Does not certify arbitrary meshes, target navigation or real building codes.
    """
    entities = {r["id"]: r for r in records if r["record_type"] == "entity"}
    relations = [r for r in records if r["record_type"] == "relation"]
    results: list[dict] = []

    def check(rule: str, ids: list[str], passed: bool, message: str, severity="hard") -> None:
        results.append({"rule": rule, "scope_ids": ids, "state": "pass" if passed else "fail", "message": message, "severity": severity})

    def kind(name):
        return [e for e in entities.values() if e["kind"] == name]

    spec = next(r for r in records if r["record_type"] == "world_spec")
    settings = spec["extensions"].get("city_spec", spec["extensions"].get("pilot_spec"))
    stage = spec["extensions"]["stage"]
    if stage in {"buildings", "interiors"}:
        check("pilot.building_count", [next(e["id"] for e in entities.values() if e["kind"] == "world")], len(kind("building")) == settings["building_count"], "all requested buildings exist")
    if stage == "interiors":
        check("pilot.interior_count", [next(e["id"] for e in entities.values() if e["kind"] == "world")], len([b for b in kind("building") if b["attributes"].get("interior_state") == "generated"]) == settings["interior_count"], "all requested interiors exist")

    positions = {}

    def origin(e):
        if e["id"] not in positions:
            parent = origin(entities[e["parent_id"]]) if e["parent_id"] else [0, 0, 0]
            positions[e["id"]] = [parent[i] + e["transform"]["translation"][i] for i in range(3)]
        return positions[e["id"]]

    for e in entities.values():
        check("pilot.axis_aligned", [e["id"]], e["transform"]["rotation_xyzw"] == [0, 0, 0, 1] and e["transform"]["scale"] == [1, 1, 1], "pilot supports translation-only geometry")
        if e["kind"] != "world":
            check("pilot.world_bounds", [e["id"]], all(abs(origin(e)[i] - e["bounds"]["min"][i]) < 1e-6 for i in range(3)), "world AABB matches composed local translations")
            check("pilot.containment", [e["id"], e["parent_id"]], contains(entities[e["parent_id"]]["bounds"], e["bounds"]), "entity is inside its declared parent")
        size = (e.get("geometry") or {}).get("size_m")
        if size:
            check("pilot.size", [e["id"]], all(abs(e["bounds"]["max"][i] - e["bounds"]["min"][i] - size[i]) < 1e-6 and size[i] > 0 for i in range(3)), "geometry size matches bounds")
    buildings, rivers, bridges = kind("building"), kind("river"), kind("bridge")
    for building in buildings:
        for river in rivers:
            check("pilot.river_setback", [building["id"], river["id"]], not overlaps(building["bounds"], {"min": [river["bounds"]["min"][0]-2, river["bounds"]["min"][1], -4], "max": [river["bounds"]["max"][0]+2, river["bounds"]["max"][1], 32]}), "building clears channel plus 2 m setback")
        parcel = entities[building["parent_id"]]
        raw = parcel["attributes"]["raw_height_range_m"]
        platform = parcel["attributes"]["platform_z_m"]
        check("pilot.platform", [building["id"], parcel["id"]], max(raw) <= platform and abs(building["bounds"]["min"][2]-platform) < 1e-6, "supported level platform is above sampled ground")
        check("pilot.earthwork", [parcel["id"]], platform - min(raw) <= 2, "prefer platform fill depth <= 2 m", "soft")
    if settings.get("region_size_m") == 512:
        # A sweep preserves the all-buildings condition without materializing
        # thousands of passing pairwise constraints in the city snapshot.
        active = []
        collisions = []
        for building in sorted(buildings, key=lambda item: (item["bounds"]["min"][0], item["id"])):
            active = [item for item in active if item["bounds"]["max"][0] > building["bounds"]["min"][0] + 1e-6]
            collisions.extend((item, building) for item in active if overlaps(item["bounds"], building["bounds"]))
            active.append(building)
        if collisions:
            for a, b in collisions:
                check("pilot.building_overlap", [a["id"], b["id"]], False, "building footprints do not overlap")
        else:
            check("pilot.building_overlap", [next(e["id"] for e in entities.values() if e["kind"] == "world")], True,
                  "all building footprints do not overlap")
    else:
        for a, b in combinations(buildings, 2):
            check("pilot.building_overlap", [a["id"], b["id"]], not overlaps(a["bounds"], b["bounds"]), "building footprints do not overlap")
    roads = kind("road") + bridges
    graph = {r["id"]: set() for r in roads}
    for a, b in combinations(roads, 2):
        if touches(a["bounds"], b["bounds"]) and abs(a["attributes"]["surface_z_m"] - b["attributes"]["surface_z_m"]) < 1e-6:
            graph[a["id"]].add(b["id"])
            graph[b["id"]].add(a["id"])
    if graph:
        visited, pending = set(), [next(iter(graph))]
        while pending:
            node = pending.pop()
            if node not in visited:
                visited.add(node)
                pending.extend(graph[node] - visited)
        check("pilot.network_connected", sorted(graph), len(visited) == len(graph), "road surfaces form one geometrically connected network")
    for road in roads:
        check("pilot.road_width", [road["id"]], min(road["geometry"]["size_m"][:2]) >= 2, "road is at least 2 m wide")
        for river in rivers:
            if overlaps(road["bounds"], river["bounds"]):
                check("pilot.channel_crossing", [road["id"], river["id"]], road["kind"] == "bridge" and road["bounds"]["min"][2] >= river["bounds"]["max"][2]+1, "only an elevated bridge crosses the channel")
    for bridge in bridges:
        river = entities["river_main"]
        check("pilot.bridge_span", [bridge["id"], river["id"]], bridge["bounds"]["min"][0] <= river["bounds"]["min"][0] and bridge["bounds"]["max"][0] >= river["bounds"]["max"][0], "bridge spans the full channel width")
    for building in buildings:
        entrances = [r for r in relations if r["relation_type"] == "entrance" and r["source_id"] == building["id"]]
        entry = building["geometry"]["entry"]
        x = building["bounds"]["max"][0] if entry["side"] == "east" else building["bounds"]["min"][0]
        y = building["bounds"]["min"][1] + entry["offset_m"]
        access = [entities[t] for r in entrances for t in r["target_ids"] if t in graph]
        check("pilot.entrance_access", [building["id"]], any(a["bounds"]["min"][0] <= x <= a["bounds"]["max"][0] and a["bounds"]["min"][1] <= y <= a["bounds"]["max"][1] and abs(a["attributes"]["surface_z_m"]-building["bounds"]["min"][2]) < 1e-6 for a in access), "entry point joins a road at the same elevation")
        if building["attributes"]["interior_state"] == "generated":
            stairs = [s for s in kind("stair") if s["parent_id"] == building["id"]]
            needs_stair = building["attributes"]["storeys"] >= 2
            check("pilot.stair_required", [building["id"]], bool(stairs) == needs_stair,
                  "a building with more than one storey has a stair, a single-storey one does not")
    for stair in kind("stair"):
        g, building = stair["geometry"], entities[stair["parent_id"]]
        check("pilot.stair_dimensions", [stair["id"]], g["clear_width_m"] >= 1.2 and g["run_m"] > 0 and g["rise_m"] / g["run_m"] <= 0.5 and g["steps"] > 0 and g["rise_m"]/g["steps"] <= 0.2 and g["headroom_m"] >= 2 and g["landing_length_m"] >= 1.2, "template width, slope, riser, headroom and landing thresholds")
        check("pilot.stair_envelope", [stair["id"]], g["clear_width_m"] <= g["size_m"][0] and g["run_m"] + g["landing_length_m"] <= g["size_m"][1] and g["rise_m"] + g["headroom_m"] <= g["size_m"][2], "stair fits its envelope")
        void = building["geometry"]["stair_void_local_m"]
        local = stair["transform"]["translation"]
        check("pilot.stair_void", [stair["id"], building["id"]], all(void["min"][i] <= local[i] and void["max"][i] >= local[i] + g["size_m"][i] for i in (0, 1)), "upper floor opening covers the stair run and landing")
        links = [r for r in relations if r["relation_type"] == "connects" and r["source_id"] == stair["id"]]
        rooms = [entities[t] for r in links for t in r["target_ids"] if entities[t]["kind"] == "room"]
        check("pilot.stair_levels", [stair["id"]], len(rooms) == 2 and sorted(r["bounds"]["min"][2] for r in rooms) == g["floor_levels_m"] and abs(g["floor_levels_m"][1]-g["floor_levels_m"][0]-g["rise_m"]) < 1e-6, "stair connects the two room floor levels")
    for furniture in kind("furniture"):
        room = entities[furniture["parent_id"]]
        check("pilot.furniture_floor", [furniture["id"], room["id"]], abs(furniture["bounds"]["min"][2]-room["bounds"]["min"][2]) < 1e-6, "furniture rests on room floor")
        building_id = entities[room["parent_id"]]["parent_id"]
        for stair in kind("stair"):
            if stair["parent_id"] != building_id:
                continue
            check("pilot.furniture_stair", [furniture["id"], stair["id"]], not overlaps(furniture["bounds"], stair["bounds"], (0, 1, 2)), "furniture does not obstruct stair envelope")
    rooms = kind("room")
    for room in rooms:
        storey = entities[room["parent_id"]]
        building = entities[storey["parent_id"]]
        check("city.room_storey_bounds", [room["id"], storey["id"]],
              contains(storey["bounds"], room["bounds"]), "room stays inside its storey")
        void = building["geometry"]["stair_void_local_m"]
        base = building["bounds"]["min"]
        void_box = {"min": [base[0] + void["min"][0], base[1] + void["min"][1], base[2] + 3],
                    "max": [base[0] + void["max"][0], base[1] + void["max"][1], base[2] + 3.2]}
        check("city.room_stair_void", [room["id"], building["id"]],
              not overlaps(room["bounds"], void_box, (0, 1)), "room clears the stair reservation")
    for storey in kind("storey"):
        siblings = sorted((r for r in rooms if r["parent_id"] == storey["id"]), key=lambda r: r["id"])
        for a, b in combinations(siblings, 2):
            check("city.room_overlap", [a["id"], b["id"]],
                  not overlaps(a["bounds"], b["bounds"], (0, 1)), "rooms on one storey do not overlap")
    for wall in kind("partition"):
        storey = entities[wall["parent_id"]]
        siblings = sorted((r for r in rooms if r["parent_id"] == storey["id"]), key=lambda r: r["id"])
        check("city.partition_pair", [wall["id"], storey["id"]], len(siblings) == 2,
              "a partition divides exactly two rooms")
        if len(siblings) == 2:
            check("city.partition_room_bounds", [wall["id"]] + [r["id"] for r in siblings],
                  all(touches(wall["bounds"], r["bounds"]) for r in siblings)
                  and not any(overlaps(wall["bounds"], r["bounds"], (0, 1)) for r in siblings),
                  "the partition touches both rooms without occupying either")
        opening = (wall.get("attributes") or {}).get("opening")
        span_x = wall["bounds"]["max"][0] - wall["bounds"]["min"][0]
        span_z = wall["bounds"]["max"][2] - wall["bounds"]["min"][2]
        check("city.partition_opening", [wall["id"]],
              isinstance(opening, dict) and 0 < opening.get("width_m", 0) < span_x
              and 0 < opening.get("height_m", 0) < span_z,
              "the declared opening fits inside its partition")
    if settings.get("region_size_m") == 512:
        # The 128 m pilot predates declared partitions and keeps its own plan,
        # so this circulation rule is scoped to the city contract.
        for room in rooms:
            storey = entities[room["parent_id"]]
            building = entities[storey["parent_id"]]
            walls = [w for w in kind("partition") if w["parent_id"] == storey["id"]]
            void = building["geometry"]["stair_void_local_m"]
            base = building["bounds"]["min"]
            void_box = {"min": [base[0] + void["min"][0], base[1] + void["min"][1], base[2] + 3],
                        "max": [base[0] + void["max"][0], base[1] + void["max"][1], base[2] + 3.2]}
            # Adjacency, not a path solve: the room must touch a declared
            # partition or the stair void, which keeps the storey's
            # circulation open.
            check("city.room_circulation", [room["id"], building["id"]],
                  any(touches(room["bounds"], w["bounds"]) for w in walls) or touches(room["bounds"], void_box),
                  "room touches a declared partition or the stair void")
    return results
