#!/bin/bash
# content-factory skill installer
# Usage: bash install.sh
# Installs the content-factory OpenClaw skill and all dependencies.

set -euo pipefail

G="\033[0;32m"; R="\033[0;31m"; B="\033[0;34m"; N="\033[0m"; D="\033[2m"
ok()   { echo -e "  ${G}✓${N}  $1"; }
step() { echo -e "\n  ${B}──${N}  $1"; }
warn() { echo -e "  \033[0;33m!${N}  $1"; }
die()  { echo -e "  ${R}✗${N}  $1"; exit 1; }

SKILL_DIR="$HOME/.openclaw/skills/content-factory"
FACTORY_DIR="${FACTORY_DIR:-$HOME/factory}"

echo ""
echo "  🎬 Content Factory — OpenClaw Skill Installer"
echo "  ─────────────────────────────────────────────"
echo ""

# ── 1. System deps ─────────────────────────────────────────────────────────
step "System dependencies"

sudo apt-get install -y -qq ffmpeg python3-pip fonts-dejavu 2>/dev/null \
  || warn "apt install had errors — continuing"
ok "ffmpeg + fonts installed"

# ── 2. Python packages ─────────────────────────────────────────────────────
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
|| warn "Some Python packages may have failed"
ok "Python packages installed"

# ── 3. Piper TTS ───────────────────────────────────────────────────────────
step "Piper TTS"

if command -v piper &>/dev/null; then
  ok "Piper already installed"
else
  pip3 install piper-tts --break-system-packages -q 2>/dev/null \
  || pip3 install piper-tts --user -q 2>/dev/null \
  || warn "Piper install failed — voice phase will be skipped"
  ok "Piper TTS installed"
fi

# Download voice model if not present
PIPER_MODEL_DIR="${PIPER_MODEL_DIR:-/usr/share/piper/voices}"
sudo mkdir -p "$PIPER_MODEL_DIR" 2>/dev/null || mkdir -p "$HOME/.local/share/piper"
PIPER_MODEL="$PIPER_MODEL_DIR/en_US-lessac-medium.onnx"

if [ ! -f "$PIPER_MODEL" ]; then
  ALT_MODEL="$HOME/.local/share/piper/en_US-lessac-medium.onnx"
  if [ ! -f "$ALT_MODEL" ]; then
    echo "  Downloading Piper voice model (~60MB)..."
    MODEL_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
    CONFIG_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
    TARGET_DIR="$HOME/.local/share/piper"
    mkdir -p "$TARGET_DIR"
    wget -q --show-progress "$MODEL_URL" -O "$TARGET_DIR/en_US-lessac-medium.onnx" 2>/dev/null \
    || curl -sL "$MODEL_URL" -o "$TARGET_DIR/en_US-lessac-medium.onnx" \
    || warn "Voice model download failed — run manually later"
    wget -q "$CONFIG_URL" -O "$TARGET_DIR/en_US-lessac-medium.onnx.json" 2>/dev/null \
    || curl -sL "$CONFIG_URL" -o "$TARGET_DIR/en_US-lessac-medium.onnx.json" 2>/dev/null || true
    ok "Voice model downloaded"
  else
    ok "Voice model already present"
  fi
else
  ok "Voice model already present"
fi

# ── 4. Factory source ──────────────────────────────────────────────────────
step "Factory source"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# If factory dir exists, update it. Otherwise copy from skill bundle.
if [ -d "$FACTORY_DIR" ]; then
  ok "Factory already at $FACTORY_DIR"
else
  if [ -d "$SCRIPT_DIR/factory" ]; then
    cp -r "$SCRIPT_DIR/factory" "$FACTORY_DIR"
    ok "Factory copied to $FACTORY_DIR"
  else
    warn "Factory source not found — please copy your factory directory to $FACTORY_DIR"
  fi
fi

# ── 5. Skill directory ─────────────────────────────────────────────────────
step "OpenClaw skill"

mkdir -p "$SKILL_DIR"
cp "$SCRIPT_DIR/SKILL.md"          "$SKILL_DIR/SKILL.md"
cp "$SCRIPT_DIR/youtube_upload.py" "$SKILL_DIR/youtube_upload.py"

# Create default schedule
if [ ! -f "$SKILL_DIR/schedule.json" ]; then
  echo '{"upload_time": "09:00", "timezone": "local"}' > "$SKILL_DIR/schedule.json"
fi

ok "Skill installed to $SKILL_DIR"

# ── 6. Background music dir ────────────────────────────────────────────────
step "Assets"

mkdir -p "$FACTORY_DIR/assets/music"
echo "  Put royalty-free .mp3 files in: $FACTORY_DIR/assets/music/"
echo "  Recommended: pixabay.com/music (free, no attribution required)"
ok "Assets directory ready"

# ── 7. Factory services ────────────────────────────────────────────────────
step "Factory services"

if [ -f "$FACTORY_DIR/start.sh" ]; then
  chmod +x "$FACTORY_DIR/start.sh"
  ok "start.sh ready"
else
  warn "start.sh not found in $FACTORY_DIR"
fi

# ── Done ───────────────────────────────────────────────────────────────────
echo ""
echo -e "  ${G}✓  Content Factory installed!${N}"
echo ""
echo "  ─────────────────────────────────────────────"
echo ""
echo "  Start the factory:"
echo "    bash ~/factory/start.sh"
echo ""
echo "  Start visual agent (ComfyUI must be running):"
echo "    bash ~/factory/start_visual.sh"
echo ""
echo "  Set up YouTube upload:"
echo "    Message OpenClaw: 'youtube setup'"
echo ""
echo "  Make your first video:"
echo "    Message OpenClaw: 'make a video about the rise and fall of Kodak'"
echo ""
echo "  Check status:"
echo "    Message OpenClaw: 'status'"
echo "    Or visit: http://localhost:7000"
echo ""
