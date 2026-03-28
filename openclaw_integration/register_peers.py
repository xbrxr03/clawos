"""Register Nexus and RAGd as A2A peers in the running OpenClaw gateway."""
import json
from pathlib import Path

OPENCLAW_DIR = Path.home() / ".openclaw"


def register_peers():
    """Tell OpenClaw about Nexus and RAGd A2A endpoints."""
    peers = [
        {
            "name":         "nexus",
            "agentCardUrl": "http://localhost:7081/.well-known/agent-card.json",
            "description":  "ClawOS local agent — file ops, shell, memory",
        },
        {
            "name":         "ragd",
            "agentCardUrl": "http://localhost:7082/.well-known/agent-card.json",
            "description":  "ClawOS document retrieval — RAG with citations",
        },
    ]
    config_path = OPENCLAW_DIR / "openclaw.json"
    if not config_path.exists():
        print("  openclaw.json not found — skipping peer registration")
        return
    try:
        cfg = json.loads(config_path.read_text())
        cfg.setdefault("a2a", {})["peers"] = peers
        config_path.write_text(json.dumps(cfg, indent=2))
        print("  ✓  Registered Nexus and RAGd as OpenClaw A2A peers")
    except Exception as e:
        print(f"  ✗  Peer registration failed: {e}")


if __name__ == "__main__":
    register_peers()
