# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS Phase 9 System Tests
============================
Validates Phase 9 deliverables: security hardening, A2A endpoints,
capabilityd, voice components, plan mode, dashboard tokens.
"""
import sys
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

passed = 0
failed = 0


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def ok(label: str):
    global passed
    passed += 1
    print(f"  ✓  {label}")


def fail(label: str, reason: str = ""):
    global failed
    failed += 1
    msg = f"  ✗  {label}"
    if reason:
        msg += f"  [{reason}]"
    print(msg)


# ── Security: no shell=True in agent-exposed paths ────────────────────────────
def test_no_shell_true_toolbridge():
    f = read_text(ROOT / "services" / "toolbridge" / "service.py")
    lines_with_shell_true = [
        l for l in f.splitlines()
        if "shell=True" in l and not l.strip().startswith("#")
    ]
    if not lines_with_shell_true:
        ok("toolbridge: no shell=True")
    else:
        fail("toolbridge: shell=True found", str(lines_with_shell_true))


def test_no_shell_true_runner():
    f = read_text(ROOT / "tools" / "shell" / "do" / "runner.py")
    lines = [l for l in f.splitlines() if "shell=True" in l and not l.strip().startswith("#")]
    if not lines:
        ok("do/runner: no shell=True")
    else:
        fail("do/runner: shell=True found", str(lines))


def test_no_shell_true_doctor():
    f = read_text(ROOT / "clawctl" / "commands" / "doctor.py")
    lines = [l for l in f.splitlines() if "shell=True" in l and not l.strip().startswith("#")]
    if not lines:
        ok("doctor: no shell=True")
    else:
        fail("doctor: shell=True found", str(lines))


# ── Security: dashd bound to 127.0.0.1 ───────────────────────────────────────
def test_dashd_localhost():
    f = read_text(ROOT / "services" / "dashd" / "api.py")
    if '0.0.0.0' not in f and '127.0.0.1' in f:
        ok("dashd: bound to 127.0.0.1")
    elif '0.0.0.0' not in f:
        ok("dashd: 0.0.0.0 not present")
    else:
        fail("dashd: still binding to 0.0.0.0")


def test_dashd_bearer_token():
    f = read_text(ROOT / "services" / "dashd" / "api.py")
    if "DASHBOARD_TOKEN" in f and "Bearer" in f:
        ok("dashd: bearer token auth present")
    else:
        fail("dashd: bearer token auth missing")


# ── Security: SQLite WAL mode ─────────────────────────────────────────────────
def test_sqlite_wal_policyd():
    f = read_text(ROOT / "services" / "policyd" / "service.py")
    if "journal_mode=WAL" in f:
        ok("policyd: SQLite WAL mode")
    else:
        fail("policyd: SQLite WAL missing")


def test_sqlite_wal_audit():
    f = read_text(ROOT / "clawos_core" / "logging" / "audit.py")
    if "journal_mode=WAL" in f:
        ok("audit: SQLite WAL mode")
    else:
        fail("audit: SQLite WAL missing")


def test_a2a_ports():
    from clawos_core.constants import A2A_PORT_NEXUS, A2A_PORT_RAGD, PORT_A2AD
    if A2A_PORT_NEXUS == PORT_A2AD == 7083:
        ok("constants: A2A_PORT_NEXUS aliases PORT_A2AD=7083")
    else:
        fail("constants: A2A_PORT_NEXUS wrong", str(A2A_PORT_NEXUS))
    if A2A_PORT_RAGD == 7082:
        ok("constants: A2A_PORT_RAGD=7082")
    else:
        fail("constants: A2A_PORT_RAGD wrong", str(A2A_PORT_RAGD))


# ── config_gen: ctx cap and model list ───────────────────────────────────────
def test_config_gen_no_qwen3():
    from openclaw_integration.config_gen import GOOD_MODELS
    bad = [m for m in GOOD_MODELS if "qwen3" in m]
    if not bad:
        ok("config_gen: qwen3 excluded")
    else:
        fail("config_gen: qwen3 present", str(bad))


def test_config_gen_kimi():
    from openclaw_integration.config_gen import GOOD_MODELS
    if "kimi-k2.5:cloud" in GOOD_MODELS:
        ok("config_gen: kimi-k2.5:cloud present")
    else:
        fail("config_gen: kimi-k2.5:cloud missing")


def test_config_gen_ctx_cap():
    from openclaw_integration.config_gen import CTX_CAP, GOOD_MODELS
    if CTX_CAP == 8192:
        ok(f"config_gen: CTX_CAP=8192")
    else:
        fail("config_gen: CTX_CAP wrong", str(CTX_CAP))
    # Ensure no local model exceeds cap
    for name, m in GOOD_MODELS.items():
        if "cloud" in name:
            continue
        if m["ctx"] > CTX_CAP:
            fail(f"config_gen: {name} ctx={m['ctx']} > CTX_CAP")
            return
    ok("config_gen: all local model ctxs <= CTX_CAP")


# ── sys.exit guard in test files ──────────────────────────────────────────────
def test_sys_exit_guards():
    test_dir = ROOT / "tests" / "system"
    bad = []
    for f in sorted(test_dir.glob("test_phase*.py")):
        if f.name == "test_phase9.py":
            continue
        content = read_text(f)
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "sys.exit" in line:
                # Check if it's inside an if __name__ block
                context = "\n".join(lines[max(0, i-3):i+1])
                if "__main__" not in context:
                    bad.append(f"{f.name}:{i+1}")
    if not bad:
        ok("test files: sys.exit wrapped in __main__ guard")
    else:
        fail("test files: bare sys.exit found", str(bad))


# ── A2A: clawd has A2A server code ────────────────────────────────────────────
def test_clawd_a2a():
    f = read_text(ROOT / "services" / "clawd" / "service.py")
    if "agent-card.json" in f and "/a2a/tasks/send" in f:
        ok("clawd: A2A endpoint present")
    else:
        fail("clawd: A2A endpoint missing")


def test_memd_ragd_a2a():
    f = read_text(ROOT / "services" / "memd" / "service.py")
    if "agent-card.json" in f and "RAGd" in f:
        ok("memd: RAGd A2A endpoint present")
    else:
        fail("memd: RAGd A2A endpoint missing")


# ── OpenClaw skills: RAG skill present ───────────────────────────────────────
def test_rag_skill():
    skill_dir = ROOT / "openclaw_integration" / "skills" / "clawos-rag"
    if (skill_dir / "SKILL.md").exists() and (skill_dir / "rag_query.py").exists():
        ok("clawos-rag skill: SKILL.md + rag_query.py present")
    else:
        fail("clawos-rag skill: missing files")


# ── capability manifests ─────────────────────────────────────────────────────
def test_capability_manifests():
    manifests = list((ROOT / "services").rglob("*.capability.yaml"))
    if len(manifests) >= 3:
        ok(f"capability manifests: {len(manifests)} found")
    else:
        fail("capability manifests: fewer than 3 found", str(manifests))


# ── Voice: wake word and tray ─────────────────────────────────────────────────
def test_wake_word():
    f = ROOT / "services" / "voiced" / "wake.py"
    if f.exists() and "WakeWordDetector" in read_text(f):
        ok("voiced: wake.py present")
    else:
        fail("voiced: wake.py missing")


def test_voice_tray():
    f = ROOT / "services" / "voiced" / "tray.py"
    if f.exists() and "VoiceTray" in read_text(f):
        ok("voiced: tray.py present")
    else:
        fail("voiced: tray.py missing")


def test_talk_mode():
    f = read_text(ROOT / "services" / "voiced" / "service.py")
    if "TALK_MODE_TIMEOUT" in f and "run_voice_session" in f:
        ok("voiced: talk mode present")
    else:
        fail("voiced: talk mode missing")


# ── Plan mode ────────────────────────────────────────────────────────────────
def test_plan_mode_cli():
    f = read_text(ROOT / "nexus" / "cli.py")
    if "_run_plan_mode" in f and '"plan"' in f:
        ok("nexus/cli: plan mode present")
    else:
        fail("nexus/cli: plan mode missing")


def test_plan_mode_repl():
    f = read_text(ROOT / "clients" / "cli" / "repl.py")
    if "/plan" in f:
        ok("repl: /plan slash command present")
    else:
        fail("repl: /plan missing")


# ── GTK4 wizard: intentionally removed in the web-setup migration ──────────
# The legacy GTK wizard and its 10 screens were deleted; the browser-based
# setup flow at http://localhost:7070/setup replaces it.


# ── Nexus Command ─────────────────────────────────────────────────────────────
def test_nexus_command():
    f = ROOT / "dashboard" / "nexus-command" / "serve.py"
    if f.exists() and "openclaw-office" in read_text(f):
        ok("nexus-command: serve.py present")
    else:
        fail("nexus-command: serve.py missing")


def test_nexus_command_cli():
    f = read_text(ROOT / "nexus" / "cli.py")
    if "cmd_command" in f and '"command"' in f:
        ok("nexus/cli: 'command' subcommand present")
    else:
        fail("nexus/cli: 'command' subcommand missing")


# ── ISO build pipeline ────────────────────────────────────────────────────────
def test_iso_chroot():
    f = ROOT / "packaging" / "iso" / "chroot_install.sh"
    content = read_text(f) if f.exists() else ""
    if f.exists() and "dashboard/frontend" in content and "clawos-setup.desktop" in content:
        ok("ISO: chroot_install.sh builds the frontend and wires setup autostart")
    else:
        fail("ISO: chroot_install.sh missing or incomplete")


# ── malformed directory gone ──────────────────────────────────────────────────
def test_no_malformed_dir():
    bad = ROOT / "dashboard" / "{backend,frontend"
    if not bad.exists():
        ok("malformed dashboard dir: cleaned up")
    else:
        fail("malformed dashboard dir: still exists")


# ── modeld: task routing present ─────────────────────────────────────────────
def test_modeld_routing():
    f = read_text(ROOT / "services" / "modeld" / "service.py")
    if "TASK_ROUTING" in f and "classify_task" in f:
        ok("modeld: task-aware routing present")
    else:
        fail("modeld: task routing missing")


# ── Run all tests ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n  ClawOS Phase 9 Tests\n  " + "─"*46)

    tests = [
        test_no_shell_true_toolbridge,
        test_no_shell_true_runner,
        test_no_shell_true_doctor,
        test_dashd_localhost,
        test_dashd_bearer_token,
        test_sqlite_wal_policyd,
        test_sqlite_wal_audit,
        test_a2a_ports,
        test_config_gen_no_qwen3,
        test_config_gen_kimi,
        test_config_gen_ctx_cap,
        test_sys_exit_guards,
        test_clawd_a2a,
        test_memd_ragd_a2a,
        test_rag_skill,
        test_capability_manifests,
        test_wake_word,
        test_voice_tray,
        test_talk_mode,
        test_plan_mode_cli,
        test_plan_mode_repl,
        test_nexus_command,
        test_nexus_command_cli,
        test_iso_chroot,
        test_no_malformed_dir,
        test_modeld_routing,
    ]

    for t in tests:
        try:
            t()
        except Exception as e:
            fail(t.__name__, str(e))

    total = passed + failed
    print(f"\n  {'─'*46}")
    print(f"  {passed}/{total} passed", end="")
    if failed:
        print(f"  |  {failed} FAILED  ←")
    else:
        print("  ✓  all passed")
    print()

    if __name__ == "__main__":
        sys.exit(0 if failed == 0 else 1)
