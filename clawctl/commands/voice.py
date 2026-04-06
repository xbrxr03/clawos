# SPDX-License-Identifier: AGPL-3.0-or-later
"""clawctl voice — manage voice pipeline."""
import shutil, subprocess
from clawctl.ui.banner import success, error, info


def run_status():
    print()
    piper_ok   = shutil.which("piper") is not None
    try:
        import whisper; whisper_ok = True
    except ImportError:
        whisper_ok = False

    info(f"Whisper (STT): {'✓ installed' if whisper_ok else '✗ missing'}")
    info(f"Piper   (TTS): {'✓ installed' if piper_ok else '✗ missing'}")

    try:
        r = subprocess.run(["arecord", "-l"], capture_output=True, text=True, timeout=3)
        has_mic = "card" in r.stdout.lower()
        info(f"Microphone:    {'✓ detected' if has_mic else '✗ not found'}")
    except Exception:
        info("Microphone:    unknown")

    if not whisper_ok:
        print("\n  Install: pip install openai-whisper --break-system-packages")
    if not piper_ok:
        print("  Install: pip install piper-tts --break-system-packages")
    print()


def run_test():
    print()
    info("Testing TTS (Piper) ...")
    try:
        from clawos_core.constants import VOICE_DIR
        model = VOICE_DIR / "en_US-lessac-medium.onnx"
        if not model.exists():
            error(f"Piper model not found at {model}")
            info("Download: clawctl voice download")
            return
        r = subprocess.run(
            ["piper", "--model", str(model), "--output-raw"],
            input="ClawOS voice system ready.", text=True,
            capture_output=True, timeout=10
        )
        if r.returncode == 0:
            success("TTS working")
        else:
            error(f"TTS error: {r.stderr[:100]}")
    except Exception as e:
        error(f"TTS test failed: {e}")
    print()


def run_enable():
    _set_voice_config(True, "push_to_talk")
    success("Voice enabled (push-to-talk)")
    info("Restart voiced: clawctl restart voiced")


def run_disable():
    _set_voice_config(False, "off")
    success("Voice disabled")
    info("Restart voiced: clawctl restart voiced")


def _set_voice_config(enabled: bool, mode: str):
    from clawos_core.constants import CLAWOS_CONFIG, CONFIG_DIR
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        import yaml
        cfg = {}
        if CLAWOS_CONFIG.exists():
            with open(CLAWOS_CONFIG) as f:
                cfg = yaml.safe_load(f) or {}
        cfg.setdefault("voice", {})["enabled"] = enabled
        cfg.setdefault("voice", {})["mode"]    = mode
        with open(CLAWOS_CONFIG, "w") as f:
            yaml.dump(cfg, f)
    except ImportError:
        pass
