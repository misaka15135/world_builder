from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from . import CITY_GENERATOR_VERSION, GENERATOR_VERSION


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


@dataclass(frozen=True)
class PilotSpec:
    """Historical fixed 128 m pilot; its serialized fields and identity stay stable."""

    seed: int = 1
    scenario: str = "riverside"
    building_count: int = 6
    interior_count: int = 2
    source_prompt: str = "A small editable arcane settlement beside a river."
    layout_profile: str = "standard"
    lock_stair_void: bool = False
    accepted_response_hash: str | None = None
    model_provenance: dict | None = None

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
        if (self.accepted_response_hash is None) != (self.model_provenance is None):
            raise ValueError("accepted response hash and model provenance must appear together")
        if self.accepted_response_hash is not None:
            if not isinstance(self.accepted_response_hash, str) or len(self.accepted_response_hash) != 71 or not self.accepted_response_hash.startswith("sha256:"):
                raise ValueError("accepted_response_hash must be a SHA-256 digest")
            if not isinstance(self.model_provenance, dict):
                raise ValueError("model_provenance must be an object")

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def region_size_m(self) -> int:
        return 128

    @property
    def generator_version(self) -> str:
        return GENERATOR_VERSION

    @property
    def contract_key(self) -> str:
        return "pilot_spec"

    @property
    def world_id(self) -> str:
        return "world_" + digest(self.to_dict())[7:23]


@dataclass(frozen=True)
class CitySpec(PilotSpec):
    """Fixed 512 m source-data city; target-adapter validation is separate."""

    building_count: int = 80
    interior_count: int = 80
    source_prompt: str = "An editable arcane city across a river."
    region_size_m: int = 512
    plan_profile: str = "district_v2"
    style_profile: str = "arcane_medieval"

    def __post_init__(self) -> None:
        if type(self.region_size_m) is not int or self.region_size_m != 512:
            raise ValueError("city region_size_m must be 512")
        if type(self.building_count) is not int or self.building_count != 80:
            raise ValueError("city building_count must be 80")
        if type(self.interior_count) is not int or not 1 <= self.interior_count <= self.building_count:
            raise ValueError("city interior_count must be between 1 and building_count")
        if self.plan_profile not in {"district_v1", "district_v2"}:
            raise ValueError("city plan_profile must be district_v1 or district_v2")
        if self.style_profile not in {"arcane_medieval", "modern_grid"}:
            raise ValueError("city style_profile must be arcane_medieval or modern_grid")
        if self.accepted_response_hash is not None or self.model_provenance is not None:
            raise ValueError("city specification currently supports offline fixed inputs only")
        # Reuse common field validation without accepting the pilot count limits.
        if type(self.seed) is not int or not 0 <= self.seed < 2**64:
            raise ValueError("seed must be an unsigned 64-bit integer")
        if self.scenario not in {"riverside", "hillside", "dense"}:
            raise ValueError("scenario must be riverside, hillside or dense")
        if not isinstance(self.source_prompt, str) or not self.source_prompt.strip():
            raise ValueError("source_prompt must be nonempty")
        if self.layout_profile not in {"standard", "compact"}:
            raise ValueError("layout_profile must be standard or compact")
        if type(self.lock_stair_void) is not bool:
            raise ValueError("lock_stair_void must be a boolean")

    @property
    def generator_version(self) -> str:
        return CITY_GENERATOR_VERSION

    @property
    def contract_key(self) -> str:
        return "city_spec"


@dataclass(frozen=True)
class Budget:
    wall_time_ms: int = 30000
    max_candidates: int = 3

    def __post_init__(self) -> None:
        if type(self.wall_time_ms) is not int or self.wall_time_ms < 1:
            raise ValueError("wall_time_ms must be positive")
        if type(self.max_candidates) is not int or not 1 <= self.max_candidates <= 3:
            raise ValueError("max_candidates must be 1..3")
