from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


@dataclass(frozen=True)
class PilotSpec:
    """Fixed 128 m pilot, bounded until target sample conversions are verified."""

    seed: int = 1
    scenario: str = "riverside"
    building_count: int = 6
    interior_count: int = 2
    source_prompt: str = "A small editable arcane settlement beside a river."
    layout_profile: str = "standard"
    lock_stair_void: bool = False

    def __post_init__(self) -> None:
        if type(self.seed) is not int or not 0 <= self.seed < 2**64:
            raise ValueError("seed must be an unsigned 64-bit integer")
        if self.scenario not in {"riverside", "hillside", "dense"}:
            raise ValueError("scenario must be riverside, hillside or dense")
        if type(self.building_count) is not int or not 1 <= self.building_count <= 6:
            raise ValueError("pilot supports 1..6 buildings; city expansion requires 008/009 sample validation")
        if type(self.interior_count) is not int or not 0 <= self.interior_count <= self.building_count:
            raise ValueError("interior_count must be between zero and building_count")
        if not isinstance(self.source_prompt, str) or not self.source_prompt.strip():
            raise ValueError("source_prompt must be nonempty")
        if self.layout_profile not in {"standard", "compact"}:
            raise ValueError("layout_profile must be standard or compact (a preference, not an exact size constraint)")
        if type(self.lock_stair_void) is not bool:
            raise ValueError("lock_stair_void must be a boolean")

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def world_id(self) -> str:
        return "world_" + digest(self.to_dict())[7:23]


@dataclass(frozen=True)
class Budget:
    wall_time_ms: int = 30000
    max_candidates: int = 3

    def __post_init__(self) -> None:
        if type(self.wall_time_ms) is not int or self.wall_time_ms < 1:
            raise ValueError("wall_time_ms must be positive")
        if type(self.max_candidates) is not int or not 1 <= self.max_candidates <= 3:
            raise ValueError("max_candidates must be 1..3")
