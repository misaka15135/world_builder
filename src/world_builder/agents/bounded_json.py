"""Opt-in, auditable repair of two unambiguous provider JSON syntax errors."""
from __future__ import annotations

import json
import hashlib
import math

from .contracts import AgentError, canonical, strict_json


def _equal_duplicate_json(raw: bytes) -> tuple[object, bool]:
    duplicates = False

    def pairs(items):
        nonlocal duplicates
        value = {}
        for key, item in items:
            if key in value:
                if value[key] != item:
                    raise AgentError("json.conflicting_duplicate", f"Conflicting duplicate key: {key}")
                duplicates = True
            value[key] = item
        return value

    def invalid(value):
        raise AgentError("json.nonfinite", f"Nonfinite number: {value}")

    def number(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            invalid(value)
        return int(parsed) if parsed.is_integer() else parsed

    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid, parse_float=number)
    except (ValueError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, AgentError):
            raise
        raise AgentError("json.invalid", "Expected one UTF-8 JSON value, without Markdown") from exc
    return value, duplicates


def parse_bounded_json(raw: bytes) -> tuple[object, dict | None]:
    """Return parsed value and a manifest; never guess missing or conflicting data."""
    try:
        return strict_json(raw), None
    except AgentError as original:
        if original.code not in ("json.invalid", "json.duplicate_key"):
            raise
        stripped = raw.rstrip()
        candidates = [(raw, False)]
        if stripped.endswith(b"}"):
            candidates.append((stripped[:-1], True))
        for candidate, extra_closer in candidates:
            try:
                value, duplicate = _equal_duplicate_json(candidate)
            except AgentError:
                continue
            if not duplicate and not extra_closer:
                continue
            repaired = canonical(value)
            # Canonical encoding must itself pass the strict reader.
            strict_json(repaired)
            return value, {"mode": "bounded_syntax_v1", "extra_closing_brace": extra_closer,
                           "equal_duplicate_keys": duplicate,
                           "repaired_sha256": "sha256:" + hashlib.sha256(repaired).hexdigest()}
        raise original from None
