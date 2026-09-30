"""Desktop resource, lifecycle and persistent configuration boundaries."""
import json
import sys
from urllib.request import urlopen

import pytest

from world_builder.resources import resource_root
from world_builder.agents.contracts import ROOT
from world_builder.agents.providers import load_config
from world_builder.desktop.app import DesktopSession, self_test, user_directory


def test_source_and_frozen_resources(monkeypatch, tmp_path):
    assert (resource_root() / "web/index.html").is_file()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert resource_root() == tmp_path


def test_data_directory_independent_of_current_working_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert user_directory() == tmp_path / "WorldBuilder"


def test_session_serves_and_releases_socket_and_lock(tmp_path):
    session = DesktopSession(tmp_path)
    origin = session.server.origin
    assert json.loads(urlopen(origin + "/api/v1/bootstrap").read())["settings_persistence"] == "application"
    assert not session.active()
    with pytest.raises(RuntimeError):
        DesktopSession(tmp_path)
    session.close(); session.close()
    with pytest.raises(OSError):
        urlopen(origin + "/api/v1/bootstrap", timeout=.2)
    again = DesktopSession(tmp_path); again.close()


def test_preferences_survive_changed_port_and_reject_secret(tmp_path):
    first = DesktopSession(tmp_path)
    try:
        config = load_config(ROOT / "config/agents.example.json")
        config["model"] = "my-saved-model"
        first.service.save_preferences(config)
        config["api_key"] = "never-write-me"
        with pytest.raises(ValueError):
            first.service.save_preferences(config)
        assert "never-write-me" not in (tmp_path / "preferences.json").read_text("utf-8")
    finally:
        first.close()
    second = DesktopSession(tmp_path)
    try:
        assert second.service.config["model"] == "my-saved-model"
    finally:
        second.close()


def test_packaging_self_test_compiles_replays_and_recovers_history(tmp_path):
    session = DesktopSession(tmp_path)
    try:
        self_test(session)
        report = json.loads((tmp_path / "self-test.json").read_text("utf-8"))
        assert report["status"] == "pass"
        assert len(report["runs"]) == 2
        assert report["runs"][0]["result"]["exports"]["unity"]["mesh_count"] == 45
    finally:
        session.close()
    session = DesktopSession(tmp_path)
    try:
        assert len(session.service.list()) == 2
        assert all(j["status"] == "succeeded" for j in session.service.list())
    finally:
        session.close()


def test_invalid_preferences_release_lock(tmp_path):
    (tmp_path / "preferences.json").write_text('{}')
    with pytest.raises(ValueError):
        DesktopSession(tmp_path)
    config = load_config(ROOT / "config/agents.example.json")
    (tmp_path / "preferences.json").write_text(json.dumps(config))
    session = DesktopSession(tmp_path); session.close()
