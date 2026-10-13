"""Opt-in, fail-closed projection of an obvious road feature in legacy A plans.

The v0.1 A wire schema has only buildable-site requirements. This adapter does
not invent geometry: it retains the road's full text as a site constraint and
acceptance criterion, while keeping the raw response and a transformation log.
Ambiguous classifications are left for the ordinary validator to reject.
"""
from __future__ import annotations

from copy import deepcopy
import re

from .contracts import PAYLOADS, validate_schema


_ROAD_WORDS = re.compile(r"(?:^|[_\s])(?:road|street)(?:[_\s]|$)|道路|街道", re.IGNORECASE)
_BUILDING_WORDS = re.compile(r"house|building|shop|home|cabin|屋|房|楼|建筑|商铺|住宅", re.IGNORECASE)


def normalize_single_site_road(payload: dict) -> tuple[dict, list[str]]:
    """Move one unambiguous road requirement to site/scene criteria, or leave unchanged."""
    validate_schema(payload, PAYLOADS["A"])
    items = payload["requirements"]
    roads = [item for item in items if _ROAD_WORDS.search(item["id"])
             and _ROAD_WORDS.search(item["programme"])
             and not _BUILDING_WORDS.search(re.split(r"[(（]", item["programme"], maxsplit=1)[0])
             and not item["interior_required"]]
    sites = [item for item in items if item not in roads]
    if len(roads) != 1 or len(sites) != 1 or len(items) != 2:
        return payload, []
    road, site = roads[0], sites[0]
    if site["min_count"] != 1 or site["max_count"] != 1:
        return payload, []
    # No prose is discarded. The two destination fields have contract limits;
    # refuse instead of truncating a request that cannot fit.
    description = site["description"] + "\n道路约束（" + road["id"] + "）：" + road["description"]
    criterion = "道路约束（" + road["id"] + "）：" + road["description"]
    if len(description) > 1000 or len(criterion) > 1000 or len(payload["acceptance_criteria"]) >= 24:
        return payload, []
    result = deepcopy(payload)
    result["requirements"] = [item for item in result["requirements"] if item["id"] != road["id"]]
    result["requirements"][0]["description"] = description
    result["acceptance_criteria"].append(criterion)
    validate_schema(result, PAYLOADS["A"])
    return result, [road["id"]]
