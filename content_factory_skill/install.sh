#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# content-factory installer — Pollinations.ai edition
# No ComfyUI, no GPU required for images.
# Installs: system deps, Python packages, Piper TTS + model,
#           factory pipeline, Claw Core + OpenClaw skill.
# Safe to re-run — skips anything already installed.
set -euo pipefail

G="\033[38;5;84m"; R="\033[38;5;203m"; B="\033[38;5;75m"
Y="\033[38;5;220m"; D="\033[2m\033[38;5;245m"; RESET="\033[0m"; BOLD="\033[1m"
ok()   { echo -e "  ${G}✓${RESET}  $1"; }
step() { echo -e "\n  ${B}${BOLD}──${RESET}  $1"; }
warn() { echo -e "  ${Y}!${RESET}  $1"; }
info() { echo -e "  ${D}·  $1${RESET}"; }
die()  { echo -e "\n  ${R}✗${RESET}  $1\n"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FACTORY_DIR="${FACTORY_DIR:-$HOME/factory}"
PIPER_MODEL_DIR="$HOME/.local/share/piper"
CLAW_SKILL_DIR="$HOME/.claw/skills/content-factory"
OC_SKILL_DIR="$HOME/.openclaw/skills/content-factory"

echo ""
echo -e "  ${B}${BOLD}🎬 Content Factory — Installer${RESET}"
echo -e "  ${D}────────────────────────────────${RESET}"
echo ""
info "Factory dir: $FACTORY_DIR"
info "Image gen:   Pollinations.ai (free, online, no GPU needed)"
info "Voice:       Piper TTS (local, offline)"
echo ""

# ── 1. System packages ────────────────────────────────────────────────────────
step "System packages"
sudo apt-get update -qq 2>/dev/null || warn "apt update had errors — continuing"
sudo apt-get install -y -qq ffmpeg python3-pip fonts-dejavu wget git curl \
  2>/dev/null || warn "Some packages failed — continuing"
ok "ffmpeg, git, wget, fonts installed"

# ── 2. Python packages ────────────────────────────────────────────────────────
step "Python packages"
pip3 install -q psutil pathvalidate piper-tts requests pillow \
  google-auth-oauthlib google-api-python-client \
  --break-system-packages 2>/dev/null \
|| pip3 install -q psutil pathvalidate piper-tts requests pillow \
  google-auth-oauthlib google-api-python-client --user 2>/dev/null \
|| warn "Some packages failed"
ok "psutil, pathvalidate, piper-tts, requests, pillow, google-auth installed"

# ── 3. Piper TTS voice model ──────────────────────────────────────────────────
step "Piper TTS voice model"
mkdir -p "$PIPER_MODEL_DIR"
PIPER_MODEL="$PIPER_MODEL_DIR/en_US-lessac-medium.onnx"

if [ ! -f "$PIPER_MODEL" ]; then
  info "Downloading voice model (~60MB)..."
  BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"
  wget -q --show-progress "$BASE/en_US-lessac-medium.onnx" -O "$PIPER_MODEL" 2>&1 \
  || curl -L --progress-bar "$BASE/en_US-lessac-medium.onnx" -o "$PIPER_MODEL" \
  || die "Voice model download failed"
  wget -q "$BASE/en_US-lessac-medium.onnx.json" -O "${PIPER_MODEL}.json" 2>/dev/null || true
  ok "Voice model downloaded"
else
  ok "Voice model already present"
fi

if echo "test" | piper --model "$PIPER_MODEL" --output_file /tmp/piper_verify.wav 2>/dev/null; then
  rm -f /tmp/piper_verify.wav
  ok "Piper TTS verified working"
else
  warn "Piper verification failed — check piper installation"
fi

# ── 4. Factory pipeline ───────────────────────────────────────────────────────
step "Factory pipeline"
if [ -d "$FACTORY_DIR" ]; then
  info "Updating factory at $FACTORY_DIR"
  cp -r "$SCRIPT_DIR/factory/." "$FACTORY_DIR/"
else
  cp -r "$SCRIPT_DIR/factory" "$FACTORY_DIR"
fi

mkdir -p \
  "$FACTORY_DIR/jobs/inbox"     "$FACTORY_DIR/jobs/active" \
  "$FACTORY_DIR/jobs/completed" "$FACTORY_DIR/jobs/failed" \
  "$FACTORY_DIR/artifacts"      "$FACTORY_DIR/logs" \
  "$FACTORY_DIR/state/agents"   "$FACTORY_DIR/state/events" \
  "$FACTORY_DIR/state/leases"   "$FACTORY_DIR/state/metrics" \
  "$FACTORY_DIR/assets/music"

chmod +x "$FACTORY_DIR/start.sh" "$FACTORY_DIR/stop.sh" \
         "$FACTORY_DIR/factoryctl" 2>/dev/null || true

cat > "$FACTORY_DIR/.env" << ENV
FACTORY_ROOT=$FACTORY_DIR
PYTHONPATH=$FACTORY_DIR
OLLAMA_MODEL=qwen2.5:7b
PIPER_BIN=piper
PIPER_MODEL_DIR=$PIPER_MODEL_DIR
PIPER_VOICE=en_US-lessac-medium.onnx
VISUAL_IMAGE_WIDTH=1280
VISUAL_IMAGE_HEIGHT=720
POLLINATIONS_MODEL=flux
POLLINATIONS_TIMEOUT=90
ENV

ok "Factory ready at $FACTORY_DIR"

# ── 5. Skill registration ─────────────────────────────────────────────────────
step "Installing skill"
mkdir -p "$CLAW_SKILL_DIR" "$OC_SKILL_DIR"
for dir in "$CLAW_SKILL_DIR" "$OC_SKILL_DIR"; do
  cp "$SCRIPT_DIR/SKILL.md"          "$dir/SKILL.md"
  cp "$SCRIPT_DIR/youtube_upload.py" "$dir/youtube_upload.py"
  if [ ! -f "$dir/schedule.json" ]; then
    echo '{"upload_time":"09:00","timezone":"local","enabled":false}' \
      > "$dir/schedule.json"
  fi
done
ok "Skill installed → ~/.claw/skills/content-factory/"
ok "Skill installed → ~/.openclaw/skills/content-factory/"

# ── 6. Test suite ─────────────────────────────────────────────────────────────
step "Running tests"
if PYTHONPATH="$FACTORY_DIR" \
   PIPER_MODEL_DIR="$PIPER_MODEL_DIR" \
   python3 "$SCRIPT_DIR/test_factory.py" --quick; then
  ok "All tests passed"
else
  warn "Some tests failed — see output above"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "  ${G}${BOLD}✓  Content Factory installed!${RESET}"
echo ""
echo -e "  ${D}────────────────────────────────${RESET}"
echo ""
echo -e "  ${BOLD}1. Start:${RESET}   ${B}bash ~/factory/start.sh${RESET}"
echo -e "  ${BOLD}2. Submit:${RESET}  ${B}cd ~/factory && python3 factoryctl.py new-job \"Your topic\" --template documentary_video${RESET}"
echo -e "  ${BOLD}3. Watch:${RESET}   ${B}python3 factoryctl.py status${RESET}  or  ${B}http://localhost:7000${RESET}"
echo ""
echo -e "  ${D}YouTube upload (opt-in): tell Jarvis 'youtube setup'${RESET}"
echo ""
