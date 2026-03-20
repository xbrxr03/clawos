#!/bin/bash
# content-factory — ClawOS skill installer
# Installs the full automated YouTube documentary pipeline.
#
# Usage: bash install.sh
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
CLAW_SKILL_DIR="$HOME/.claw/skills/content-factory"
OC_SKILL_DIR="$HOME/.openclaw/skills/content-factory"

echo ""
echo -e "  ${B}${BOLD}🎬 Content Factory — ClawOS Skill Installer${RESET}"
echo -e "  ${D}────────────────────────────────────────────${RESET}"
echo ""

# ── 1. System dependencies ────────────────────────────────────────────────────
step "System dependencies"

sudo apt-get install -y -qq \
  ffmpeg \
  python3-pip \
  fonts-dejavu \
  wget \
  2>/dev/null || warn "apt install had errors — continuing"
ok "System deps installed"

# ── 2. Python packages (ALL required) ────────────────────────────────────────
step "Python packages"

pip3 install -q \
  psutil \
  pathvalidate \
  piper-tts \
  requests \
  pillow \
  google-auth-oauthlib \
  google-api-python-client \
  --break-system-packages 2>/dev/null \
|| pip3 install -q \
  psutil \
  pathvalidate \
  piper-tts \
  requests \
  pillow \
  google-auth-oauthlib \
  google-api-python-client \
  --user 2>/dev/null \
|| warn "Some Python packages failed"
ok "Python packages installed (psutil, pathvalidate, piper-tts, requests, pillow, google)"

# ── 3. Piper voice model ──────────────────────────────────────────────────────
step "Piper TTS voice model"

PIPER_MODEL_DIR="$HOME/.local/share/piper"
mkdir -p "$PIPER_MODEL_DIR"
PIPER_MODEL="$PIPER_MODEL_DIR/en_US-lessac-medium.onnx"

if [ ! -f "$PIPER_MODEL" ]; then
  info "Downloading voice model (~60MB)..."
  BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"
  wget -q "$BASE/en_US-lessac-medium.onnx"      -O "$PIPER_MODEL" 2>/dev/null \
  || curl -sL "$BASE/en_US-lessac-medium.onnx"  -o "$PIPER_MODEL" \
  || warn "Voice model download failed — run manually later"
  wget -q "$BASE/en_US-lessac-medium.onnx.json" -O "${PIPER_MODEL}.json" 2>/dev/null || true
  ok "Voice model downloaded"
else
  ok "Voice model already present"
fi

# Verify piper works
if piper --model "$PIPER_MODEL" --output_file /tmp/piper_test.wav <<< "test" 2>/dev/null; then
  rm -f /tmp/piper_test.wav
  ok "Piper TTS verified working"
else
  warn "Piper test failed — check installation"
fi

# ── 4. Install factory ────────────────────────────────────────────────────────
step "Installing factory pipeline"

if [ -d "$FACTORY_DIR" ]; then
  info "Factory exists at $FACTORY_DIR — updating files"
  cp -r "$SCRIPT_DIR/factory/." "$FACTORY_DIR/"
  ok "Factory updated"
else
  cp -r "$SCRIPT_DIR/factory" "$FACTORY_DIR"
  ok "Factory installed to $FACTORY_DIR"
fi

# Ensure all dirs exist
mkdir -p \
  "$FACTORY_DIR/jobs/inbox"     \
  "$FACTORY_DIR/jobs/active"    \
  "$FACTORY_DIR/jobs/completed" \
  "$FACTORY_DIR/jobs/failed"    \
  "$FACTORY_DIR/artifacts"      \
  "$FACTORY_DIR/logs"           \
  "$FACTORY_DIR/state/agents"   \
  "$FACTORY_DIR/state/events"   \
  "$FACTORY_DIR/state/leases"   \
  "$FACTORY_DIR/state/metrics"  \
  "$FACTORY_DIR/assets/music"

chmod +x "$FACTORY_DIR/start.sh" "$FACTORY_DIR/stop.sh" \
         "$FACTORY_DIR/factoryctl" 2>/dev/null || true

# Write .env with correct paths
cat > "$FACTORY_DIR/.env" << ENV
FACTORY_ROOT=$FACTORY_DIR
PYTHONPATH=$FACTORY_DIR
OLLAMA_MODEL=qwen2.5:7b
PIPER_MODEL_DIR=$HOME/.local/share/piper
PIPER_VOICE=en_US-lessac-medium.onnx
COMFYUI_DIR=
ENV
ok "Factory ready at $FACTORY_DIR"

# ── 5. Install skill for Claw Core ───────────────────────────────────────────
step "Installing skill (Claw Core + OpenClaw)"

mkdir -p "$CLAW_SKILL_DIR" "$OC_SKILL_DIR"
cp "$SCRIPT_DIR/SKILL.md"          "$CLAW_SKILL_DIR/SKILL.md"
cp "$SCRIPT_DIR/youtube_upload.py" "$CLAW_SKILL_DIR/youtube_upload.py"
cp "$SCRIPT_DIR/SKILL.md"          "$OC_SKILL_DIR/SKILL.md"
cp "$SCRIPT_DIR/youtube_upload.py" "$OC_SKILL_DIR/youtube_upload.py"

for dir in "$CLAW_SKILL_DIR" "$OC_SKILL_DIR"; do
  if [ ! -f "$dir/schedule.json" ]; then
    echo '{"upload_time": "09:00", "timezone": "local"}' > "$dir/schedule.json"
  fi
done

ok "Skill installed for Claw Core (~/.claw/skills/content-factory/)"
ok "Skill installed for OpenClaw (~/.openclaw/skills/content-factory/)"

# ── 6. Background music dir ───────────────────────────────────────────────────
step "Assets"
mkdir -p "$FACTORY_DIR/assets/music"
info "Drop royalty-free .mp3 files in: $FACTORY_DIR/assets/music/"
info "Recommended source: pixabay.com/music (free, no attribution needed)"
ok "Assets directory ready"

# ── 7. Run test suite ────────────────────────────────────────────────────────
step "Running preflight tests"

if PYTHONPATH="$FACTORY_DIR" python3 "$SCRIPT_DIR/test_factory.py" --quick 2>/dev/null; then
  ok "All preflight tests passed"
else
  warn "Some tests failed — check output above"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "  ${G}${BOLD}✓  Content Factory installed!${RESET}"
echo ""
echo -e "  ${D}────────────────────────────────────────────${RESET}"
echo ""
echo -e "  ${BOLD}Start the factory:${RESET}"
echo -e "    ${B}bash ~/factory/start.sh${RESET}"
echo ""
echo -e "  ${BOLD}Submit a job:${RESET}"
echo -e "    ${B}cd ~/factory && python3 factoryctl.py new-job \"your topic\" --template documentary_video${RESET}"
echo ""
echo -e "  ${BOLD}In claw REPL:${RESET}"
echo -e "    ${D}make a video about the rise and fall of Kodak${RESET}"
echo ""
echo -e "  ${BOLD}Dashboard:${RESET} ${B}http://localhost:7000${RESET}"
echo ""
echo -e "  ${BOLD}YouTube upload (optional):${RESET}"
echo -e "    ${D}Message Jarvis: 'youtube setup'${RESET}"
echo ""
