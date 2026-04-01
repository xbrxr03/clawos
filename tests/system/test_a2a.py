"""
ClawOS A2A System Tests
========================
Validates A2A service structure, agent card generation, and task models.
Runs without a live HTTP server.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

passed = 0
failed = 0


def ok(label):
    global passed; passed += 1
    print(f"  ✓  {label}")

def fail(label, reason=""):
    global failed; failed += 1
    msg = f"  ✗  {label}"
    if reason: msg += f"  [{reason}]"
    print(msg)


def test_a2a_models_importable():
    try:
        from clawos_core.models import AgentCard, AgentSkill, A2ATask
        ok("AgentCard, AgentSkill, A2ATask importable")
    except Exception as e:
        fail("A2A models importable", str(e))


def test_agent_card_builds():
    try:
        from clawos_core.models import AgentCard, AgentSkill
        card = AgentCard(
            name="test-node",
            description="Test node",
            url="http://localhost:7083/a2a",
            skills=[AgentSkill("chat", "General chat")],
        )
        d = card.to_dict()
        assert "name" in d
        assert "skills" in d
        assert d["metadata"]["offline"] is True
        ok("AgentCard.to_dict() correct structure")
    except Exception as e:
        fail("AgentCard.to_dict()", str(e))


def test_a2a_task_model():
    try:
        from clawos_core.models import A2ATask
        t = A2ATask(intent="do something", workspace="nexus_default")
        d = t.to_dict()
        assert "auth_token" not in d, "auth_token must not be serialized"
        assert "task_id" in d
        ok("A2ATask model (auth_token excluded from serialization)")
    except Exception as e:
        fail("A2ATask model", str(e))


def test_discovery_importable():
    try:
        from services.a2ad.discovery import get_peers, get_local_ip
        ip = get_local_ip()
        assert isinstance(ip, str) and len(ip) > 0
        ok(f"a2ad discovery importable (local_ip={ip})")
    except Exception as e:
        fail("a2ad discovery importable", str(e))


def test_agent_card_builder_importable():
    try:
        from services.a2ad.agent_card import build_card
        ok("a2ad agent_card.build_card importable")
    except Exception as e:
        fail("a2ad agent_card importable", str(e))


def test_task_handler_importable():
    try:
        from services.a2ad.task_handler import handle_task
        ok("a2ad task_handler importable")
    except Exception as e:
        fail("a2ad task_handler importable", str(e))


def test_a2a_constants():
    try:
        from clawos_core.constants import PORT_A2AD, A2A_MDNS_SERVICE
        assert PORT_A2AD == 7083
        assert "_clawos._tcp" in A2A_MDNS_SERVICE
        ok(f"A2A constants correct (port={PORT_A2AD})")
    except Exception as e:
        fail("A2A constants", str(e))


if __name__ == "__main__":
    print("\n  ClawOS — A2A Tests\n  " + "─" * 40)
    test_a2a_models_importable()
    test_agent_card_builds()
    test_a2a_task_model()
    test_discovery_importable()
    test_agent_card_builder_importable()
    test_task_handler_importable()
    test_a2a_constants()
    print(f"\n  {passed} passed  {failed} failed\n")
    sys.exit(0 if failed == 0 else 1)
