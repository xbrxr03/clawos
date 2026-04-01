"""clawctl a2a — A2A peer management and task delegation."""
from clawctl.ui.banner import success, error, info, table


def run_peers():
    """List discovered ClawOS A2A nodes on LAN."""
    print()
    try:
        from services.a2ad.discovery import get_peers
        peers = get_peers()
        if not peers:
            info("No A2A peers discovered on LAN. Ensure a2ad is running and other ClawOS nodes are present.")
            return
        rows = [(p.get("name", "?"), p.get("ip", "?"),
                 str(p.get("port", "?")), p.get("url", "?")) for p in peers]
        table(rows, headers=("name", "ip", "port", "url"))
    except Exception as e:
        error(f"A2A peer discovery unavailable: {e}")
    print()


def run_card():
    """Print this node's A2A Agent Card JSON."""
    import json
    try:
        from services.a2ad.agent_card import build_card
        from services.a2ad.discovery import get_local_ip
        card = build_card(local_ip=get_local_ip())
        print(json.dumps(card.to_dict(), indent=2))
    except Exception as e:
        error(f"Could not build Agent Card: {e}")


def run_delegate(task: str, peer_ip: str, workspace: str = "nexus_default"):
    """Send a task to a remote ClawOS A2A node."""
    import asyncio
    print()
    info(f"Delegating to {peer_ip}: {task[:60]}")
    try:
        from services.gatewayd.service import delegate_to_peer
        result = asyncio.run(delegate_to_peer(
            f"http://{peer_ip}:7083/a2a", task, workspace
        ))
        success("Result:")
        print(f"\n  {result}\n")
    except Exception as e:
        error(f"Delegation failed: {e}")
    print()


def run_status():
    """Show A2A service status."""
    from services.a2ad.health import check
    h = check()
    if h["status"] == "ok":
        success(f"a2ad running on port {h.get('port', 7083)}")
    else:
        error("a2ad not running  (clawctl start)")
