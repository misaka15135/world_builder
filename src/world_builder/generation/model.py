"""Versioned, replaceable prompt-to-pilot-spec service contract.

The HTTP adapter uses this project's own JSON protocol. It does not assume a
particular model vendor's wire format, tool calls or deterministic sampling.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from world_builder.storage.repository import Repository, StoreError

from .spec import PilotSpec, canonical

CONTRACT_VERSION = "0.1.0"
MAX_RESPONSE_BYTES = 65_536
OUTPUT_FIELDS = {"scenario", "building_count", "interior_count", "layout_profile", "lock_stair_void"}


class ModelContractError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


class SpecProvider(Protocol):
    def complete(self, prompt: str, seed: int) -> bytes: ...


@dataclass(frozen=True)
class PreparedSpec:
    spec: PilotSpec
    response_bytes: bytes


class FixtureProvider:
    """Use an already accepted, local response for offline replay and tests."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def complete(self, prompt: str, seed: int) -> bytes:
        if self.path.stat().st_size > MAX_RESPONSE_BYTES:
            raise ModelContractError("contract.response_too_large", str(self.path))
        return self.path.read_bytes()


class HttpJSONProvider:
    """POST the contract request to a configured HTTPS JSON service."""

    def __init__(self, endpoint: str, model_id: str, api_key_env: str | None = None, timeout_s: float = 20):
        parts = urlsplit(endpoint)
        if parts.scheme != "https" or not parts.netloc or parts.username or parts.password or parts.fragment:
            raise ModelContractError("contract.endpoint", "model endpoint must be an HTTPS URL without embedded credentials or fragment")
        if not model_id or timeout_s <= 0:
            raise ModelContractError("contract.model_configuration", "model ID and positive timeout are required")
        self.endpoint, self.model_id = endpoint, model_id
        self.api_key_env, self.timeout_s = api_key_env, timeout_s

    def complete(self, prompt: str, seed: int) -> bytes:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key_env:
            key = os.environ.get(self.api_key_env)
            if not key:
                raise ModelContractError("contract.credential_missing", f"environment variable {self.api_key_env} is empty")
            headers["Authorization"] = "Bearer " + key
        body = canonical({"contract_version": CONTRACT_VERSION, "model_id": self.model_id,
                          "prompt": prompt, "seed": seed,
                          "response_fields": sorted(OUTPUT_FIELDS), "response_format": "json_object"})
        request = urllib.request.Request(self.endpoint, data=body, headers=headers, method="POST")
        try:
            # Do not forward a credential through a server-selected redirect.
            opener = urllib.request.build_opener(_NoRedirect())
            with opener.open(request, timeout=self.timeout_s) as response:
                if response.status != 200:
                    raise ModelContractError("execution.model_http", f"HTTP {response.status}")
                payload = response.read(MAX_RESPONSE_BYTES + 1)
        except (OSError, TimeoutError) as exc:
            raise ModelContractError("execution.model_unavailable", str(exc)) from exc
        if len(payload) > MAX_RESPONSE_BYTES:
            raise ModelContractError("contract.response_too_large", "model response exceeded 64 KiB")
        return payload


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def compile_spec(prompt: str, seed: int, provider: SpecProvider, *, max_total_tokens: int = 4000) -> PreparedSpec:
    """Accept exactly one response after validating its bounded declared fields."""
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 20_000:
        raise ModelContractError("contract.prompt", "prompt must be 1..20000 characters")
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ModelContractError("contract.seed", "seed must be unsigned 64-bit")
    if type(max_total_tokens) is not int or max_total_tokens < 1:
        raise ModelContractError("contract.token_budget", "max_total_tokens must be positive")
    raw = provider.complete(prompt, seed)
    if not isinstance(raw, bytes) or len(raw) > MAX_RESPONSE_BYTES:
        raise ModelContractError("contract.response_size", "provider must return at most 64 KiB of bytes")
    try:
        response = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise ModelContractError("contract.response_json", "response is not valid UTF-8 JSON") from exc
    if not isinstance(response, dict) or set(response) != {"contract_version", "provider_id", "model_id", "candidate", "usage"}:
        raise ModelContractError("contract.response_shape", "response must contain contract_version, provider_id, model_id, candidate and usage only")
    if response["contract_version"] != CONTRACT_VERSION:
        raise ModelContractError("contract.version", "unsupported model response version")
    if not isinstance(response["provider_id"], str) or not response["provider_id"] or not isinstance(response["model_id"], str) or not response["model_id"]:
        raise ModelContractError("contract.provenance", "provider and model ID are required")
    usage = response["usage"]
    if not isinstance(usage, dict) or set(usage) != {"input_tokens", "output_tokens"} or any(type(usage[k]) is not int or usage[k] < 0 for k in usage):
        raise ModelContractError("contract.usage", "nonnegative integer input/output token counts are required")
    if sum(usage.values()) > max_total_tokens:
        raise ModelContractError("execution.model_token_budget", "reported token usage exceeds the configured budget")
    candidate = response["candidate"]
    if not isinstance(candidate, dict) or not set(candidate) <= OUTPUT_FIELDS or set(candidate) != OUTPUT_FIELDS:
        raise ModelContractError("contract.candidate_shape", "candidate must contain exactly the five supported pilot fields")
    content_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
    provenance = {"contract_version": CONTRACT_VERSION, "provider_id": response["provider_id"],
                  "model_id": response["model_id"], "usage": usage, "max_total_tokens": max_total_tokens,
                  "response_hash": content_hash}
    try:
        spec = PilotSpec(seed=seed, source_prompt=prompt, accepted_response_hash=content_hash,
                         model_provenance=provenance, **candidate)
    except (TypeError, ValueError) as exc:
        raise ModelContractError("contract.candidate_invalid", str(exc)) from exc
    return PreparedSpec(spec, raw)


def publish_accepted(repository: Repository, prepared: PreparedSpec) -> PilotSpec:
    content_hash, _ = repository.publish(prepared.response_bytes)
    if content_hash != prepared.spec.accepted_response_hash:
        raise StoreError("resource.hash_mismatch", "accepted model response")
    return prepared.spec


def replay_spec(repository: Repository, world_id: str) -> PilotSpec:
    """Recover the accepted spec and response without calling its provider."""
    package = repository.load(world_id)
    record = next(r for r in package["records"] if r["record_type"] == "world_spec")
    spec = PilotSpec(**record["extensions"]["pilot_spec"])
    if spec.accepted_response_hash is None:
        raise ModelContractError("contract.no_accepted_response", "world was generated from a fixed local spec")
    asset = next((r for r in package["records"] if r["id"] == "asset_model_response"), None)
    if asset is None or asset["content_hash"] != spec.accepted_response_hash:
        raise ModelContractError("resource.accepted_response_missing", world_id)
    raw = (repository.root / asset["uri"]).read_bytes()
    compiled = compile_spec(spec.source_prompt, spec.seed, FixtureBytes(raw),
                            max_total_tokens=spec.model_provenance["max_total_tokens"])
    if compiled.spec != spec:
        raise ModelContractError("contract.replay_mismatch", "accepted response no longer matches the saved spec")
    return spec


class FixtureBytes:
    def __init__(self, payload: bytes):
        self.payload = payload

    def complete(self, prompt: str, seed: int) -> bytes:
        return self.payload
