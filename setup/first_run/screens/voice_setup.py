"""Screen 5 — Voice setup."""
import shutil


def _test_tts() -> bool:
    try:
        import subprocess
        from clawos_core.constants import VOICE_DIR
        model = VOICE_DIR / "en_US-lessac-medium.onnx"
        if not model.exists():
            return False
        r = subprocess.run(
            ["piper", "--model", str(model), "--output_raw"],
            input="ClawOS voice test.", text=True,
            capture_output=True, timeout=8
        )
        return r.returncode == 0
    except Exception:
        return False


def run(state) -> bool:
    print("\n  ── Voice Setup ─────────────────────────────────")
    print()

    if not state.has_mic:
        print("  No microphone detected — voice will be disabled.")
        state.voice_enabled = False
        state.voice_mode    = "off"
        state.mark_done("voice_setup")
        return True

    piper_ok   = shutil.which("piper") is not None
    whisper_ok = True
    try:
        import whisper
    except ImportError:
        whisper_ok = False

    if not piper_ok or not whisper_ok:
        print(f"  Voice deps: piper={'✓' if piper_ok else '✗'}  whisper={'✓' if whisper_ok else '✗'}")
        if not piper_ok or not whisper_ok:
            print("  Missing voice dependencies.")
            print("  Install later: pip install openai-whisper piper-tts --break-system-packages")
            ans = input("  Skip voice for now? [Y/n]: ").strip().lower()
            if ans != "n":
                state.voice_enabled = False
                state.voice_mode    = "off"
                state.mark_done("voice_setup")
                return True

    print("  Voice options:")
    print("  [1] Push-to-talk  — hold key to speak  ← recommended")
    print("  [2] Always-on     — wake word 'Hey Claw'")
    print("  [3] Off           — no voice")
    print()
    choice = input("  Choose [1/2/3] or Enter for push-to-talk: ").strip()

    if choice == "2":
        state.voice_mode    = "always_on"
        state.voice_enabled = True
    elif choice == "3":
        state.voice_mode    = "off"
        state.voice_enabled = False
    else:
        state.voice_mode    = "push_to_talk"
        state.voice_enabled = True

    if state.voice_enabled:
        print(f"\n  Voice: {state.voice_mode}")
        print(f"  STT: Whisper {state.profile} model | TTS: Piper lessac-medium")
        print(f"  Audio: {state.ram_gb}GB RAM — {'good' if state.ram_gb >= 12 else 'may be slow'}")

    state.mark_done("voice_setup")
    return True
