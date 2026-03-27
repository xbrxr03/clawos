"""Write initial permissions/policy config for a workspace."""
import json
from pathlib import Path
from clawos_core.constants import CONFIG_DIR

DEFAULT_POLICY = {
    "mode": "recommended",
    "version": "0.1.0",
    "workspaces": {
        "nexus_default": {
            "granted_tools": [
                "fs.read", "fs.write", "fs.list", "fs.search",
                "web.search", "web.fetch",
                "memory.read", "memory.write",
                "system.info", "workspace.inspect", "workspace.create",
            ],
            "blocked_paths": ["/etc/shadow", "/etc/passwd", "/.ssh/"],
            "require_approval": ["fs.delete", "shell.restricted", "web.download"],
        }
    },
    "global": {
        "approval_timeout_s": 120,
        "audit_enabled": True,
        "merkle_chain": True,
    }
}

DEVELOPER_EXTRAS = ["shell.restricted", "shell.elevated", "api.external"]


def write(mode: str = "recommended", workspace_id: str = "nexus_default"):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    policy = dict(DEFAULT_POLICY)
    policy["mode"] = mode
    if mode == "developer":
        ws = policy["workspaces"].get(workspace_id, {})
        ws.setdefault("granted_tools", []).extend(DEVELOPER_EXTRAS)
    path = CONFIG_DIR / "policy.json"
    path.write_text(json.dumps(policy, indent=2))
    return path


def load() -> dict:
    path = CONFIG_DIR / "policy.json"
    if path.exists():
        return json.loads(path.read_text())
    return DEFAULT_POLICY
