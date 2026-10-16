"""Setting packs: what a background is allowed to contain (work order 015).

A setting pack is data, not code. Adding a background means adding a directory
under `settings/` holding a `setting.json` (identity, era, materials, terrain
preferences, default scale) and a `catalogue.json` (the building and landmark
repertoire with sizes, adjacency and site needs). The pipeline only reads
packs, so a new background never edits the generator.

Every catalogue entry declares whether a design exists yet. `implemented`
entries must name the generator programme they map to; `planned` entries must
carry a note saying what is missing. That field is what keeps the repertoire
from reading as delivered capability.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from world_builder.resources import resource_root

SETTING_VERSION = "0.1.1"
CATALOGUE_VERSION = "0.1.0"
REPO_ROOT = resource_root()
DEFAULT_SETTINGS_ROOT = REPO_ROOT / "settings"

ROLES = ("landmark", "civic", "commerce", "craft", "housing", "infrastructure", "defence", "green", "vessel")
DESIGN_STATES = ("implemented", "planned")
STYLE_PROFILES = ("arcane_medieval", "modern_grid")
TARGETS = ("minecraft", "unity", "viewer", "ifc")
PRIORITIES = ("must", "should", "may")
# Site features an entry may sit next to or require. Catalogue types are also
# allowed in `adjacency` (a hall next to a temple), but `needs` is about the
# site itself, so it only accepts these.
SITE_FEATURES = ("plaza", "water", "coast", "road", "rail", "centre", "hill", "gate")
MATERIAL_ROLES = ("shell", "floor", "roof", "street", "accent")

SETTING_KEYS = {"setting_version", "id", "display_name", "eras", "summary", "style_profile",
                "materials", "terrain_preferences", "default_scale", "default_targets", "default_prompt"}
CATALOGUE_KEYS = {"catalogue_version", "setting", "entries"}
ENTRY_REQUIRED_KEYS = {"type", "role", "required", "count_range", "design_state"}
ENTRY_OPTIONAL_KEYS = {"footprint_m2_range", "linear_m", "width_m_range", "height_m_range",
                       "adjacency", "needs", "maps_to_programme", "silhouette", "note"}


class SceneError(ValueError):
    """A planning artifact failed validation; the code names the failing rule."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def _number_range(value, field: str, code: str, *, minimum: float = 0.0, integral: bool = False):
    if not isinstance(value, list) or len(value) != 2:
        raise SceneError(code, f"{field} must be a two-element range")
    if any(type(v) not in (int, float) for v in value):
        raise SceneError(code, f"{field} must contain numbers")
    if integral and any(type(v) is not int for v in value):
        raise SceneError(code, f"{field} must contain whole numbers")
    low, high = float(value[0]), float(value[1])
    if low > high or low < minimum:
        raise SceneError(code, f"{field} must satisfy {minimum} <= low <= high")
    return (low, high) if not integral else (int(low), int(high))


@dataclass(frozen=True)
class CatalogueEntry:
    """One building or work type a background may contain."""

    type: str
    role: str
    required: bool
    count_range: tuple[int, int]
    design_state: str
    footprint_m2_range: tuple[float, float] | None = None
    height_m_range: tuple[float, float] | None = None
    linear_m: tuple[float, float] | None = None
    width_m_range: tuple[float, float] | None = None
    adjacency: tuple[str, ...] = ()
    needs: tuple[str, ...] = ()
    maps_to_programme: str | None = None
    silhouette: str = ""
    note: str = ""

    @property
    def footprint_kind(self) -> str:
        return "linear" if self.linear_m is not None else "area"


@dataclass(frozen=True)
class SettingPack:
    """A loaded, validated background."""

    id: str
    display_name: str
    eras: tuple[str, ...]
    summary: str
    style_profile: str
    materials: dict
    terrain_preferences: dict
    default_scale: dict
    default_targets: tuple[str, ...]
    default_prompt: str
    entries: dict
    root: Path

    def entry(self, type_name: str) -> CatalogueEntry:
        try:
            return self.entries[type_name]
        except KeyError:
            raise SceneError("catalogue.unknown_type", f"{self.id} has no catalogue entry {type_name!r}") from None

    @property
    def required_entries(self) -> tuple[CatalogueEntry, ...]:
        return tuple(entry for entry in self.entries.values() if entry.required)

    @property
    def implemented_entries(self) -> tuple[CatalogueEntry, ...]:
        return tuple(entry for entry in self.entries.values() if entry.design_state == "implemented")

    @property
    def planned_entries(self) -> tuple[CatalogueEntry, ...]:
        return tuple(entry for entry in self.entries.values() if entry.design_state == "planned")

    def summary_counts(self) -> dict:
        return {"entries": len(self.entries), "required": len(self.required_entries),
                "implemented": len(self.implemented_entries), "planned": len(self.planned_entries)}


def _load_json(path: Path, code: str) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SceneError(code, f"cannot read {path}: {exc}") from exc
    except ValueError as exc:
        raise SceneError(code, f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SceneError(code, f"{path} must contain a JSON object")
    return payload


def _exact_keys(payload: dict, allowed: set, code: str, label: str) -> None:
    extra = sorted(set(payload) - allowed)
    if extra:
        raise SceneError(code, f"{label} has unknown field(s): {', '.join(extra)}")


def _parse_entry(raw: dict, setting_id: str, types: set) -> CatalogueEntry:
    code = "catalogue.entry"
    if not isinstance(raw, dict):
        raise SceneError(code, "each catalogue entry must be an object")
    missing = sorted(ENTRY_REQUIRED_KEYS - set(raw))
    if missing:
        raise SceneError(code, f"entry is missing {', '.join(missing)}")
    _exact_keys(raw, ENTRY_REQUIRED_KEYS | ENTRY_OPTIONAL_KEYS, code, "catalogue entry")
    type_name = raw["type"]
    if not isinstance(type_name, str) or not type_name.strip():
        raise SceneError(code, "entry type must be a nonempty string")
    if raw["role"] not in ROLES:
        raise SceneError(code, f"{type_name}: role must be one of {', '.join(ROLES)}")
    if type(raw["required"]) is not bool:
        raise SceneError(code, f"{type_name}: required must be a boolean")
    count_range = _number_range(raw["count_range"], f"{type_name}.count_range", code, minimum=0, integral=True)
    if raw["design_state"] not in DESIGN_STATES:
        raise SceneError(code, f"{type_name}: design_state must be one of {', '.join(DESIGN_STATES)}")
    footprint = height = linear = width = None
    if ("footprint_m2_range" in raw) == ("linear_m" in raw):
        raise SceneError(code, f"{type_name}: declare exactly one of footprint_m2_range or linear_m")
    if "footprint_m2_range" in raw:
        footprint = _number_range(raw["footprint_m2_range"], f"{type_name}.footprint_m2_range", code, minimum=1.0)
        if "width_m_range" in raw:
            raise SceneError(code, f"{type_name}: width_m_range belongs to linear works")
    else:
        linear = _number_range(raw["linear_m"], f"{type_name}.linear_m", code, minimum=1.0)
        if "width_m_range" not in raw:
            raise SceneError(code, f"{type_name}: a linear work also needs width_m_range")
        width = _number_range(raw["width_m_range"], f"{type_name}.width_m_range", code, minimum=0.5)
    if "height_m_range" in raw:
        height = _number_range(raw["height_m_range"], f"{type_name}.height_m_range", code, minimum=0.0)
    adjacency = tuple(raw.get("adjacency", ()))
    needs = tuple(raw.get("needs", ()))
    for feature in adjacency:
        if not isinstance(feature, str) or (feature not in SITE_FEATURES and feature not in types):
            raise SceneError(code, f"{type_name}: adjacency {feature!r} is neither a site feature nor a catalogue type")
    for feature in needs:
        if feature not in SITE_FEATURES:
            raise SceneError(code, f"{type_name}: needs {feature!r} must be a site feature")
    if raw["required"] and count_range[0] < 1:
        raise SceneError(code, f"{type_name}: a required entry needs count_range low >= 1")
    programme = raw.get("maps_to_programme")
    if raw["design_state"] == "implemented" and not programme:
        raise SceneError(code, f"{type_name}: implemented designs must name maps_to_programme")
    if raw["design_state"] == "planned" and programme:
        raise SceneError(code, f"{type_name}: planned designs must not claim a programme mapping")
    note = raw.get("note", "")
    if raw["design_state"] == "planned" and not note.strip():
        raise SceneError(code, f"{type_name}: planned designs must say what is missing in note")
    return CatalogueEntry(type=type_name, role=raw["role"], required=raw["required"], count_range=count_range,
                          design_state=raw["design_state"], footprint_m2_range=footprint, height_m_range=height,
                          linear_m=linear, width_m_range=width, adjacency=adjacency, needs=needs,
                          maps_to_programme=programme, silhouette=raw.get("silhouette", ""), note=note)


def parse_catalogue(payload: dict, setting_id: str) -> dict:
    """Validate a catalogue document and return its entries by type."""
    code = "catalogue.document"
    _exact_keys(payload, CATALOGUE_KEYS, code, "catalogue")
    if payload.get("catalogue_version") != CATALOGUE_VERSION:
        raise SceneError(code, f"catalogue_version must be {CATALOGUE_VERSION}")
    if payload.get("setting") != setting_id:
        raise SceneError(code, f"catalogue belongs to {payload.get('setting')!r}, loaded as {setting_id!r}")
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise SceneError(code, "catalogue needs a nonempty entries list")
    types = {raw.get("type") for raw in raw_entries if isinstance(raw, dict)}
    if len(types) != len(raw_entries):
        raise SceneError(code, "catalogue entry types must be unique and present")
    entries = {}
    for raw in raw_entries:
        entry = _parse_entry(raw, setting_id, types)
        entries[entry.type] = entry
    return entries


def parse_setting(payload: dict, setting_id: str) -> dict:
    """Validate a setting document and return the fields the pipeline reads."""
    code = "setting.document"
    _exact_keys(payload, SETTING_KEYS, code, "setting")
    missing = sorted(SETTING_KEYS - set(payload))
    if missing:
        raise SceneError(code, f"setting.json is missing {', '.join(missing)}")
    if payload["setting_version"] != SETTING_VERSION:
        raise SceneError(code, f"setting_version must be {SETTING_VERSION}")
    if payload["id"] != setting_id:
        raise SceneError(code, f"setting id {payload['id']!r} does not match directory {setting_id!r}")
    for field in ("display_name", "summary", "default_prompt"):
        if not isinstance(payload[field], str) or not payload[field].strip():
            raise SceneError(code, f"{field} must be a nonempty string")
    eras = payload["eras"]
    if not isinstance(eras, list) or not eras or any(not isinstance(e, str) or not e.strip() for e in eras):
        raise SceneError(code, "eras must be a nonempty list of names")
    if payload["style_profile"] not in STYLE_PROFILES:
        raise SceneError(code, f"style_profile must be one of {', '.join(STYLE_PROFILES)}")
    materials = payload["materials"]
    if not isinstance(materials, dict) or not materials:
        raise SceneError(code, "materials must map at least one material role to a block or material")
    unknown = sorted(set(materials) - set(MATERIAL_ROLES))
    if unknown:
        raise SceneError(code, f"materials has unknown role(s): {', '.join(unknown)}")
    if any(not isinstance(v, str) or not v.strip() for v in materials.values()):
        raise SceneError(code, "material values must be nonempty strings")
    preferences = payload["terrain_preferences"]
    if not isinstance(preferences, dict) or any(not isinstance(v, str) for v in preferences.values()):
        raise SceneError(code, "terrain_preferences must be a mapping of strings")
    scale = payload["default_scale"]
    if not isinstance(scale, dict) or set(scale) != {"region_m", "buildings"}:
        raise SceneError(code, "default_scale must hold region_m and buildings")
    region = scale["region_m"]
    if type(region) is not int or region < 128 or region > 4096 or region % 128:
        raise SceneError(code, "default_scale.region_m must be a multiple of 128 between 128 and 4096")
    buildings = _number_range(scale["buildings"], "default_scale.buildings", code, minimum=1, integral=True)
    targets = payload["default_targets"]
    if not isinstance(targets, list) or not targets or any(t not in TARGETS for t in targets):
        raise SceneError(code, f"default_targets must be a nonempty subset of {', '.join(TARGETS)}")
    return {"display_name": payload["display_name"], "eras": tuple(eras), "summary": payload["summary"],
            "style_profile": payload["style_profile"], "materials": dict(materials),
            "terrain_preferences": dict(preferences),
            "default_scale": {"region_m": region, "buildings": buildings}, "default_targets": tuple(targets),
            "default_prompt": payload["default_prompt"]}


def available_settings(root: Path | str = DEFAULT_SETTINGS_ROOT) -> tuple[str, ...]:
    """Directory names under `settings/`, in a stable order."""
    directory = Path(root)
    if not directory.is_dir():
        raise SceneError("setting.root", f"settings root {directory} does not exist")
    return tuple(sorted(p.name for p in directory.iterdir() if (p / "setting.json").is_file()))


def load_setting_pack(setting_id: str, root: Path | str = DEFAULT_SETTINGS_ROOT) -> SettingPack:
    """Load and validate one background by id."""
    if not isinstance(setting_id, str) or not setting_id.strip():
        raise SceneError("setting.id", "setting id must be a nonempty string")
    directory = Path(root) / setting_id
    if not (directory / "setting.json").is_file():
        raise SceneError("setting.unknown", f"no setting pack {setting_id!r} under {Path(root)}")
    setting = parse_setting(_load_json(directory / "setting.json", "setting.document"), setting_id)
    entries = parse_catalogue(_load_json(directory / "catalogue.json", "catalogue.document"), setting_id)
    return SettingPack(id=setting_id, root=directory, entries=entries, **setting)
