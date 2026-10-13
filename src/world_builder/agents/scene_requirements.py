"""Draft v0.2 typed scene requirements, isolated from the v0.1 runtime.

This module validates proposals and cross-stage reference projections. It does
not schedule tasks, create geometry, or claim that a model understood the prompt.
"""
from __future__ import annotations

from collections import Counter

from .contracts import AgentError, ID, arr, enum, integer, obj, string, validate_schema


VERSION = "0.2.0-draft.1"
AXES = "RH_X_east_Y_north_Z_up"

_COMMON = {"id": ID, "description": string(2000),
           "necessity": enum("required", "optional")}
_COUNT = {"min_count": integer(0, 1024), "max_count": integer(0, 1024)}
_REQUIREMENT = {"oneOf": [
    obj(**_COMMON, kind={"const": "site"}, programme=string(100),
        interior_required={"type": "boolean"}, **_COUNT),
    obj(**_COMMON, kind={"const": "road_network"}, connects=arr(ID, 0, 32)),
    obj(**_COMMON, kind={"const": "terrain_condition"}),
    obj(**_COMMON, kind={"const": "interior_space"}, parent_site_id=ID, **_COUNT),
    obj(**_COMMON, kind={"const": "natural_object"}, **_COUNT),
]}

SCENE_BRIEF_SCHEMA = {"$schema": "https://json-schema.org/draft/2020-12/schema",
                      **obj(contract_version={"const": VERSION}, title=string(120),
                            region_m=integer(32, 512), units={"const": "m"},
                            axes={"const": AXES}, style=string(2000),
                            requirements=arr(_REQUIREMENT, 1, 128),
                            relations=arr(obj(subject_id=ID,
                                              predicate=enum("near", "inside", "connected_to",
                                                             "away_from", "alongside"),
                                              object_id=ID), 0, 128),
                            acceptance_criteria=arr(obj(id=ID, requirement_ids=arr(ID, 1, 128),
                                                        description=string(2000)), 1, 128))}

# A minimal typed projection of later C/D/E output. This is not a new runtime
# response envelope: the dynamic task graph and stage payloads belong to 030.
SCENE_LINKS_SCHEMA = {"$schema": "https://json-schema.org/draft/2020-12/schema",
                      **obj(contract_version={"const": VERSION},
                            catalogue=arr(obj(id=ID, requirement_id=ID,
                                              kind=enum("site", "natural_object")), 0, 128),
                            sites=arr(obj(id=ID, catalogue_id=ID), 0, 128),
                            roads=arr(obj(id=ID, requirement_id=ID), 0, 256),
                            interior_spaces=arr(obj(id=ID, requirement_id=ID, site_id=ID), 0, 256),
                            natural_objects=arr(obj(id=ID, catalogue_id=ID), 0, 1024))}


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise AgentError(code, message)


def _by_id(items: list[dict], label: str) -> dict[str, dict]:
    result = {item["id"]: item for item in items}
    _require(len(result) == len(items), "scene.identity", f"Duplicate {label} ID")
    return result


def validate_scene_brief(brief: dict, *, region_m: int, max_sites: int) -> None:
    """Validate the typed A proposal without coercing or discarding intent."""
    validate_schema(brief, SCENE_BRIEF_SCHEMA, "scene.brief_schema")
    _require(brief["region_m"] == region_m and 32 <= region_m <= 512 and region_m % 16 == 0,
             "scene.region", "Region must equal the caller's 16 m-aligned region")
    _require(type(max_sites) is int and max_sites >= 0, "scene.budget", "Invalid site budget")
    requirements = _by_id(brief["requirements"], "requirement")
    for req in requirements.values():
        if "min_count" in req:
            _require(req["min_count"] <= req["max_count"], "scene.count",
                     f"{req['id']}: reversed count range")
            if req["necessity"] == "required":
                _require(req["min_count"] > 0, "scene.required_count",
                         f"{req['id']}: required object needs a positive minimum")
        if req["kind"] == "interior_space":
            parent = requirements.get(req["parent_site_id"])
            _require(parent is not None and parent["kind"] == "site", "scene.interior_parent",
                     f"{req['id']}: interior must name a site requirement")
            _require(parent["interior_required"], "scene.interior_parent",
                     f"{req['id']}: parent site must permit an interior")
        elif req["kind"] == "road_network":
            _require(len(req["connects"]) == len(set(req["connects"])), "scene.road_reference",
                     f"{req['id']}: duplicate connection")
            _require(all(target in requirements and requirements[target]["kind"] == "site"
                         for target in req["connects"]), "scene.road_reference",
                     f"{req['id']}: roads may connect only site requirements")
    _require(sum(req["min_count"] for req in requirements.values() if req["kind"] == "site") <= max_sites,
             "scene.site_budget", "Only site requirements count toward max_sites")
    for relation in brief["relations"]:
        _require(relation["subject_id"] in requirements and relation["object_id"] in requirements,
                 "scene.relation_reference", "Relation refers to an unknown requirement")
    criteria = _by_id(brief["acceptance_criteria"], "criterion")
    covered = set()
    for criterion in criteria.values():
        refs = criterion["requirement_ids"]
        _require(len(refs) == len(set(refs)) and set(refs) <= requirements.keys(),
                 "scene.criterion_reference", f"{criterion['id']}: invalid requirement reference")
        covered.update(refs)
    _require({r["id"] for r in requirements.values() if r["necessity"] == "required"} <= covered,
             "scene.criterion_coverage", "Every required requirement needs an acceptance criterion")


def validate_scene_links(brief: dict, links: dict, *, region_m: int, max_sites: int) -> None:
    """Check category/ID coverage across proposed catalogue, placement and interiors.

    Geometric feasibility and correspondence to the original prose are separate
    checks; passing this projection must never publish a WIR by itself.
    """
    validate_scene_brief(brief, region_m=region_m, max_sites=max_sites)
    validate_schema(links, SCENE_LINKS_SCHEMA, "scene.links_schema")
    requirements = _by_id(brief["requirements"], "requirement")
    catalogue = _by_id(links["catalogue"], "catalogue")
    sites = _by_id(links["sites"], "site")
    _by_id(links["roads"] + links["interior_spaces"] + links["natural_objects"], "placed object")
    all_ids = [item["id"] for field in ("catalogue", "sites", "roads", "interior_spaces", "natural_objects")
               for item in links[field]]
    _require(len(all_ids) == len(set(all_ids)), "scene.identity", "Cross-stage object ID collision")
    for item in catalogue.values():
        req = requirements.get(item["requirement_id"])
        _require(req is not None and req["kind"] == item["kind"], "scene.catalogue_kind",
                 f"{item['id']}: catalogue kind must match its site or natural-object requirement")

    counts = Counter()
    for site in sites.values():
        entry = catalogue.get(site["catalogue_id"])
        _require(entry is not None and entry["kind"] == "site", "scene.site_kind",
                 f"{site['id']}: site must reference a site catalogue entry")
        counts[entry["requirement_id"]] += 1
    _require(len(sites) <= max_sites, "scene.site_budget", "Placed sites exceed max_sites")
    for road in links["roads"]:
        req = requirements.get(road["requirement_id"])
        _require(req is not None and req["kind"] == "road_network", "scene.road_kind",
                 f"{road['id']}: road must reference a road-network requirement")
        counts[req["id"]] += 1
    for space in links["interior_spaces"]:
        req = requirements.get(space["requirement_id"])
        site = sites.get(space["site_id"])
        _require(req is not None and req["kind"] == "interior_space" and site is not None,
                 "scene.interior_kind", f"{space['id']}: invalid interior or site reference")
        parent_requirement_id = catalogue[site["catalogue_id"]]["requirement_id"]
        _require(req["parent_site_id"] == parent_requirement_id, "scene.interior_parent",
                 f"{space['id']}: interior belongs to a different site requirement")
        counts[req["id"]] += 1
    for placed in links["natural_objects"]:
        entry = catalogue.get(placed["catalogue_id"])
        _require(entry is not None and entry["kind"] == "natural_object", "scene.natural_kind",
                 f"{placed['id']}: natural object must reference a natural catalogue entry")
        counts[entry["requirement_id"]] += 1
    for req in requirements.values():
        if "min_count" in req:
            _require(req["min_count"] <= counts[req["id"]] <= req["max_count"],
                     "scene.coverage", f"{req['id']}: placed count outside declared range")
        elif req["kind"] == "road_network" and req["necessity"] == "required":
            _require(counts[req["id"]] > 0, "scene.coverage", f"{req['id']}: required road network absent")
