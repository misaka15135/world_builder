"""Replaceable API boundary. Providers never plan geometry or execute tools."""
from __future__ import annotations

import hashlib
import json
import os
import re
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


def _http_error_message(exc: urllib.error.HTTPError, key: str) -> str:
    """Keep a bounded provider hint, never an authorization value or raw body."""
    fallback = f"HTTP {exc.code}; inspect provider configuration or quota"
    try:
        payload = json.loads(exc.read(4096))
        error = payload.get("error") if isinstance(payload, dict) else None
        if not isinstance(error, dict):
            return fallback
        fields = []
        for name in ("type", "code", "param", "message"):
            value = error.get(name)
            if not isinstance(value, str) or not value:
                continue
            value = value.replace(key, "[redacted]")
            value = re.sub(r"(?i)sk[-_][A-Za-z0-9_-]{8,}", "[redacted]", value)
            value = " ".join(value.split())[:300]
            fields.append(f"{name}={value}")
        return f"HTTP {exc.code}; " + "; ".join(fields) if fields else fallback
    except (OSError, ValueError, TypeError):
        return fallback


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
        if "deepseek_thinking" in config and (endpoint.hostname != "api.deepseek.com" or
                                              config["protocol"] != "chat_completions"):
            raise AgentError("api.config", "deepseek_thinking requires the official DeepSeek Chat endpoint")
        if "deepseek_reasoning" in config and (endpoint.hostname != "api.deepseek.com" or
                                               config["protocol"] != "responses"):
            raise AgentError("api.config", "deepseek_reasoning requires the official DeepSeek Responses endpoint")
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
            if "deepseek_thinking" in config:
                body["thinking"] = {"type": config["deepseek_thinking"]}
            if config["response_format"] == "json_schema":
                schema = {k: v for k, v in request["response_schema"].items() if k != "$schema"}
                body["response_format"]["json_schema"] = {
                    "name": f"world_builder_{request['stage']}", "strict": True, "schema": schema}
        elif config["protocol"] == "responses":
            data = {k: v for k, v in request.items() if k != "instructions"}
            schema = {k: v for k, v in request["response_schema"].items() if k != "$schema"}
            body = {"model": model, "stream": False, "store": False,
                    "instructions": request["instructions"],
                    "input": canonical(data).decode("utf-8"),
                    "max_output_tokens": config["limits"]["max_output_tokens"],
                    "text": {"format": {"type": "json_schema",
                                        "name": f"world_builder_{request['stage']}", "schema": schema}}}
            if "deepseek_reasoning" in config:
                body["reasoning"] = {"effort": config["deepseek_reasoning"]}
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
            raise AgentError("api.http", _http_error_message(exc, self.key)) from None
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
                reason = choices[0].get("finish_reason") if len(choices) == 1 else None
                if reason not in ("length", "content_filter", "tool_calls",
                                  "insufficient_system_resource", "aborted", "stop"):
                    reason = "unknown"
                reported = body.get("usage")
                usage = None
                if isinstance(reported, dict):
                    prompt = reported.get("prompt_tokens")
                    completion = reported.get("completion_tokens")
                    if type(prompt) is int and prompt >= 0 and type(completion) is int and completion >= 0:
                        usage = {"input_tokens": prompt, "output_tokens": completion}
                raise AgentError("api.incomplete", f"Provider response incomplete (finish_reason={reason})",
                                 details={"finish_reason": reason, "choice_count": len(choices),
                                          "provider_usage": usage})
            message = choices[0]["message"]
            if message.get("refusal") or message.get("tool_calls"):
                raise AgentError("api.refusal", "Provider refused or attempted a tool call")
            content = message["content"]
            if not isinstance(content, str):
                raise AgentError("api.content", "Expected text containing the response JSON")
            raw = content.encode("utf-8")
            input_tokens, output_tokens = body["usage"]["prompt_tokens"], body["usage"]["completion_tokens"]
        elif protocol == "responses":
            usage = body.get("usage")
            if body.get("status") != "completed":
                reason = body.get("incomplete_details")
                reason = reason.get("reason") if isinstance(reason, dict) else None
                if reason not in ("max_output_tokens", "content_filter"):
                    reason = "unknown"
                reported = None
                if isinstance(usage, dict) and type(usage.get("input_tokens")) is int and type(usage.get("output_tokens")) is int:
                    reported = {"input_tokens": usage["input_tokens"], "output_tokens": usage["output_tokens"]}
                raise AgentError("api.incomplete", f"Provider response incomplete (reason={reason})",
                                 details={"reason": reason, "provider_usage": reported})
            output = body["output"]
            if len(output) != 1 or output[0].get("type") != "message" or output[0].get("status") != "completed":
                raise AgentError("api.content", "Expected one completed assistant message")
            parts = output[0]["content"]
            if len(parts) != 1 or parts[0].get("type") != "output_text" or not isinstance(parts[0].get("text"), str):
                raise AgentError("api.content", "Expected one JSON output_text part")
            raw = parts[0]["text"].encode("utf-8")
            input_tokens, output_tokens = usage["input_tokens"], usage["output_tokens"]
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
                raise AgentError(failure["code"], failure["message"], details=failure.get("details"))
            meta = strict_json((path / "completion.json").read_bytes())
            raw = (path / "response.json").read_bytes()
        except OSError as exc:
            raise AgentError("replay.missing", f"No recorded response for {request['stage']}:{request['scope_id']}") from exc
        if saved != request or meta["response_sha256"] != "sha256:" + hashlib.sha256(raw).hexdigest():
            raise AgentError("replay.mismatch", "Recorded request or response hash differs")
        return Completion(raw, meta["model"], meta["input_tokens"], meta["output_tokens"], "replay")
