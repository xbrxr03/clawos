# SPDX-License-Identifier: AGPL-3.0-or-later
import plistlib

from clawos_core import desktop_integration as di


def test_enable_launch_on_login_writes_linux_autostart(tmp_path, monkeypatch):
    monkeypatch.setattr(di, "is_linux", lambda: True)
    monkeypatch.setattr(di, "is_macos", lambda: False)
    monkeypatch.setattr(di, "linux_autostart_dir", lambda: tmp_path)
    monkeypatch.setenv("CLAWOS_COMMAND_CENTER_CMD", "/usr/bin/clawos-command-center")

    path = di.enable_launch_on_login()

    assert path == tmp_path / "clawos-command-center.desktop"
    assert path.exists()
    assert "Exec=/usr/bin/clawos-command-center" in path.read_text(encoding="utf-8")
    assert di.desktop_posture()["launch_on_login_enabled"] is True
    assert di.disable_launch_on_login() is True
    assert di.launch_on_login_enabled() is False


def test_enable_launch_on_login_writes_macos_launch_agent(tmp_path, monkeypatch):
    monkeypatch.setattr(di, "is_linux", lambda: False)
    monkeypatch.setattr(di, "is_macos", lambda: True)
    monkeypatch.setattr(di, "launch_agents_dir", lambda: tmp_path)
    monkeypatch.setattr(di, "preferred_shell_path_entries", lambda: ["/opt/homebrew/bin", "/usr/bin"])

    path = di.enable_launch_on_login("clawos-command-center --desktop")
    payload = plistlib.load(path.open("rb"))

    assert path == tmp_path / "io.clawos.command-center.plist"
    assert payload["Label"] == "io.clawos.command-center"
    assert payload["ProgramArguments"] == ["/bin/sh", "-lc", "clawos-command-center --desktop"]
    assert payload["EnvironmentVariables"]["PATH"] == "/opt/homebrew/bin:/usr/bin"
    assert di.desktop_posture()["autostart_kind"] == "launchagent"
