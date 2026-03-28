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
    f = (ROOT / "services" / "toolbridge" / "service.py").read_text()
    lines_with_shell_true = [
        l for l in f.splitlines()
        if "shell=True" in l and not l.strip().startswith("#")
    ]
    if not lines_with_shell_true:
        ok("toolbridge: no shell=True")
    else:
        fail("toolbridge: shell=True found", str(lines_with_shell_true))


def test_no_shell_true_runner():
    f = (ROOT / "tools" / "shell" / "do" / "runner.py").read_text()
    lines = [l for l in f.splitlines() if "shell=True" in l and not l.strip().startswith("#")]
    if not lines:
        ok("do/runner: no shell=True")
    else:
        fail("do/runner: shell=True found", str(lines))


def test_no_shell_true_doctor():
    f = (ROOT / "clawctl" / "commands" / "doctor.py").read_text()
    lines = [l for l in f.splitlines() if "shell=True" in l and not l.strip().startswith("#")]
    if not lines:
        ok("doctor: no shell=True")
    else:
        fail("doctor: shell=True found", str(lines))


# ── Security: dashd bound to 127.0.0.1 ───────────────────────────────────────
def test_dashd_localhost():
    f = (ROOT / "services" / "dashd" / "api.py").read_text()
    if '0.0.0.0' not in f and '127.0.0.1' in f:
        ok("dashd: bound to 127.0.0.1")
    elif '0.0.0.0' not in f:
        ok("dashd: 0.0.0.0 not present")
    else:
        fail("dashd: still binding to 0.0.0.0")


def test_dashd_bearer_token():
    f = (ROOT / "services" / "dashd" / "api.py").read_text()
    if "DASHBOARD_TOKEN" in f and "Bearer" in f:
        ok("dashd: bearer token auth present")
    else:
        fail("dashd: bearer token auth missing")


# ── Security: SQLite WAL mode ─────────────────────────────────────────────────
def test_sqlite_wal_policyd():
    f = (ROOT / "services" / "policyd" / "service.py").read_text()
    if "journal_mode=WAL" in f:
        ok("policyd: SQLite WAL mode")
    else:
        fail("policyd: SQLite WAL missing")


def test_sqlite_wal_audit():
    f = (ROOT / "clawos_core" / "logging" / "audit.py").read_text()
    if "journal_mode=WAL" in f:
        ok("audit: SQLite WAL mode")
    else:
        fail("audit: SQLite WAL missing")


# ── Port: gatewayd moved to 18789 ────────────────────────────────────────────
def test_port_gatewayd():
    from clawos_core.constants import PORT_GATEWAYD
    if PORT_GATEWAYD == 18789:
        ok("constants: PORT_GATEWAYD=18789")
    else:
        fail("constants: PORT_GATEWAYD wrong", str(PORT_GATEWAYD))


def test_a2a_ports():
    from clawos_core.constants import A2A_PORT_NEXUS, A2A_PORT_RAGD
    if A2A_PORT_NEXUS == 7081:
        ok("constants: A2A_PORT_NEXUS=7081")
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
        content = f.read_text()
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
    f = (ROOT / "services" / "clawd" / "service.py").read_text()
    if "agent-card.json" in f and "/a2a/tasks/send" in f:
        ok("clawd: A2A endpoint present")
    else:
        fail("clawd: A2A endpoint missing")


def test_memd_ragd_a2a():
    f = (ROOT / "services" / "memd" / "service.py").read_text()
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


# ── capabilityd: service and manifests ───────────────────────────────────────
def test_capabilityd_service():
    f = ROOT / "services" / "capabilityd" / "service.py"
    if f.exists() and "CapabilityGraph" in f.read_text():
        ok("capabilityd: service.py present")
    else:
        fail("capabilityd: service.py missing")


def test_capability_manifests():
    manifests = list((ROOT / "services").rglob("*.capability.yaml"))
    if len(manifests) >= 3:
        ok(f"capability manifests: {len(manifests)} found")
    else:
        fail("capability manifests: fewer than 3 found", str(manifests))


# ── Voice: wake word and tray ─────────────────────────────────────────────────
def test_wake_word():
    f = ROOT / "services" / "voiced" / "wake.py"
    if f.exists() and "WakeWordDetector" in f.read_text():
        ok("voiced: wake.py present")
    else:
        fail("voiced: wake.py missing")


def test_voice_tray():
    f = ROOT / "services" / "voiced" / "tray.py"
    if f.exists() and "VoiceTray" in f.read_text():
        ok("voiced: tray.py present")
    else:
        fail("voiced: tray.py missing")


def test_talk_mode():
    f = (ROOT / "services" / "voiced" / "service.py").read_text()
    if "TALK_MODE_TIMEOUT" in f and "run_voice_session" in f:
        ok("voiced: talk mode present")
    else:
        fail("voiced: talk mode missing")


# ── Plan mode ────────────────────────────────────────────────────────────────
def test_plan_mode_cli():
    f = (ROOT / "nexus" / "cli.py").read_text()
    if "_run_plan_mode" in f and '"plan"' in f:
        ok("nexus/cli: plan mode present")
    else:
        fail("nexus/cli: plan mode missing")


def test_plan_mode_repl():
    f = (ROOT / "clients" / "cli" / "repl.py").read_text()
    if "/plan" in f:
        ok("repl: /plan slash command present")
    else:
        fail("repl: /plan missing")


# ── GTK4 wizard ──────────────────────────────────────────────────────────────
def test_gtk_wizard():
    f = ROOT / "setup" / "first_run" / "gtk_wizard.py"
    if f.exists():
        content = f.read_text()
        screens = ["welcome", "hardware", "edition", "model",
                   "workspace", "voice", "openclaw", "review", "install", "complete"]
        missing = [s for s in screens if f"_screen_{s}" not in content]
        if not missing:
            ok("gtk_wizard: all 10 screens present")
        else:
            fail("gtk_wizard: screens missing", str(missing))
    else:
        fail("gtk_wizard: file missing")


# ── Nexus Command ─────────────────────────────────────────────────────────────
def test_nexus_command():
    f = ROOT / "dashboard" / "nexus-command" / "serve.py"
    if f.exists() and "openclaw-office" in f.read_text():
        ok("nexus-command: serve.py present")
    else:
        fail("nexus-command: serve.py missing")


def test_nexus_command_cli():
    f = (ROOT / "nexus" / "cli.py").read_text()
    if "cmd_command" in f and '"command"' in f:
        ok("nexus/cli: 'command' subcommand present")
    else:
        fail("nexus/cli: 'command' subcommand missing")


# ── ISO build pipeline ────────────────────────────────────────────────────────
def test_iso_chroot():
    f = ROOT / "packaging" / "iso" / "chroot_install.sh"
    if f.exists() and "gtk_wizard" in f.read_text():
        ok("ISO: chroot_install.sh present with wizard reference")
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
    f = (ROOT / "services" / "modeld" / "service.py").read_text()
    if "TASK_ROUTING" in f and "classify_task" in f:
        ok("modeld: task-aware routing present")
    else:
        fail("modeld: task routing missing")


# ── gatewayd: WhatsApp wired ──────────────────────────────────────────────────
def test_gatewayd_whatsapp():
    f = (ROOT / "services" / "gatewayd" / "service.py").read_text()
    if "WhatsAppChannel" in f and "on_message" in f:
        ok("gatewayd: WhatsApp channel wired")
    else:
        fail("gatewayd: WhatsApp channel not wired")


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
        test_port_gatewayd,
        test_a2a_ports,
        test_config_gen_no_qwen3,
        test_config_gen_kimi,
        test_config_gen_ctx_cap,
        test_sys_exit_guards,
        test_clawd_a2a,
        test_memd_ragd_a2a,
        test_rag_skill,
        test_capabilityd_service,
        test_capability_manifests,
        test_wake_word,
        test_voice_tray,
        test_talk_mode,
        test_plan_mode_cli,
        test_plan_mode_repl,
        test_gtk_wizard,
        test_nexus_command,
        test_nexus_command_cli,
        test_iso_chroot,
        test_no_malformed_dir,
        test_modeld_routing,
        test_gatewayd_whatsapp,
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
