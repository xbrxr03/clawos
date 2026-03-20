#!/bin/bash
# content-factory — ClawOS skill installer
# Installs the full automated YouTube documentary pipeline.
#
# What this installs:
#   ~/factory/          — multi-agent video production system
#   ~/.claw/skills/content-factory/     — Claw Core skill
#   ~/.openclaw/skills/content-factory/ — OpenClaw skill
#
# Usage:
#   bash install.sh
#
# After install:
#   bash ~/factory/start.sh
#   # Then in claw or WhatsApp: "make a video about the rise of Tesla"

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
ok "ffmpeg + fonts installed"

# ── 2. Python packages ────────────────────────────────────────────────────────
step "Python packages"

pip3 install -q \
  google-auth-oauthlib \
  google-api-python-client \
  pillow \
  requests \
  --break-system-packages 2>/dev/null \
|| pip3 install -q \
  google-auth-oauthlib \
  google-api-python-client \
  pillow \
  requests \
  --user 2>/dev/null \
|| warn "Some Python packages failed — YouTube upload may not work"
ok "Python packages installed"

# ── 3. Piper TTS ──────────────────────────────────────────────────────────────
step "Piper TTS (voice generation)"

if command -v piper &>/dev/null; then
  ok "Piper already installed"
else
  pip3 install piper-tts --break-system-packages -q 2>/dev/null \
  || pip3 install piper-tts --user -q 2>/dev/null \
  || warn "Piper install failed — voice phase will be skipped"
  ok "Piper TTS installed"
fi

# Download voice model
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

# ── 4. Install factory ────────────────────────────────────────────────────────
step "Installing factory pipeline"

if [ -d "$FACTORY_DIR" ]; then
  info "Factory already exists at $FACTORY_DIR — updating agents only"
  # Update agents and config from this package
  cp "$SCRIPT_DIR/factory/agents/render_agent.py"  "$FACTORY_DIR/agents/"
  cp "$SCRIPT_DIR/factory/agents/upload_agent.py"  "$FACTORY_DIR/agents/"
  cp "$SCRIPT_DIR/factory/core/config.py"           "$FACTORY_DIR/core/"
  cp "$SCRIPT_DIR/factory/schemas/job_templates.json" "$FACTORY_DIR/schemas/"
  ok "Factory agents updated"
else
  cp -r "$SCRIPT_DIR/factory" "$FACTORY_DIR"
  ok "Factory installed to $FACTORY_DIR"
fi

# Ensure all required dirs exist
mkdir -p \
  "$FACTORY_DIR/jobs/inbox" \
  "$FACTORY_DIR/jobs/active" \
  "$FACTORY_DIR/jobs/completed" \
  "$FACTORY_DIR/jobs/failed" \
  "$FACTORY_DIR/artifacts" \
  "$FACTORY_DIR/logs" \
  "$FACTORY_DIR/state/agents" \
  "$FACTORY_DIR/state/events" \
  "$FACTORY_DIR/state/leases" \
  "$FACTORY_DIR/state/metrics" \
  "$FACTORY_DIR/assets/music"

chmod +x "$FACTORY_DIR/start.sh" "$FACTORY_DIR/stop.sh" 2>/dev/null || true
ok "Factory directories ready"

# ── 5. Install skill for Claw Core ───────────────────────────────────────────
step "Installing skill (Claw Core)"

mkdir -p "$CLAW_SKILL_DIR"
cp "$SCRIPT_DIR/SKILL.md"          "$CLAW_SKILL_DIR/SKILL.md"
cp "$SCRIPT_DIR/youtube_upload.py" "$CLAW_SKILL_DIR/youtube_upload.py"

if [ ! -f "$CLAW_SKILL_DIR/schedule.json" ]; then
  echo '{"upload_time": "09:00", "timezone": "local"}' > "$CLAW_SKILL_DIR/schedule.json"
fi
ok "Claw Core skill ready (~/.claw/skills/content-factory/)"

# ── 6. Install skill for OpenClaw ────────────────────────────────────────────
step "Installing skill (OpenClaw)"

mkdir -p "$OC_SKILL_DIR"
cp "$SCRIPT_DIR/SKILL.md"          "$OC_SKILL_DIR/SKILL.md"
cp "$SCRIPT_DIR/youtube_upload.py" "$OC_SKILL_DIR/youtube_upload.py"

if [ ! -f "$OC_SKILL_DIR/schedule.json" ]; then
  echo '{"upload_time": "09:00", "timezone": "local"}' > "$OC_SKILL_DIR/schedule.json"
fi
ok "OpenClaw skill ready (~/.openclaw/skills/content-factory/)"

# ── 7. Background music dir ───────────────────────────────────────────────────
step "Assets"

mkdir -p "$FACTORY_DIR/assets/music"
info "Drop royalty-free .mp3 files in: $FACTORY_DIR/assets/music/"
info "Recommended source: pixabay.com/music (free, no attribution needed)"
ok "Assets directory ready"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "  ${G}${BOLD}✓  Content Factory installed!${RESET}"
echo ""
echo -e "  ${D}────────────────────────────────────────────${RESET}"
echo ""
echo -e "  ${BOLD}Start the factory:${RESET}"
echo -e "    ${B}bash ~/factory/start.sh${RESET}"
echo ""
echo -e "  ${BOLD}Make your first video:${RESET}"
echo -e "    ${B}claw${RESET}  then: ${D}make a video about the rise and fall of Kodak${RESET}"
echo -e "    ${D}or via WhatsApp if OpenClaw gateway is running${RESET}"
echo ""
echo -e "  ${BOLD}Check pipeline status:${RESET}"
echo -e "    ${B}cd ~/factory && python3 factoryctl.py status${RESET}"
echo -e "    ${B}http://localhost:7000${RESET}  (dashboard)"
echo ""
echo -e "  ${BOLD}Set up YouTube upload (optional):${RESET}"
echo -e "    ${D}Message Jarvis: 'youtube setup'${RESET}"
echo ""
echo -e "  ${BOLD}Visual images (optional, needs ComfyUI):${RESET}"
echo -e "    ${B}bash ~/factory/start_visual.sh${RESET}"
echo -e "    ${D}Without ComfyUI, Pollinations.ai is used as fallback (free, online)${RESET}"
echo ""
