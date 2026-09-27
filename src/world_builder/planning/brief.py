"""Structured scene brief: the pipeline's single entry point (work order 013).

The brief is what the rest of the pipeline reads instead of a free-form
prompt: a background, an era, a scale, the landmarks the scene must contain,
the targets it will be exported to and the run budget. It is validated against
the setting pack it names, so a brief can never ask for a building that its
background has no catalogue entry for.

Two implementations share this contract, as the redesign requires: the offline
rule compiler below (default, zero model calls, deterministic) and a model
implementation that fills the same JSON object.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Protocol

from .catalogue import (DEFAULT_SETTINGS_ROOT, PRIORITIES, SceneError, TARGETS, SettingPack,
                        load_setting_pack)

BRIEF_VERSION = "0.1.0"
MODEL_CONTRACT_VERSION = "0.1.0"
MAX_RESPONSE_BYTES = 65_536
MIN_REGION_M, MAX_REGION_M, REGION_STEP_M = 128, 4096, 128
DEFAULT_WALL_TIME_MS = 120_000


@dataclass(frozen=True)
class Landmark:
    """A building or work the scene must, should or may contain."""

    type: str
    count: int = 1
    priority: str = "must"

    def to_dict(self) -> dict:
        return {"type": self.type, "count": self.count, "priority": self.priority}


@dataclass(frozen=True)
class SceneBrief:
    """Validated input for the scene pipeline."""

    setting: str
    era: str
    region_m: int
    buildings: tuple[int, int]
    required_landmarks: tuple[Landmark, ...]
    targets: tuple[str, ...]
    seed: int = 1
    mood: str = ""
    notes: str = ""
    source_prompt: str = ""
    wall_time_ms: int = DEFAULT_WALL_TIME_MS
    model_calls: int = 0
    brief_version: str = BRIEF_VERSION
    extensions: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "brief_version": self.brief_version,
            "setting": self.setting,
            "era": self.era,
            "scale": {"region_m": self.region_m, "buildings": list(self.buildings)},
            "required_landmarks": [landmark.to_dict() for landmark in self.required_landmarks],
            "targets": list(self.targets),
            "seed": self.seed,
            "mood": self.mood,
            "notes": self.notes,
            "source_prompt": self.source_prompt,
            "budget": {"wall_time_ms": self.wall_time_ms, "model_calls": self.model_calls},
            "extensions": dict(self.extensions),
        }

    def digest(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()

    def requirements(self, pack: SettingPack) -> tuple[Landmark, ...]:
        """The brief's landmarks merged with the background's own requirements.

        A description of a harbour always implies piers and warehouses, so the
        catalogue's required entries are part of the effective requirement set
        even when the user only said "a harbour". When both name a type, the
        higher priority and the larger count win; the brief cannot lower what
        the background already requires.
        """
        # The catalogue's counts are written for the background's default region.
        # A brief that shrinks or grows the map scales them with it, so a 256 m
        # town is not asked to hold the same number of houses as a 512 m city
        # (the brief's own building budget scales the same way, and the two have
        # to stay comparable or `validate_brief` rejects the pair).
        factor = self.region_m / pack.default_scale["region_m"]
        merged: dict[str, Landmark] = {}
        for entry in pack.required_entries:
            merged[entry.type] = Landmark(type=entry.type,
                                          count=max(1, round(entry.count_range[0] * factor)),
                                          priority="must")
        for landmark in self.required_landmarks:
            existing = merged.get(landmark.type)
            if existing is None:
                merged[landmark.type] = landmark
                continue
            priority = landmark.priority if PRIORITIES.index(landmark.priority) < PRIORITIES.index(existing.priority) \
                else existing.priority
            merged[landmark.type] = Landmark(type=landmark.type, count=max(landmark.count, existing.count),
                                             priority=priority)
        order = {landmark.type: index for index, landmark in enumerate(self.required_landmarks)}
        return tuple(sorted(merged.values(), key=lambda item: (order.get(item.type, len(order)), item.type)))


def validate_brief(brief: SceneBrief, pack: SettingPack) -> None:
    """Raise `SceneError` when the brief disagrees with its setting pack."""
    if brief.brief_version != BRIEF_VERSION:
        raise SceneError("brief.version", f"brief_version must be {BRIEF_VERSION}")
    if brief.setting != pack.id:
        raise SceneError("brief.setting", f"brief names {brief.setting!r} but pack {pack.id!r} was loaded")
    if brief.era not in pack.eras:
        raise SceneError("brief.era", f"{brief.setting} declares era(s) {', '.join(pack.eras)}")
    if type(brief.region_m) is not int or not MIN_REGION_M <= brief.region_m <= MAX_REGION_M \
            or brief.region_m % REGION_STEP_M:
        raise SceneError("brief.scale", f"region_m must be a multiple of {REGION_STEP_M} within "
                                        f"{MIN_REGION_M}..{MAX_REGION_M}")
    low, high = brief.buildings
    if type(low) is not int or type(high) is not int or low < 1 or low > high:
        raise SceneError("brief.buildings", "buildings must be a whole-number range with 1 <= low <= high")
    if not brief.required_landmarks:
        raise SceneError("brief.landmarks", "a brief must name at least one required landmark")
    seen = set()
    for landmark in brief.required_landmarks:
        if landmark.type not in pack.entries:
            raise SceneError("brief.unknown_landmark",
                             f"{landmark.type!r} is not in the {pack.id} catalogue")
        if landmark.type in seen:
            raise SceneError("brief.duplicate_landmark", f"{landmark.type} appears twice")
        seen.add(landmark.type)
        if landmark.priority not in PRIORITIES:
            raise SceneError("brief.priority", f"priority must be one of {', '.join(PRIORITIES)}")
        if type(landmark.count) is not int or landmark.count < 1:
            raise SceneError("brief.landmark_count", f"{landmark.type}: count must be a positive whole number")
        entry = pack.entry(landmark.type)
        if landmark.count > entry.count_range[1]:
            raise SceneError("brief.landmark_count",
                             f"{landmark.type}: {landmark.count} exceeds the catalogue maximum "
                             f"{entry.count_range[1]}")
    if not brief.targets or any(target not in TARGETS for target in brief.targets):
        raise SceneError("brief.targets", f"targets must be a nonempty subset of {', '.join(TARGETS)}")
    # The background's own requirements count towards the building budget: a
    # brief that asks for 60 buildings but implies 90 required ones is a
    # contradiction, and it is cheaper to catch it here than in stage D.
    demanded = sum(landmark.count for landmark in brief.requirements(pack))
    if demanded > brief.buildings[1]:
        raise SceneError("brief.landmark_budget",
                         f"required landmarks demand {demanded} buildings but the brief allows at most "
                         f"{brief.buildings[1]}")
    if type(brief.seed) is not int or not 0 <= brief.seed < 2**64:
        raise SceneError("brief.seed", "seed must be an unsigned 64-bit integer")
    if type(brief.wall_time_ms) is not int or brief.wall_time_ms < 1:
        raise SceneError("brief.budget", "wall_time_ms must be positive")
    if type(brief.model_calls) is not int or brief.model_calls < 0:
        raise SceneError("brief.budget", "model_calls must be nonnegative")


def brief_from_dict(payload: dict, pack: SettingPack) -> SceneBrief:
    """Build a brief from JSON and validate it against the pack."""
    if not isinstance(payload, dict):
        raise SceneError("brief.json", "brief must be a JSON object")
    allowed = {"brief_version", "setting", "era", "scale", "required_landmarks", "targets", "seed",
               "mood", "notes", "source_prompt", "budget", "extensions"}
    extra = sorted(set(payload) - allowed)
    if extra:
        raise SceneError("brief.json", f"unknown brief field(s): {', '.join(extra)}")
    missing = {"brief_version", "setting", "era", "scale", "required_landmarks", "targets"} - set(payload)
    if missing:
        raise SceneError("brief.json", f"brief is missing {', '.join(sorted(missing))}")
    scale = payload["scale"]
    if not isinstance(scale, dict) or set(scale) != {"region_m", "buildings"}:
        raise SceneError("brief.scale", "scale must hold region_m and buildings")
    budget = payload.get("budget", {})
    if not isinstance(budget, dict) or set(budget) - {"wall_time_ms", "model_calls"}:
        raise SceneError("brief.budget", "budget may hold wall_time_ms and model_calls")
    landmarks = []
    for raw in payload["required_landmarks"]:
        if not isinstance(raw, dict) or "type" not in raw:
            raise SceneError("brief.landmarks", "each landmark needs a type")
        landmarks.append(Landmark(type=raw["type"], count=raw.get("count", 1), priority=raw.get("priority", "must")))
    target_list = payload["targets"]
    brief = SceneBrief(
        setting=payload["setting"], era=payload["era"], region_m=scale["region_m"],
        buildings=tuple(scale["buildings"]), required_landmarks=tuple(landmarks),
        targets=tuple(target_list) if isinstance(target_list, list) else target_list,
        seed=payload.get("seed", 1), mood=payload.get("mood", ""), notes=payload.get("notes", ""),
        source_prompt=payload.get("source_prompt", ""),
        wall_time_ms=budget.get("wall_time_ms", DEFAULT_WALL_TIME_MS),
        model_calls=budget.get("model_calls", 0), brief_version=payload["brief_version"],
        extensions=payload.get("extensions", {}))
    validate_brief(brief, pack)
    return brief


def load_brief(path: str | Path, pack: SettingPack) -> SceneBrief:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise SceneError("brief.read", f"cannot read {path}: {exc}") from exc
    except ValueError as exc:
        raise SceneError("brief.json", f"{path} is not valid JSON: {exc}") from exc
    return brief_from_dict(payload, pack)


# --- offline rule compiler -------------------------------------------------

# Keyword tables are code, not pack data: they describe how the *same*
# description maps onto whatever backgrounds exist, so a new pack does not need
# new parsing rules. Order is part of the contract because ties break by order.
SETTING_KEYWORDS = (
    ("arcane_medieval", ("魔法", "中世纪", "城邦", "城堡", "魔法师", "arcane", "medieval", "fantasy", "fortress")),
    ("modern_metropolis", ("现代", "大都市", "都市", "摩天", "天际线", "地铁", "cbd", "modern", "metropolis", "skyline")),
    ("industrial_park", ("工业", "产业园", "厂房", "工厂", "物流", "炼油", "industrial", "factory", "refinery")),
    ("harbour", ("港口", "码头", "港湾", "海运", "货轮", "船坞", "harbour", "harbor", "port", "dock")),
)
LANDMARK_KEYWORDS = (
    (("城堡", "castle"), "castle"), (("城墙", "护城", "city wall"), "city_wall"),
    (("工会", "冒险者", "guild"), "guild_hall"), (("教堂", "礼拜", "church", "temple"), "temple"),
    (("市政厅", "town hall"), "town_hall"), (("旅店", "客栈", "inn", "tavern"), "inn"),
    (("图书馆", "library"), "library"), (("铁匠", "锻造", "smith", "forge"), "workshop"),
    (("居民", "住宅", "民宅", "housing", "residence"), "residence"),
    (("广场", "plaza", "square"), "plaza"),
    (("摩天", "超高层", "skyscraper"), "skyscraper"), (("枢纽", "交通中心", "transit", "station"), "transit_hub"),
    (("地铁", "metro"), "metro_line"), (("医院", "hospital"), "hospital"),
    (("学校", "school"), "school"), (("公园", "绿地", "park"), "park"),
    (("机关", "政府", "government", "city hall"), "government"),
    (("写字楼", "办公楼", "office"), "office_block"), (("公寓", "apartment"), "apartment"),
    (("厂房", "车间", "factory", "plant"), "factory_hall"), (("仓库", "warehouse"), "warehouse"),
    (("储罐", "silo", "tank"), "silo_tank"), (("电厂", "power plant"), "power_plant"),
    (("铁路", "rail"), "rail_line"), (("码头", "pier", "wharf"), "pier"),
    (("船坞", "dry dock"), "dry_dock"), (("灯塔", "lighthouse"), "lighthouse"),
    (("货轮", "cargo", "ship"), "cargo_ship"), (("海关", "customs"), "customs_house"),
    (("堆场", "集装箱", "container"), "container_yard"),
)
SMALL_WORDS = ("小", "小镇", "村落", "村庄", "hamlet", "village")
LARGE_WORDS = ("大区域", "大都市圈", "巨型", "megacity", "region")


def compile_brief(prompt: str, seed: int = 1, root: Path | str = DEFAULT_SETTINGS_ROOT) -> SceneBrief:
    """Turn a description into a validated brief, offline and deterministically.

    This is the default implementation of stage A: no model call, no clock, no
    randomness. A model implementation must produce the same `SceneBrief`
    fields for the same description.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise SceneError("brief.prompt", "prompt must be a nonempty string")
    text = prompt.strip()
    lowered = text.lower()
    scored = []
    for setting_id, keywords in SETTING_KEYWORDS:
        hits = sum(1 for keyword in keywords if keyword in lowered)
        scored.append((hits, setting_id))
    best = max(hit for hit, _ in scored)
    if best == 0:
        raise SceneError("brief.setting_unknown",
                         "description names no known background; add its keywords or pass setting explicitly")
    setting_id = next(setting for hit, setting in scored if hit == best)
    pack = load_setting_pack(setting_id, root)

    region = pack.default_scale["region_m"]
    if any(word in lowered for word in SMALL_WORDS):
        region = max(MIN_REGION_M, region // 2)
    elif any(word in lowered for word in LARGE_WORDS):
        region = min(MAX_REGION_M, region * 2)
    factor = region / pack.default_scale["region_m"]
    low, high = pack.default_scale["buildings"]
    buildings = (max(1, round(low * factor)), max(1, round(high * factor)))

    landmarks: dict[str, Landmark] = {}
    for keywords, type_name in LANDMARK_KEYWORDS:
        if any(keyword in lowered for keyword in keywords) and type_name in pack.entries:
            landmarks[type_name] = Landmark(type=type_name, count=1, priority="must")
    if not landmarks:
        # Nothing specific was asked for, so the brief takes the background's
        # own requirements as its requirement list.
        landmarks = {entry.type: Landmark(type=entry.type, count=entry.count_range[0], priority="must")
                     for entry in pack.required_entries}

    mentioned = [target for target in TARGETS if target in lowered]
    if "我的世界" in lowered and "minecraft" not in mentioned:
        mentioned.append("minecraft")
    if "查看器" in lowered and "viewer" not in mentioned:
        mentioned.append("viewer")
    targets = tuple(mentioned) if mentioned else pack.default_targets

    brief = SceneBrief(
        setting=setting_id, era=pack.eras[0], region_m=region, buildings=buildings,
        required_landmarks=tuple(landmarks.values()), targets=targets, seed=seed,
        mood=text[:120], source_prompt=text,
        extensions={"compiled_by": "rule_compiler_v1", "background_hits": best})
    validate_brief(brief, pack)
    return brief


# --- optional model implementation of the same contract ---------------------

class BriefProvider(Protocol):
    """A source of brief proposals. The real service is a user decision."""

    def complete(self, prompt: str, seed: int) -> bytes: ...


@dataclass(frozen=True)
class FixtureBriefProvider:
    """Replay an already accepted response, offline and byte for byte."""

    path: str | Path

    def complete(self, prompt: str, seed: int) -> bytes:
        payload = Path(self.path).read_bytes()
        if len(payload) > MAX_RESPONSE_BYTES:
            raise SceneError("brief.response_too_large", f"{self.path} exceeds {MAX_RESPONSE_BYTES} bytes")
        return payload


def brief_from_response(raw: bytes, pack: SettingPack) -> SceneBrief:
    """Validate one accepted model response and turn it into a brief.

    The response is a proposal, not a licence: the same `validate_brief` rules
    apply, so a model cannot ask for a landmark the background lacks or a
    footprint the catalogue forbids. The accepted bytes are hashed into the
    brief so a run can be replayed and audited.
    """
    if not isinstance(raw, bytes) or len(raw) > MAX_RESPONSE_BYTES:
        raise SceneError("brief.response_size", f"response must be at most {MAX_RESPONSE_BYTES} bytes")
    try:
        payload = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise SceneError("brief.response_json", "response is not valid UTF-8 JSON") from exc
    required = {"contract_version", "provider_id", "model_id", "brief", "usage"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise SceneError("brief.response_shape",
                         f"response must contain exactly {', '.join(sorted(required))}")
    if payload["contract_version"] != MODEL_CONTRACT_VERSION:
        raise SceneError("brief.response_version", "unsupported model response version")
    if not isinstance(payload["provider_id"], str) or not payload["provider_id"].strip():
        raise SceneError("brief.response_provenance", "provider_id is required")
    if not isinstance(payload["model_id"], str) or not payload["model_id"].strip():
        raise SceneError("brief.response_provenance", "model_id is required")
    usage = payload["usage"]
    if not isinstance(usage, dict) or set(usage) != {"input_tokens", "output_tokens"} \
            or any(type(v) is not int or v < 0 for v in usage.values()):
        raise SceneError("brief.response_usage", "usage needs nonnegative input_tokens and output_tokens")
    brief = brief_from_dict(payload["brief"], pack)
    response_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
    extensions = dict(brief.extensions)
    extensions.update({"compiled_by": "model", "provider_id": payload["provider_id"],
                       "model_id": payload["model_id"], "accepted_response_hash": response_hash,
                       "usage": dict(usage)})
    return replace(brief, extensions=extensions)


def compile_brief_with_provider(prompt: str, seed: int, provider: BriefProvider,
                                setting: str, root: Path | str = DEFAULT_SETTINGS_ROOT) -> SceneBrief:
    """Ask the provider for a brief and validate it exactly like the offline one.

    The setting is explicit here: a model does not get to pick the background
    by keyword, the caller does. Nothing in this path is used unless a provider
    is configured, so the offline default never depends on a service.
    """
    pack = load_setting_pack(setting, root)
    return brief_from_response(provider.complete(prompt, seed), pack)
