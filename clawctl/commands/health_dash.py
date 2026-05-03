# SPDX-License-Identifier: AGPL-3.0-or-later
"""Health dashboard - real-time service status overview."""
import asyncio
import sys
from datetime import datetime

import httpx

import json

from clawos_core.constants import (
    PORT_DASHD, PORT_CLAWD, PORT_AGENTD, PORT_MEMD,
    PORT_POLICYD, PORT_MODELD, PORT_VOICED, PORT_DESKTOPD,
    PORT_REMINDERD, PORT_WAKETRD,
)


SERVICES = [
    ("dashd", PORT_DASHD, "/health"),
    ("clawd", PORT_CLAWD, "/health"),
    ("agentd", PORT_AGENTD, "/health"),
    ("memd", PORT_MEMD, "/health"),
    ("policyd", PORT_POLICYD, "/health"),
    ("modeld", PORT_MODELD, "/health"),
    ("voiced", PORT_VOICED, "/health"),
    ("desktopd", PORT_DESKTOPD, "/health"),
    ("reminderd", PORT_REMINDERD, "/health"),
    ("waketrd", PORT_WAKETRD, "/health"),
]


async def check_service(name: str, port: int, path: str) -> dict:
    """Check a single service health."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"http://127.0.0.1:{port}{path}")
            if r.status_code == 200:
                data = r.json()
                return {
                    "name": name,
                    "port": port,
                    "status": "up",
                    "details": data,
                }
            else:
                return {
                    "name": name,
                    "port": port,
                    "status": f"error ({r.status_code})",
                    "details": None,
                }
    except httpx.ConnectError:
        return {
            "name": name,
            "port": port,
            "status": "down",
            "details": None,
        }
    except (json.JSONDecodeError, ValueError) as e:
        return {
            "name": name,
            "port": port,
            "status": f"error: {e}",
            "details": None,
        }


async def run_dashboard():
    """Run the health dashboard."""
    print("🏥 ClawOS Service Health Dashboard")
    print("=" * 50)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Check all services concurrently
    tasks = [check_service(name, port, path) for name, port, path in SERVICES]
    results = await asyncio.gather(*tasks)
    
    # Count
    up = sum(1 for r in results if r["status"] == "up")
    down = sum(1 for r in results if r["status"] == "down")
    errors = len(results) - up - down
    
    # Print table
    print(f"{'Service':<15} {'Port':<8} {'Status':<15} {'Details'}")
    print("-" * 60)
    
    for r in results:
        name = r["name"]
        port = r["port"]
        status = r["status"]
        
        # Color coding
        if status == "up":
            status_str = "✅ up"
        elif status == "down":
            status_str = "❌ down"
        else:
            status_str = f"⚠️ {status}"
        
        details = ""
        if r["details"]:
            if "version" in r["details"]:
                details = f"v{r['details']['version']}"
            elif "features" in r["details"]:
                feats = r["details"]["features"]
                if isinstance(feats, dict):
                    enabled = [k for k, v in feats.items() if v]
                    details = f"{', '.join(enabled[:3])}"
        
        print(f"{name:<15} {port:<8} {status_str:<15} {details}")
    
    print("-" * 60)
    print(f"\nSummary: {up} up, {down} down, {errors} errors")
    
    if down > 0:
        print("\n💡 Tip: Start services with: clawctl start")
    
    return up == len(results)


def run():
    """Entry point."""
    all_healthy = asyncio.run(run_dashboard())
    sys.exit(0 if all_healthy else 1)
