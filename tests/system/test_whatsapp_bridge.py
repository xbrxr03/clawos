# SPDX-License-Identifier: AGPL-3.0-or-later
"""
WhatsApp bridge reliability tests for gatewayd and dashd.
"""
import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient


class FakeBus:
    def __init__(self):
        self.events = []
        self.subscribers = []

    def subscribe(self, fn):
        self.subscribers.append(fn)

    def unsubscribe(self, fn):
        if fn in self.subscribers:
            self.subscribers.remove(fn)

    async def publish(self, event_type: str, data: dict | None = None):
        self.events.append({"type": event_type, **(data or {})})


class FakeWA:
    def __init__(self):
        self.sent = []

    def send(self, jid: str, message: str):
        self.sent.append((jid, message))

    def send_self(self, message: str):
        self.sent.append(("self", message))

    def status(self):
        return {"whatsapp": "linked", "phone_number": "+15551234567", "restart_count": 0}


class FakeRouter:
    def __init__(self):
        self.routes = {}

    def is_owner_jid(self, jid: str) -> bool:
        return jid.startswith("1555")

    def get_workspace(self, jid: str) -> str:
        workspace = self.routes.get(jid)
        if not workspace:
            workspace = f"wa_{jid.split('@')[0]}"
            self.routes[jid] = workspace
        return workspace

    def list_routes(self):
        return dict(self.routes)

    def set_workspace(self, jid: str, workspace_id: str):
        self.routes[jid] = workspace_id


def test_gateway_routes_voice_notes_and_handles_approval_reply(monkeypatch):
    from services.gatewayd.approval_bridge import WhatsAppApprovalBridge
    from services.gatewayd.service import GatewayService

    bus = FakeBus()
    wa = FakeWA()
    router = FakeRouter()
    service = GatewayService()
    service._wa = wa
    service._router = router
    service._approval_bridge = WhatsAppApprovalBridge(service._send_self_message)

    class FakeEngine:
        def __init__(self):
            self.decisions = []

        def decide_approval(self, request_id: str, approve: bool) -> bool:
            self.decisions.append((request_id, approve))
            return True

    class FakeManager:
        def __init__(self):
            self.calls = []

        async def chat_direct(self, message: str, workspace_id: str, channel: str, source: str):
            self.calls.append((message, workspace_id, channel, source))
            return f"Reply for {workspace_id}"

    engine = FakeEngine()
    manager = FakeManager()

    monkeypatch.setattr("services.gatewayd.service.get_bus", lambda: bus)
    monkeypatch.setattr("services.gatewayd.approval_bridge.get_engine", lambda: engine, raising=False)
    monkeypatch.setattr("services.policyd.service.get_engine", lambda: engine)
    monkeypatch.setattr("services.agentd.service.get_manager", lambda: manager)
    monkeypatch.setattr(
        "services.gatewayd.media_handler.process_inbound_media",
        lambda media_path: {"kind": "voice_note", "ok": True, "transcript": "summarize the latest trace"},
    )

    asyncio.run(service._approval_bridge.notify_request("req-123456", "shell.restricted", "/tmp/demo", "nexus_default"))
    approval = asyncio.run(service.handle_inbound("15551234567@s.whatsapp.net", "yes"))
    assert approval["status"] == "approval"
    assert engine.decisions == [("req-123456", True)]
    assert any("Approved req-123456" in message for _, message in wa.sent)

    routed = asyncio.run(service.handle_inbound("19995550123@s.whatsapp.net", "", media_path="/tmp/voice.ogg"))
    assert routed["status"] == "routed"
    assert routed["workspace"] == "wa_19995550123"
    assert manager.calls[0][0].endswith("summarize the latest trace")
    assert manager.calls[0][1] == "wa_19995550123"
    assert manager.calls[0][2] == "whatsapp"
    assert manager.calls[0][3] == "19995550123@s.whatsapp.net"
    assert wa.sent[-1] == ("19995550123@s.whatsapp.net", "Reply for wa_19995550123")
    assert bus.events[-1]["workspace"] == "wa_19995550123"


def test_dashd_exposes_gateway_health_and_route_updates(monkeypatch):
    from services.dashd.api import create_app

    class FakeGatewayService:
        def __init__(self):
            self.route_map = {"19995550123@s.whatsapp.net": "wa_19995550123"}

        def health(self):
            return {
                "status": "running",
                "whatsapp": "linked",
                "channels": ["whatsapp"],
                "linked_phone": "+15551234567",
                "routes_count": len(self.route_map),
                "approval_queue": 1,
            }

        def routes(self):
            return dict(self.route_map)

        def set_route(self, jid: str, workspace_id: str):
            self.route_map[jid] = workspace_id
            return self.routes()

    monkeypatch.setattr("services.dashd.api._gateway_service", lambda: FakeGatewayService())
    monkeypatch.setattr("services.dashd.api._collect_models", lambda: [])
    monkeypatch.setattr("services.dashd.api._approval_payloads", lambda: [])
    monkeypatch.setattr("services.dashd.api._collect_service_health", lambda: {"dashd": {"status": "up", "latency_ms": 0}})

    app = create_app({"host": "127.0.0.1", "auth_required": True, "token": "dash-token", "cookie_name": "dash_session"})

    with TestClient(app) as client:
        assert client.post("/api/login", json={"token": "dash-token"}).status_code == 200

        health = client.get("/api/gateway/health")
        assert health.status_code == 200
        assert health.json()["whatsapp"] == "linked"

        routes = client.get("/api/gateway/routes")
        assert routes.status_code == 200
        assert "19995550123@s.whatsapp.net" in routes.json()

        update = client.post(
            "/api/gateway/routes",
            json={"jid": "19995550123@s.whatsapp.net", "workspace_id": "sales_ops"},
        )
        assert update.status_code == 200
        assert update.json()["routes"]["19995550123@s.whatsapp.net"] == "sales_ops"


def test_gateway_routes_owner_messages_through_jarvis(monkeypatch):
    from services.gatewayd.service import GatewayService

    bus = FakeBus()
    wa = FakeWA()
    router = FakeRouter()
    service = GatewayService()
    service._wa = wa
    service._router = router

    class FakeJarvis:
        def __init__(self):
            self.calls = []

        async def chat(self, message: str, *, thread_key: str, source: str, speak_reply: bool | None = None):
            self.calls.append((message, thread_key, source, speak_reply))
            return {"reply": "At once, Sir."}

    class FakeManager:
        def __init__(self):
            self.calls = []

        async def chat_direct(self, message: str, workspace_id: str, channel: str, source: str):
            self.calls.append((message, workspace_id, channel, source))
            return "fallback"

    jarvis = FakeJarvis()
    manager = FakeManager()

    monkeypatch.setattr("services.gatewayd.service.get_bus", lambda: bus)
    monkeypatch.setattr("services.jarvisd.service.get_service", lambda: jarvis)
    monkeypatch.setattr("services.agentd.service.get_manager", lambda: manager)

    routed = asyncio.run(service.handle_inbound("15551234567@s.whatsapp.net", "Status on project Atlas"))

    assert routed["status"] == "routed"
    assert routed["workspace"] == "jarvis_openclaw"
    assert jarvis.calls == [("Status on project Atlas", "whatsapp:15551234567@s.whatsapp.net", "whatsapp", False)]
    assert manager.calls == []
    assert wa.sent[-1] == ("15551234567@s.whatsapp.net", "At once, Sir.")
