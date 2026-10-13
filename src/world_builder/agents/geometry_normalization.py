"""Opt-in lossless same-material cuboid de-duplication for E proposals.

Only identical-material occupied volume is removed from earlier parts. No
different-material collision, route, support or clear-space error is repaired.
The complete normalized proposal must still pass the ordinary validator.
"""
from __future__ import annotations

from copy import deepcopy

from .contracts import AgentError, PAYLOADS, validate_schema
from .validation import overlaps


def _box(lo, hi):
    return {"min": lo, "max": hi}


def _subtract(a, b):
    if not overlaps(a, b):
        return [a]
    ax, ay, az = a["min"]
    bx, by, bz = a["max"]
    ix, iy, iz = [max(a["min"][i], b["min"][i]) for i in range(3)]
    jx, jy, jz = [min(a["max"][i], b["max"][i]) for i in range(3)]
    pieces = [
        _box([ax, ay, az], [ix, by, bz]),
        _box([jx, ay, az], [bx, by, bz]),
        _box([ix, ay, az], [jx, iy, bz]),
        _box([ix, jy, az], [jx, by, bz]),
        _box([ix, iy, az], [jx, jy, iz]),
        _box([ix, iy, jz], [jx, jy, bz]),
    ]
    return [piece for piece in pieces if all(piece["min"][i] < piece["max"][i] for i in range(3))]


def deduplicate_same_material(design: dict) -> tuple[dict, dict | None]:
    """Later equal-material parts take precedence in overlap cells."""
    validate_schema(design, PAYLOADS["E"])
    original = design["parts"]
    if len({part["id"] for part in original}) != len(original):
        return design, None  # the existing identity validator must reject it
    later = []
    changed_ids, removed_ids = [], []
    reserved = {part["id"] for part in original}
    for part in reversed(original):
        fragments = [part["bounds"]]
        for other in later:
            if other["material"] != part["material"]:
                continue
            fragments = [piece for fragment in fragments
                         for piece in _subtract(fragment, other["bounds"])]
            if len(fragments) + len(later) > 512:
                raise AgentError("design.normalization_budget", "Same-material split exceeds E part limit")
        if fragments == [part["bounds"]]:
            later.append(deepcopy(part))
            continue
        changed_ids.append(part["id"])
        if not fragments:
            removed_ids.append(part["id"])
        for number, fragment in enumerate(fragments, 1):
            fresh = deepcopy(part)
            fresh["bounds"] = fragment
            if len(fragments) > 1:
                stem = part["id"][:34]
                suffix = number
                name = f"{stem}_cut_{suffix}"
                while name in reserved:
                    suffix += 1
                    name = f"{stem}_cut_{suffix}"
                reserved.add(name)
                fresh["id"] = name
            later.append(fresh)
    if not changed_ids:
        return design, None
    result = deepcopy(design)
    result["parts"] = list(reversed(later))
    validate_schema(result, PAYLOADS["E"])
    return result, {"mode": "same_material_overlap_v1", "trimmed_ids": sorted(changed_ids),
                    "fully_covered_ids": sorted(removed_ids),
                    "part_count_before": len(original), "part_count_after": len(result["parts"])}
