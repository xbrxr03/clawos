# SPDX-License-Identifier: AGPL-3.0-or-later
import plistlib
from pathlib import Path

from clawos_core import platform as platform_mod
from clawos_core import service_manager as sm


def test_blocked_paths_include_macos_sensitive_dirs(monkeypatch):
    monkeypatch.setattr(platform_mod, "is_macos", lambda: True)
    blocked = platform_mod.blocked_paths()
    assert any("Library" in path and "Keychains" in path for path in blocked)
    assert "/Library/Keychains" in blocked


def test_preferred_shell_path_entries_include_homebrew(monkeypatch):
    monkeypatch.setattr(platform_mod, "is_macos", lambda: True)
    monkeypatch.setattr(platform_mod, "homebrew_prefix", lambda: Path("/opt/homebrew"))
    monkeypatch.setenv("PATH", "/usr/bin")
    entries = platform_mod.preferred_shell_path_entries()
    assert str(Path("/opt/homebrew/bin")) in entries
    assert str(Path("/opt/homebrew/sbin")) in entries
    assert "/usr/bin" in entries


def test_service_hint_uses_launchd_paths(monkeypatch):
    monkeypatch.setattr(sm, "service_manager_name", lambda: "launchd")
    monkeypatch.setattr(sm, "user_domain_target", lambda: "gui/501")
    monkeypatch.setattr(sm, "launch_agent_path", lambda service: Path("/tmp") / f"{service}.plist")

    assert sm.service_hint("start", "clawos.service") == "launchctl bootstrap gui/501 /tmp/clawos.service.plist"
    assert sm.service_hint("stop", "clawos.service") == "launchctl bootout gui/501 /tmp/clawos.service.plist"
    assert sm.service_hint("restart", "clawos.service") == "launchctl kickstart -k gui/501/io.clawos.daemon"
    assert sm.service_hint("status", "clawos.service") == "launchctl print gui/501/io.clawos.daemon"


def test_service_hint_uses_systemd(monkeypatch):
    monkeypatch.setattr(sm, "service_manager_name", lambda: "systemd")
    assert sm.service_hint("restart", "clawos.service") == "systemctl --user restart clawos.service"


def test_install_launch_agents_writes_expected_plists(tmp_path, monkeypatch):
    agents_dir = tmp_path / "LaunchAgents"
    logs_dir = tmp_path / "logs"
    monkeypatch.setattr(sm, "launch_agents_dir", lambda: agents_dir)
    monkeypatch.setattr(sm, "LOGS_DIR", logs_dir)
    monkeypatch.setattr(sm, "preferred_shell_path_entries", lambda: ["/opt/homebrew/bin", "/usr/local/bin"])
    monkeypatch.setenv("CLAWOS_DIR", str(tmp_path / "clawos-home"))

    created = sm.install_launch_agents(
        project_root=tmp_path / "repo",
        workspace="demo",
        python_bin="/usr/bin/python3",
        ollama_bin="/opt/homebrew/bin/ollama",
    )

    assert len(created) == 2
    daemon_plist = plistlib.load((agents_dir / "io.clawos.daemon.plist").open("rb"))
    ollama_plist = plistlib.load((agents_dir / "io.clawos.ollama.plist").open("rb"))

    assert daemon_plist["Label"] == "io.clawos.daemon"
    assert daemon_plist["ProgramArguments"][-1] == "demo"
    assert daemon_plist["EnvironmentVariables"]["PYTHONPATH"] == str(tmp_path / "repo")
    assert ollama_plist["ProgramArguments"] == ["/opt/homebrew/bin/ollama", "serve"]


def test_log_files_for_launchd(monkeypatch, tmp_path):
    monkeypatch.setattr(sm, "service_manager_name", lambda: "launchd")
    monkeypatch.setattr(sm, "LOGS_DIR", tmp_path)
    assert sm.log_files_for("clawos.service") == [tmp_path / "clawos.stdout.log", tmp_path / "clawos.stderr.log"]
    assert sm.log_files_for("ollama.service") == [tmp_path / "ollama.stdout.log", tmp_path / "ollama.stderr.log"]
