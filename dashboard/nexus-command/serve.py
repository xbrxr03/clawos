# SPDX-License-Identifier: AGPL-3.0-or-later
"""Serve openclaw-office rebranded as Nexus Command."""
import os
import subprocess
import sys
from pathlib import Path


def serve(port: int = 5180):
    """Launch openclaw-office pointed at ClawOS gateway."""
    env = os.environ.copy()
    env["VITE_GATEWAY_URL"] = "ws://localhost:18789"

    # Try to read OpenClaw gateway token
    try:
        r = subprocess.run(
            ["openclaw", "config", "get", "gateway.auth.token"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            env["VITE_GATEWAY_TOKEN"] = r.stdout.strip()
    except Exception:
        pass

    # Disable device auth for web client
    try:
        subprocess.run(
            ["openclaw", "config", "set",
             "gateway.controlUi.dangerouslyDisableDeviceAuth", "true"],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass

    print(f"  Starting Nexus Command on http://localhost:{port}")
    print(f"  Gateway: ws://localhost:18789")
    print(f"  Press Ctrl+C to stop.\n")

    try:
        subprocess.run(
            ["npx", "@ww-ai-lab/openclaw-office",
             "--port", str(port), "--host", "127.0.0.1"],
            env=env,
        )
    except FileNotFoundError:
        print("  ✗  npx not found. Install Node.js to use Nexus Command.")
        print("     Install: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n  Nexus Command stopped.")


if __name__ == "__main__":
    serve()
