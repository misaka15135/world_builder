"""The only workbench module that executes the generation pipeline."""
from pathlib import Path

from world_builder.agents.compiler import save_world
from world_builder.agents.contracts import ROOT
from world_builder.agents.providers import APIProvider, FixtureProvider, ReplayProvider
from world_builder.agents.runtime import Supervisor, write_json


def provider_for(mode, config, *, api_key=None, replay_path=None):
    if mode == "adjust":
        return None  # Explicit parameter rebuild, never an API fallback.
    if mode == "fixture":
        return FixtureProvider(ROOT / "examples/agent_scene.responses.json")
    if mode == "replay":
        return ReplayProvider(replay_path)
    return APIProvider(config, api_key=api_key)


def execute(spec, config, provider, output, cancelled, on_phase):
    if spec.get("pipeline") == "nature047":
        from .nature import execute as execute_nature
        return execute_nature(spec, config, provider, output, cancelled, on_phase)
    supervisor = Supervisor(provider, config, output, region_m=spec["region_m"],
                            seed=spec["seed"], cancelled=cancelled)
    try:
        accepted = supervisor.run(spec["prompt"])
        supervisor.checkpoint()
        on_phase("compiling")
        result = save_world(accepted, output, config["limits"],
                            minecraft=spec["minecraft"], unity=spec["unity"])
        # A cancellation after commit must not label a complete world partial.
        result.update(supervisor.usage())
        result["mode"] = spec["mode"]
        write_json(Path(output) / "result.json", result)
        return result
    except Exception as exc:
        result = {"status": "failed", "code": getattr(exc, "code", "execution.error"),
                  "message": str(exc), "feasibility": "unknown", **supervisor.usage()}
        write_json(Path(output) / "result.json", result)
        raise
