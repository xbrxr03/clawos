# SPDX-License-Identifier: AGPL-3.0-or-later
"""clawctl voice - manage Nexus voice behavior."""
from __future__ import annotations

import platform
import shutil
import subprocess

from clawos_core.presence import get_voice_session, set_voice_mode
from services.setupd.state import SetupState

from clawctl.ui.banner import error, info, success


def run_status():
    print()
    piper_ok = shutil.which("piper") is not None
    try:
        import whisper  # type: ignore

        whisper_ok = True
    except ImportError:
        whisper_ok = False

    session = get_voice_session()
    info(f"Voice mode:    {session.get('mode', 'push_to_talk')}")
    info(f"Voice state:   {session.get('state', 'idle')}")
    info(f"Whisper (STT): {'installed' if whisper_ok else 'missing'}")
    info(f"Piper   (TTS): {'installed' if piper_ok else 'missing'}")

    mic_status = "unknown"
    if platform.system() != "Windows":
        probe = ["arecord", "-l"] if platform.system() == "Linux" else ["system_profiler", "SPAudioDataType"]
        try:
            result = subprocess.run(probe, capture_output=True, text=True, timeout=3, check=False)
            output = f"{result.stdout}\n{result.stderr}".lower()
            mic_status = "detected" if any(token in output for token in ["microphone", "input", "card"]) else "not found"
        except Exception:
            mic_status = "unknown"
    info(f"Microphone:    {mic_status}")
    print()


def run_test():
    print()
    info("Testing TTS (Piper) ...")
    try:
        from clawos_core.constants import VOICE_DIR

        model = VOICE_DIR / "en_US-lessac-medium.onnx"
        if not model.exists():
            error(f"Piper model not found at {model}")
            return
        result = subprocess.run(
            ["piper", "--model", str(model), "--output-raw"],
            input="Nexus voice system ready.",
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        if result.returncode == 0:
            success("TTS working")
        else:
            error(f"TTS error: {result.stderr[:100]}")
    except Exception as exc:
        error(f"TTS test failed: {exc}")
    print()


def run_enable():
    run_mode("push_to_talk")


def run_disable():
    run_mode("off")


def run_mode(mode: str = ""):
    print()
    if not mode:
        session = get_voice_session()
        info(f"Voice mode: {session.get('mode', 'push_to_talk')}")
        print()
        return

    try:
        session = set_voice_mode(mode)
    except ValueError as exc:
        error(str(exc))
        print()
        return

    state = SetupState.load()
    state.voice_mode = session.get("mode", mode)
    state.voice_enabled = session.get("mode", mode) != "off"
    state.save()

    success(f"Voice mode set to {session.get('mode', mode)}")
    info("Restart voiced if you want the runtime to pick up the new mode immediately.")
    print()
