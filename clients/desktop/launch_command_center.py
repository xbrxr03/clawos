# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Launch the local ClawOS Command Center in the user's browser.

This keeps the Setup and Command Center experience GUI-first while the
desktop-native shell is still being productized.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

from clawos_core.constants import PORT_DASHD
from services.dashd.api import load_dashboard_settings


def _canonical_local_host(host: str) -> str:
    value = (host or "").strip().lower()
    if value in {"127.0.0.1", "0.0.0.0", "::1", "localhost", ""}:
        return "localhost"
    return host


def dashboard_base_url() -> str:
    try:
        settings = load_dashboard_settings()
        port = int(settings.port)
        host = _canonical_local_host(str(settings.host))
    except Exception:
        port = PORT_DASHD
        host = "localhost"
    return f"http://{host}:{port}"


def command_center_url(route: str = "/") -> str:
    route = route if route.startswith("/") else f"/{route}"
    return f"{dashboard_base_url()}{route}"


def _health_ok(base_url: str) -> bool:
    request = urllib.request.Request(f"{base_url}/api/health", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def wait_for_dashboard(base_url: str, timeout: float = 90.0, interval: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _health_ok(base_url):
            return True
        time.sleep(interval)
    return False


def gui_available() -> bool:
    if sys.platform == "darwin":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def open_in_browser(url: str) -> bool:
    try:
        if webbrowser.open(url, new=1, autoraise=True):
            return True
    except Exception:
        pass

    if shutil.which("gio"):
        try:
            subprocess.Popen(["gio", "open", url])
            return True
        except Exception:
            pass

    if sys.platform == "darwin" and shutil.which("open"):
        try:
            subprocess.Popen(["open", url])
            return True
        except Exception:
            pass

    if shutil.which("xdg-open"):
        try:
            subprocess.Popen(["xdg-open", url])
            return True
        except Exception:
            pass

    if shutil.which("sensible-browser"):
        try:
            subprocess.Popen(["sensible-browser", url])
            return True
        except Exception:
            pass

    return False


def launch(route: str = "/", timeout: float = 90.0, require_gui: bool = True) -> tuple[bool, str]:
    url = command_center_url(route)
    if require_gui and not gui_available():
        return False, "No graphical session detected for the Command Center launcher."
    if not wait_for_dashboard(dashboard_base_url(), timeout=timeout):
        return False, f"ClawOS dashboard did not become ready within {int(timeout)}s."
    if not open_in_browser(url):
        return False, f"ClawOS dashboard is ready at {url}, but no browser launch method succeeded."
    return True, url


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the ClawOS Command Center")
    parser.add_argument("--route", default="/", help="Local route to open, for example /setup")
    parser.add_argument("--timeout", type=float, default=90.0, help="Seconds to wait for dashd")
    parser.add_argument("--allow-headless", action="store_true", help="Skip GUI session checks")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ok, detail = launch(route=args.route, timeout=args.timeout, require_gui=not args.allow_headless)
    if ok:
        print(f"Opened {detail}")
        return 0

    print(detail, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

