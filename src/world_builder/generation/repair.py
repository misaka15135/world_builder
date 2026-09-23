from __future__ import annotations

import copy
import math
from dataclasses import dataclass

from world_builder.storage.repository import Repository, StoreError


@dataclass
class RepairProposal:
    records: list[dict] | None
    actions: list[dict]
    code: str
    message: str


def propose_repair(records: list[dict], failures: list[dict], base_records: list[dict]) -> RepairProposal:
    """Bounded template repairs; proposals are revalidated in the next attempt.

    Rule thresholds are owned by validation.py. This policy chooses candidates;
    it cannot declare success, relax hard constraints or remove a field lock.
    """
    candidate = copy.deepcopy(records)
    by_id = {r["id"]: r for r in candidate}
    actions: list[dict] = []

    def assign(record: dict, path: list, value, rule: str, scope: str, source_id: str):
        target = record
        for part in path[:-1]:
            target = target[part]
        old = copy.deepcopy(target[path[-1]])
        if old == value:
            return
        target[path[-1]] = copy.deepcopy(value)
        actions.append({"entity_id": record["id"], "path": "/" + "/".join(map(str, path)),
                        "before": old, "after": copy.deepcopy(value), "rule": rule,
                        "scope": scope, "source_id": source_id})

    supported = {"pilot.stair_dimensions", "pilot.stair_envelope", "pilot.stair_void"}
    if any(f["rule"] not in supported for f in failures):
        return RepairProposal(None, [], "constraint.repair_unsupported", "no registered repair policy for one or more failed rules")
    for failure in failures:
        stair = by_id[failure["scope_ids"][0]]
        if stair.get("kind") != "stair":
            return RepairProposal(None, [], "constraint.repair_unsupported", "repair requires a stair entity")
        g, rule = stair["geometry"], failure["rule"]
        if rule == "pilot.stair_dimensions":
            # Only repair an overly steep run; do not change requested widths,
            # clearances or storey heights to disguise an unrelated violation.
            if g["run_m"] < g["rise_m"] * 2:
                assign(stair, ["geometry", "run_m"], g["rise_m"] * 2, rule, "local", stair["id"])
        else:
            building = by_id[stair["parent_id"]]
            required = g["run_m"] + g["landing_length_m"]
            local_y = stair["transform"]["translation"][1]
            # A finite policy limit, not a proof that all other layouts are impossible.
            if local_y + required > building["geometry"]["size_m"][1] - 0.2:
                return RepairProposal(None, actions, "constraint.parent_capacity", "required stair reservation exceeds the current building; broader replanning is needed")
            if rule == "pilot.stair_envelope":
                assign(stair, ["geometry", "size_m", 1], required, rule, "local", stair["id"])
                assign(stair, ["bounds", "max", 1], stair["bounds"]["min"][1] + required, rule, "local", stair["id"])
                bounds = stair["bounds"]
                chunks = [f"chunk_{x}_{y}" for x in range(max(0, int(bounds["min"][0] // 64)), max(0, math.ceil(bounds["max"][0] / 64)-1)+1)
                          for y in range(max(0, int(bounds["min"][1] // 64)), max(0, math.ceil(bounds["max"][1] / 64)-1)+1)]
                assign(stair, ["chunk_ids"], chunks, rule, "local", stair["id"])
            assign(building, ["geometry", "stair_void_local_m", "max", 1],
                   max(building["geometry"]["stair_void_local_m"]["max"][1], local_y + required),
                   rule, "parent", stair["id"])
    if not actions:
        return RepairProposal(None, [], "constraint.repair_no_progress", "registered policy cannot improve this candidate")
    try:
        # Check both committed locks and new locks introduced in the candidate.
        Repository._check_locks({"records": base_records}, {"records": candidate})
        Repository._check_locks({"records": records}, {"records": candidate})
    except StoreError as exc:
        return RepairProposal(None, actions, exc.code, str(exc))
    return RepairProposal(candidate, actions, "repair.proposed", "candidate changes require complete revalidation")
