"""Replaceable API boundary. Providers never plan geometry or execute tools."""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from .contracts import AgentError, CONFIG_SCHEMA, VERSION, canonical, strict_json, validate_schema


@dataclass(frozen=True)
class Completion:
    raw: bytes
    model: str
    input_tokens: int
    output_tokens: int
    source: str


class Provider(Protocol):
    network: bool

    def complete(self, request: dict, *, timeout_s: float) -> Completion: ...


def load_config(path):
    config = strict_json(Path(path).read_bytes())
    validate_schema(config, CONFIG_SCHEMA, "config.schema")
    return config


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class APIProvider:
    network = True

    def __init__(self, config: dict, *, api_key: str | None = None):
        validate_schema(config, CONFIG_SCHEMA, "config.schema")
        self.config = config
        endpoint = urlsplit(config["endpoint"])
        if "yourapi" in config["endpoint"].lower() or config["model"].lower() == "yourapi":
            raise AgentError("api.placeholder", "Replace yourapi endpoint and model in your local config")
        if endpoint.scheme != "https" or not endpoint.hostname or endpoint.username or endpoint.password or endpoint.fragment or endpoint.query:
            raise AgentError("api.endpoint", "Use a full HTTPS endpoint without credentials, query or fragment")
        self.key = os.environ.get(config["api_key_env"], "") if api_key is None else api_key
        if not self.key or self.key.lower() == "yourapi":
            raise AgentError("api.credential", f"Set environment variable {config['api_key_env']}")

    def complete(self, request, *, timeout_s):
        config = self.config
        chosen = config["stage_models"][request["stage"]]
        model = config["model"] if chosen == "yourapi" else chosen
        if config["protocol"] == "chat_completions":
            # The skill is privileged local configuration; all proposals and
            # user descriptions remain data inside the user message.
            data = {k: v for k, v in request.items() if k != "instructions"}
            body = {"model": model, "stream": False,
                    "messages": [{"role": "system", "content": request["instructions"]},
                                 {"role": "user", "content": canonical(data).decode("utf-8")}],
                    config["token_parameter"]: config["limits"]["max_output_tokens"],
                    "response_format": {"type": config["response_format"]}}
            if config["response_format"] == "json_schema":
                schema = {k: v for k, v in request["response_schema"].items() if k != "$schema"}
                body["response_format"]["json_schema"] = {
                    "name": f"world_builder_{request['stage']}", "strict": True, "schema": schema}
        else:
            body = {"model": model, "max_output_tokens": config["limits"]["max_output_tokens"], "request": request}
        req = urllib.request.Request(config["endpoint"], data=canonical(body), method="POST",
                                     headers={"Authorization": "Bearer " + self.key,
                                              "Content-Type": "application/json", "Accept": "application/json"})
        try:
            # No implicit network retry: all attempts are charged and journaled
            # by the supervisor. Redirects cannot forward the user's credential.
            with urllib.request.build_opener(NoRedirect()).open(req, timeout=timeout_s) as response:
                if response.status != 200:
                    raise AgentError("api.status", f"HTTP {response.status}")
                wire = response.read(config["limits"]["max_response_bytes"] + 1)
        except urllib.error.HTTPError as exc:
            raise AgentError("api.http", f"HTTP {exc.code}; inspect provider configuration or quota") from None
        except (OSError, TimeoutError) as exc:
            raise AgentError("api.transport", f"API request failed: {type(exc).__name__}") from None
        if len(wire) > config["limits"]["max_response_bytes"]:
            raise AgentError("api.response_size", "API response exceeds byte budget")
        return decode_wire(wire, model, config["protocol"])


def decode_wire(wire, model, protocol):
    body = strict_json(wire)
    try:
        if protocol == "chat_completions":
            choices = body["choices"]
            if len(choices) != 1 or choices[0]["finish_reason"] != "stop":
                raise AgentError("api.incomplete", "Expected exactly one complete, non-tool response")
            message = choices[0]["message"]
            if message.get("refusal") or message.get("tool_calls"):
                raise AgentError("api.refusal", "Provider refused or attempted a tool call")
            content = message["content"]
            if not isinstance(content, str):
                raise AgentError("api.content", "Expected text containing the response JSON")
            raw = content.encode("utf-8")
            input_tokens, output_tokens = body["usage"]["prompt_tokens"], body["usage"]["completion_tokens"]
        else:
            if set(body) != {"response", "usage", "model"}:
                raise AgentError("api.contract", "Expected response, usage and model")
            raw = canonical(body["response"])
            input_tokens, output_tokens = body["usage"]["input_tokens"], body["usage"]["output_tokens"]
        if any(type(v) is not int or v < 0 for v in (input_tokens, output_tokens)):
            raise AgentError("api.usage", "Provider must report nonnegative integer token usage")
        actual_model = body.get("model", model)
        if not isinstance(actual_model, str) or not actual_model:
            raise AgentError("api.model", "Provider must identify its model")
        return Completion(raw, actual_model, input_tokens, output_tokens, "api")
    except (KeyError, IndexError, TypeError) as exc:
        raise AgentError("api.envelope", "Malformed provider response or missing token usage") from exc


class FixtureProvider:
    """Hand-authored protocol examples, explicitly not model-quality evidence."""
    network = False

    def __init__(self, path):
        self.data = strict_json(Path(path).read_bytes())

    def complete(self, request, *, timeout_s):
        key = request["stage"] + ":" + request["scope_id"]
        if key not in self.data["responses"]:
            raise AgentError("fixture.missing", f"No synthetic response for {key}")
        envelope = {key: request[key] for key in ("contract_version", "stage", "request_id", "scope_id")}
        envelope["payload"] = self.data["responses"][key]
        return Completion(canonical(envelope), "synthetic-fixture", 0, 0, "synthetic_fixture")


class ReplayProvider:
    """Replay exact recorded bytes by input digest, never by stage name alone."""
    network = False

    def __init__(self, run_dir):
        self.root = Path(run_dir)

    def complete(self, request, *, timeout_s):
        key = request["request_id"].removeprefix("sha256:")
        # The request ID is produced by the local supervisor, not supplied by a model.
        path = self.root / "calls" / key
        try:
            saved = strict_json((path / "request.json").read_bytes())
            if saved != request:
                raise AgentError("replay.mismatch", "Recorded request differs")
            if not (path / "response.json").exists() and (path / "error.json").exists():
                failure = strict_json((path / "error.json").read_bytes())
                raise AgentError(failure["code"], failure["message"])
            meta = strict_json((path / "completion.json").read_bytes())
            raw = (path / "response.json").read_bytes()
        except OSError as exc:
            raise AgentError("replay.missing", f"No recorded response for {request['stage']}:{request['scope_id']}") from exc
        if saved != request or meta["response_sha256"] != "sha256:" + hashlib.sha256(raw).hexdigest():
            raise AgentError("replay.mismatch", "Recorded request or response hash differs")
        return Completion(raw, meta["model"], meta["input_tokens"], meta["output_tokens"], "replay")
