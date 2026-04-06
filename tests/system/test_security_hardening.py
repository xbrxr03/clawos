# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Security hardening regression tests.
"""
from __future__ import annotations

import asyncio
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


def test_policy_blocks_private_url_fetches():
    from clawos_core.models import Decision
    from services.policyd.service import PolicyEngine

    engine = PolicyEngine()
    try:
        decision, reason = asyncio.run(
            engine.evaluate(
                "web.fetch",
                "http://127.0.0.1:8080/private",
                task_id="task-1",
                workspace_id="nexus_default",
                granted_tools=["web.fetch"],
            )
        )
        assert decision is Decision.DENY
        assert "blocked" in reason
    finally:
        engine.close()


def test_support_bundle_redacts_sensitive_values(tmp_path, monkeypatch):
    from tools.support import support_bundle as bundle

    config_dir = tmp_path / "config"
    logs_dir = tmp_path / "logs"
    support_dir = tmp_path / "support"
    config_dir.mkdir()
    logs_dir.mkdir()

    clawos_config = config_dir / "clawos.yaml"
    clawos_config.write_text('token: "top-secret"\npassword: "hunter2"\n', encoding="utf-8")
    hardware = config_dir / "hardware.json"
    hardware.write_text(json.dumps({"tier": "B"}), encoding="utf-8")
    setup_state = config_dir / "setup_state.json"
    setup_state.write_text(json.dumps({"logs": ["ready"]}), encoding="utf-8")
    log_file = logs_dir / "app.log"
    log_file.write_text("Authorization: Bearer abc123\nexport API_TOKEN=abc123\n", encoding="utf-8")

    monkeypatch.setattr(bundle, "CLAWOS_CONFIG", clawos_config)
    monkeypatch.setattr(bundle, "HARDWARE_JSON", hardware)
    monkeypatch.setattr(bundle, "SETUP_STATE_JSON", setup_state)
    monkeypatch.setattr(bundle, "LOGS_DIR", logs_dir)
    monkeypatch.setattr(bundle, "SUPPORT_DIR", support_dir)
    monkeypatch.setattr(bundle, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(bundle, "desktop_posture", lambda: {"platform": "linux"})

    archive_path = bundle.create_support_bundle()
    assert archive_path.exists()

    with zipfile.ZipFile(archive_path) as archive:
        config_text = archive.read("config/clawos.yaml").decode("utf-8")
        log_text = archive.read("logs/app.log").decode("utf-8")

    assert "top-secret" not in config_text
    assert "hunter2" not in config_text
    assert "abc123" not in log_text
    assert "[REDACTED]" in config_text
    assert "[REDACTED]" in log_text


def test_secret_env_placement_shell_quotes_values(tmp_path):
    from services.secretd.placer import _place_env

    shell_rc = tmp_path / ".bashrc"
    shell_rc.write_text("# test\n", encoding="utf-8")

    _place_env("api_token", '$(touch /tmp/pwned)', str(shell_rc), "API_TOKEN")
    text = shell_rc.read_text(encoding="utf-8")

    assert "export API_TOKEN='$(touch /tmp/pwned)'" in text


def test_security_sensitive_modules_avoid_shell_true_in_hardened_paths():
    checked = [
        ROOT / "workflows" / "port_scan" / "workflow.py",
        ROOT / "workflows" / "process_report" / "workflow.py",
        ROOT / "openclaw_integration" / "compression.py",
        ROOT / "openclaw_integration" / "installer.py",
    ]
    for path in checked:
        text = path.read_text(encoding="utf-8")
        assert "shell=True" not in text


def test_legacy_entrypoints_avoid_exec_open_and_mktemp():
    legacy_factory = (ROOT / "content_factory_skill" / "factory" / "factory.py").read_text(encoding="utf-8")
    preflight = (ROOT / "content_factory_skill" / "factory" / "preflight.py").read_text(encoding="utf-8")

    assert "exec(open(" not in legacy_factory
    assert "tempfile.mktemp" not in preflight
