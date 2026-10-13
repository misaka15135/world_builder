"""Opt-in bounded road-width projection, gated by full D validation."""
from __future__ import annotations

from copy import deepcopy
from itertools import product

from .contracts import AgentError, PAYLOADS, validate_schema
from .validation import check_plan


def _road_candidates(road: dict, region_m: int) -> list[dict]:
    bounds = road["bounds"]
    if bounds["max"][2] - bounds["min"][2] not in (0, 1):
        return []
    base = deepcopy(road)
    if bounds["max"][2] == bounds["min"][2]:
        base["bounds"]["max"][2] += 1
    candidates = [base]
    for axis in (0, 1):
        if bounds["max"][axis] - bounds["min"][axis] >= 2:
            continue
        next_candidates = []
        for candidate in candidates:
            for edge in ("min", "max"):
                changed = deepcopy(candidate)
                changed["bounds"][edge][axis] = (bounds["max"][axis] - 2 if edge == "min"
                                                   else bounds["min"][axis] + 2)
                if 0 <= changed["bounds"]["min"][axis] < changed["bounds"]["max"][axis] <= region_m:
                    next_candidates.append(changed)
        candidates = next_candidates
    return candidates


def widen_short_roads(payload: dict, plans: dict, *, region_m: int, limits: dict) -> tuple[dict, dict | None]:
    """Try at most 64 minimal candidates; accept only a fully valid D plan."""
    validate_schema(payload, PAYLOADS["D"])
    deficient = [index for index, road in enumerate(payload["roads"])
                 if any(road["bounds"]["max"][axis] - road["bounds"]["min"][axis] < (1 if axis == 2 else 2)
                        for axis in range(3))]
    if not deficient or len(deficient) > 3:
        return payload, None
    options = [_road_candidates(payload["roads"][index], region_m) for index in deficient]
    total = 1
    for group in options:
        total *= len(group)
    if total == 0 or total > 64:
        return payload, None
    for selection in product(*options):
        candidate = deepcopy(payload)
        for index, road in zip(deficient, selection):
            candidate["roads"][index] = road
        try:
            check_plan("D", candidate, plans, region_m=region_m, limits=limits)
        except AgentError:
            continue
        return candidate, {"mode": "road_min_width_v1", "changed_road_ids":
                           [payload["roads"][index]["id"] for index in deficient],
                           "candidates_considered_at_most": total}
    return payload, None
