"""
Session router — maps WhatsApp JIDs to ClawOS workspaces.
Each contact gets their own isolated workspace by default.
"""
import json
import logging
from pathlib import Path
from clawos_core.constants import CONFIG_DIR, DEFAULT_WORKSPACE

log = logging.getLogger("gatewayd.router")

ROUTES_FILE = CONFIG_DIR / "whatsapp" / "routes.json"


class SessionRouter:
    def __init__(self):
        self._routes: dict[str, str] = {}   # jid → workspace_id
        self._load()

    def _load(self):
        if ROUTES_FILE.exists():
            try:
                self._routes = json.loads(ROUTES_FILE.read_text())
            except Exception:
                self._routes = {}

    def _save(self):
        ROUTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        ROUTES_FILE.write_text(json.dumps(self._routes, indent=2))

    def get_workspace(self, jid: str) -> str:
        """Return workspace for this JID. Creates one if not set."""
        if jid not in self._routes:
            # Default: owner's JID → nexus_default, others → their own
            ws = self._jid_to_workspace(jid)
            self._routes[jid] = ws
            self._save()
        return self._routes[jid]

    def set_workspace(self, jid: str, workspace_id: str):
        self._routes[jid] = workspace_id
        self._save()
        log.info(f"Route set: {jid} → {workspace_id}")

    def _jid_to_workspace(self, jid: str) -> str:
        phone = jid.split("@")[0].replace("+", "")
        return f"wa_{phone}"

    def list_routes(self) -> dict:
        return dict(self._routes)

    def is_owner_jid(self, jid: str) -> bool:
        """
        Check if this JID is the bot's own number messaging itself.
        Owner's messages go to the default workspace.
        """
        from clawos_core.constants import CONFIG_DIR
        linked = CONFIG_DIR / "whatsapp" / ".wa_linked"
        if linked.exists():
            phone = linked.read_text().strip()
            return jid.startswith(phone)
        return False
