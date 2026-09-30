"""Executable JSON contracts; no defaults that invent a model's design."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from jsonschema import Draft202012Validator

from . import VERSION
from world_builder.resources import resource_root

ROOT = resource_root()
STAGES = ("A", "B", "C", "D", "E", "F")
MATERIALS = ("stone", "wood", "glass", "brick", "metal", "grass", "white", "water")


class AgentError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def digest(value) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def strict_json(raw: bytes | str):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise AgentError("json.duplicate_key", f"Duplicate key: {key}")
            result[key] = value
        return result

    def invalid(value):
        raise AgentError("json.nonfinite", f"Nonfinite number: {value}")

    def number(text):
        value = float(text)
        if not math.isfinite(value):
            invalid(text)
        # JSON Schema's integer includes 1.0 and 1e0. Canonicalise those
        # mathematically integral values before integer grid iteration.
        return int(value) if value.is_integer() else value

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid, parse_float=number)
    except (ValueError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, AgentError):
            raise
        raise AgentError("json.invalid", "Expected one UTF-8 JSON value, without Markdown") from exc


def obj(**properties):
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def arr(items, low=0, high=128):
    return {"type": "array", "items": items, "minItems": low, "maxItems": high}


def integer(low, high):
    return {"type": "integer", "minimum": low, "maximum": high}


def string(high=1000):
    return {"type": "string", "minLength": 1, "maxLength": high}


def enum(*values):
    return {"enum": list(values)}


ID = {"type": "string", "pattern": "^[a-z][a-z0-9_]{0,47}$"}
VEC = arr(integer(0, 512), 3, 3)
BOUNDS = obj(min=VEC, max=VEC)
RECT = arr(integer(0, 512), 4, 4)
MATERIAL = enum(*MATERIALS)
PAYLOADS = {
    "A": obj(title=string(120), region_m=integer(32, 512), style=string(2000),
             requirements=arr(obj(id=ID, description=string(), programme=string(100),
                                  min_count=integer(1, 64), max_count=integer(1, 64),
                                  interior_required={"type": "boolean"}), 1, 32),
             acceptance_criteria=arr(string(), 1, 24)),
    "B": obj(cell_m=integer(4, 128), heights=arr(arr(integer(1, 24), 1, 32), 1, 32),
             ground_material=enum("grass", "stone", "brick"),
             water=arr(obj(id=ID, bounds=BOUNDS), 0, 64), rationale=string(2000)),
    "C": obj(types=arr(obj(id=ID, requirement_id=ID, programme=string(100),
                           count=integer(1, 64), size_m=arr(integer(4, 96), 2, 2),
                           max_height_m=integer(3, 48), design_brief=string(3000)), 1, 32)),
    "D": obj(districts=arr(obj(id=ID, rect=RECT, purpose=string()), 1, 64),
             sites=arr(obj(id=ID, type_id=ID, district_id=ID, bounds=BOUNDS,
                           foundation={"type": "boolean"}), 1, 64),
             roads=arr(obj(id=ID, bounds=BOUNDS, kind=enum("road", "bridge"),
                           material=enum("stone", "wood", "brick")), 1, 256)),
    "E": obj(site_id=ID, concept=string(3000),
             parts=arr(obj(id=ID, role=enum("foundation", "floor", "wall", "roof", "stair",
                                          "window", "column", "furniture", "landscape"),
                           bounds=BOUNDS, material=enum(*(m for m in MATERIALS if m != "water"))), 1, 512),
             spaces=arr(obj(id=ID, programme=string(100), bounds=BOUNDS, access_cell=VEC), 0, 64),
             entry_cell=VEC, routes=arr(obj(space_id=ID, cells=arr(VEC, 1, 1024)), 0, 64)),
    "F": obj(verdict=enum("accept", "revise"), accepted_sites=arr(ID, 0, 64),
             requirement_review=arr(obj(requirement_id=ID, satisfied={"type": "boolean"},
                                         evidence=string(2000)), 1, 32),
             fixes=arr(obj(stage=enum("B", "C", "D", "E"), scope_id=ID, reason=string(2000)), 0, 16),
             limitations=arr(string(2000), 0, 32)),
}


def response_schema(stage: str, request_id: str | None = None, scope_id: str | None = None) -> dict:
    result = obj(contract_version={"const": VERSION}, stage={"const": stage},
                 request_id={"const": request_id} if request_id else {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
                 scope_id={"const": scope_id} if scope_id else ID, payload=PAYLOADS[stage])
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", **result}


def validate_schema(value, schema, code="contract.schema"):
    # jsonschema permits NaN as a number; canonical JSON does not.
    try:
        canonical(value)
    except (ValueError, TypeError, RecursionError) as exc:
        raise AgentError(code, "Value is not finite canonical JSON") from exc
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda e: str(e.path))
    if errors:
        messages = [f"/{'/'.join(map(str, e.absolute_path))}: {e.message}" for e in errors[:8]]
        raise AgentError(code, "\n".join(messages)[:6000])


def contract_document():
    return {"$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://world-builder.local/contracts/agent-response-0.1.0",
            "oneOf": [response_schema(stage) for stage in STAGES]}


CONFIG_SCHEMA = obj(
    contract_version={"const": VERSION}, endpoint=string(2048), model=string(200),
    api_key_env={"type": "string", "pattern": "^[A-Z][A-Z0-9_]{0,127}$"},
    protocol=enum("chat_completions", "json_contract"),
    response_format=enum("json_object", "json_schema"),
    token_parameter=enum("max_completion_tokens", "max_tokens"),
    stage_models=obj(**{stage: string(200) for stage in STAGES}),
    limits=obj(max_calls=integer(6, 512), max_total_tokens=integer(1000, 4000000),
               max_output_tokens=integer(512, 64000), max_response_bytes=integer(4096, 2000000),
               timeout_s=integer(1, 300), wall_time_s=integer(1, 7200),
               attempts=integer(1, 4), review_rounds=integer(0, 3),
               workers=integer(1, 8), max_sites=integer(1, 64),
               max_parts=integer(1, 16000), max_voxels=integer(1000, 20000000)))

HASH = {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}
E_MAP = {"type": "object", "patternProperties": {ID["pattern"]: PAYLOADS["E"]},
         "additionalProperties": False, "minProperties": 1, "maxProperties": 64}
REQUEST_SCHEMA = obj(
    contract_version={"const": VERSION}, stage=enum(*STAGES), scope_id=ID, request_id=HASH,
    prompt=string(20000), seed=integer(0, 2**64 - 1), region_m=integer(32, 512),
    units={"const": "m"}, axes={"const": "RH_X_east_Y_north_Z_up"}, geometry={"const": "integer_cuboids_v1"},
    limits=CONFIG_SCHEMA["properties"]["limits"], attempt=integer(1, 4), revision_round=integer(0, 3),
    dependencies=arr({"oneOf": [obj(stage={"const": stage}, sha256=HASH,
                                    data=E_MAP if stage == "E" else PAYLOADS[stage])
                                  for stage in STAGES]}, 0, 5),
    feedback=arr({"oneOf": [PAYLOADS["F"]["properties"]["fixes"]["items"],
                            obj(code=string(200), message=string(6000),
                                rejected_response={"type": ["string", "null"], "maxLength": 12000})]}, 0, 16),
    instructions=string(40000),
    # Trusted, locally generated schema document, not model-authored policy.
    response_schema={"type": "object"})
