# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Platform helpers for ClawOS.
Centralizes OS checks and lightweight system probing so runtime code
does not need to special-case Linux and macOS in every module.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path


def platform_key() -> str:
    return platform.system().lower()


def is_linux() -> bool:
    return platform_key() == "linux"


def is_macos() -> bool:
    return platform_key() == "darwin"


def is_windows() -> bool:
    return platform_key() == "windows"


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def homebrew_prefix() -> Path:
    arch = platform.machine().lower()
    if arch in ("arm64", "aarch64"):
        return Path("/opt/homebrew")
    return Path("/usr/local")


def preferred_shell_path_entries() -> list[str]:
    entries = []
    if is_macos():
        hb = homebrew_prefix()
        entries.extend([
            str(hb / "bin"),
            str(hb / "sbin"),
        ])
    entries.extend([
        str(Path.home() / ".local" / "bin"),
        os.environ.get("PATH", ""),
    ])
    return [entry for entry in entries if entry]


def launch_agents_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def blocked_paths() -> list[str]:
    paths = [
        "/etc/passwd",
        "/etc/shadow",
        "/etc/sudoers",
        "/.ssh/",
        "/proc/",
        "/sys/",
    ]
    if is_macos():
        paths.extend([
            str(Path.home() / "Library" / "Keychains"),
            str(Path.home() / "Library" / "Mail"),
            str(Path.home() / "Library" / "Messages"),
            "/Library/Keychains",
            "/System/Volumes/Data/private/var/db",
        ])
    return paths


def _run_text(cmd: list[str], timeout: int = 5) -> str:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout.strip()


def ram_snapshot_gb() -> dict[str, float]:
    if is_linux():
        try:
            with open("/proc/meminfo", encoding="utf-8") as handle:
                meminfo = {
                    line.split()[0].rstrip(":"): int(line.split()[1])
                    for line in handle
                    if line.split()[0].rstrip(":") in ("MemTotal", "MemAvailable")
                }
            total = round(meminfo["MemTotal"] * 1024 / 1e9, 1)
            free = round(meminfo["MemAvailable"] * 1024 / 1e9, 1)
            used = round(total - free, 1)
            return {"total_gb": total, "free_gb": free, "used_gb": used}
        except (OSError, PermissionError):
            pass

    if is_macos():
        try:
            total_bytes = int(_run_text(["sysctl", "-n", "hw.memsize"]))
            vm_stat = _run_text(["vm_stat"])
            page_size = 4096
            page_match = re.search(r"page size of (\d+) bytes", vm_stat)
            if page_match:
                page_size = int(page_match.group(1))

            page_counts: dict[str, int] = {}
            for line in vm_stat.splitlines():
                match = re.match(r"(.+):\s+([\d.]+)\.", line.strip())
                if match:
                    page_counts[match.group(1)] = int(float(match.group(2)))

            free_pages = (
                page_counts.get("Pages free", 0)
                + page_counts.get("Pages speculative", 0)
                + page_counts.get("Pages inactive", 0)
            )
            free_bytes = free_pages * page_size
            total = round(total_bytes / 1e9, 1)
            free = round(free_bytes / 1e9, 1)
            used = round(max(total_bytes - free_bytes, 0) / 1e9, 1)
            return {"total_gb": total, "free_gb": free, "used_gb": used}
        except (OSError, subprocess.SubprocessError):
            pass

    if is_windows():
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total = round(stat.ullTotalPhys / 1e9, 1)
                free = round(stat.ullAvailPhys / 1e9, 1)
                used = round((stat.ullTotalPhys - stat.ullAvailPhys) / 1e9, 1)
                return {"total_gb": total, "free_gb": free, "used_gb": used}
        except (ImportError, ModuleNotFoundError):
            pass
            pass

    return {"total_gb": 0.0, "free_gb": 0.0, "used_gb": 0.0}


def disk_snapshot_gb(path: str | Path = "/") -> dict[str, float]:
    usage = shutil.disk_usage(str(path))
    return {
        "total_gb": round(usage.total / 1e9, 1),
        "used_gb": round(usage.used / 1e9, 1),
        "free_gb": round(usage.free / 1e9, 1),
        "used_pct": round((usage.used / usage.total) * 100, 1) if usage.total else 0.0,
    }


def load_snapshot() -> dict[str, float]:
    try:
        one, five, fifteen = os.getloadavg()
        return {
            "load_1m": round(one, 2),
            "load_5m": round(five, 2),
            "load_15m": round(fifteen, 2),
        }
    except (OSError, RuntimeError, AttributeError):
        return {}


def gpu_info() -> tuple[str, float]:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0 and result.stdout.strip():
            name, memory_mb = [part.strip() for part in result.stdout.split(",", 1)]
            return name, round(int(memory_mb) / 1024, 1)
    except (subprocess.SubprocessError, OSError):
        pass

    if is_macos():
        try:
            raw = _run_text(["system_profiler", "SPDisplaysDataType", "-json"], timeout=10)
            data = json.loads(raw)
            devices = data.get("SPDisplaysDataType", [])
            if devices:
                device = devices[0]
                name = (
                    device.get("sppci_model")
                    or device.get("_name")
                    or device.get("spdisplays_vendor")
                    or "Apple GPU"
                )
                vram_text = device.get("spdisplays_vram") or device.get("spdisplays_vram_shared") or ""
                match = re.search(r"(\d+)\s*MB", str(vram_text))
                if match:
                    return name, round(int(match.group(1)) / 1024, 1)
                return name, 0.0
        except (json.JSONDecodeError, ValueError):
            pass
            pass

    return "none", 0.0


def audio_info() -> tuple[bool, int, int]:
    if command_exists("arecord"):
        try:
            result = subprocess.run(["arecord", "-l"], capture_output=True, text=True, timeout=3)
            if "card" in result.stdout.lower():
                cards = re.findall(r"card (\d+):", result.stdout)
                return True, 44100, int(cards[0]) if cards else 0
        except (subprocess.SubprocessError, OSError):
            pass
            pass

    if is_macos():
        try:
            raw = _run_text(["system_profiler", "SPAudioDataType"], timeout=10)
            if raw:
                return True, 44100, 0
        except (OSError, RuntimeError):
            pass

    return True, 44100, 0

