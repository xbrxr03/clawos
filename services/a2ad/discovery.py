"""
mDNS publish + peer discovery via avahi / zeroconf.
Publishes _clawos._tcp.local and scans for other ClawOS nodes on LAN.
"""
import logging
import socket
import threading
import time
from typing import List
from clawos_core.constants import PORT_A2AD, A2A_MDNS_SERVICE, A2A_DISCOVERY_SECS

log = logging.getLogger("a2ad.discovery")

_peers: list[dict] = []
_lock  = threading.Lock()


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_peers() -> list[dict]:
    with _lock:
        return list(_peers)


def _add_peer(peer: dict):
    with _lock:
        existing = [p for p in _peers if p.get("ip") == peer.get("ip")]
        if not existing:
            _peers.append(peer)
            log.info(f"Discovered A2A peer: {peer['ip']}:{peer['port']}")


def start_discovery(interval: int = A2A_DISCOVERY_SECS):
    """Start background thread to discover ClawOS peers via mDNS."""
    def _loop():
        while True:
            _scan()
            time.sleep(interval)
    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    log.info("A2A mDNS discovery started")


def _scan():
    """Scan for _clawos._tcp.local peers using zeroconf if available."""
    try:
        from zeroconf import ServiceBrowser, Zeroconf

        class _Listener:
            def add_service(self, zc, type_, name):
                info = zc.get_service_info(type_, name)
                if info:
                    ip = socket.inet_ntoa(info.addresses[0]) if info.addresses else None
                    if ip:
                        _add_peer({
                            "name": name,
                            "ip":   ip,
                            "port": info.port,
                            "url":  f"http://{ip}:{info.port}/a2a",
                        })
            def remove_service(self, *args): pass
            def update_service(self, *args): pass

        zc = Zeroconf()
        ServiceBrowser(zc, A2A_MDNS_SERVICE + ".", _Listener())
        time.sleep(3)
        zc.close()
    except ImportError:
        log.debug("zeroconf not installed — mDNS discovery unavailable. "
                  "pip install zeroconf to enable.")
    except Exception as e:
        log.debug(f"mDNS scan error: {e}")


def publish(workspace_id: str = "nexus_default"):
    """Publish this node via mDNS."""
    try:
        from zeroconf import ServiceInfo, Zeroconf
        local_ip = get_local_ip()
        hostname = socket.gethostname()
        info = ServiceInfo(
            A2A_MDNS_SERVICE + ".",
            f"clawos-{hostname}.{A2A_MDNS_SERVICE}.",
            addresses=[socket.inet_aton(local_ip)],
            port=PORT_A2AD,
            properties={
                "workspace": workspace_id,
                "version":   "1.0",
            },
        )
        zc = Zeroconf()
        zc.register_service(info)
        log.info(f"A2A mDNS published: {local_ip}:{PORT_A2AD}")
        return zc   # keep reference to keep alive
    except ImportError:
        log.debug("zeroconf not available — mDNS publish skipped")
        return None
    except Exception as e:
        log.warning(f"mDNS publish failed: {e}")
        return None
