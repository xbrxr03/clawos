#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Run inside Cubic Ubuntu chroot to build ClawOS ISO
# Usage: bash chroot_install.sh [desktop|server]
set -euo pipefail
EDITION="${1:-desktop}"

echo "  Building ClawOS $EDITION ISO chroot..."

# Core deps
apt-get update -q
apt-get install -y -q \
    python3 python3-pip python3-gi gir1.2-gtk-4.0 gir1.2-adwaita-1 \
    libadwaita-1-dev \
    nodejs npm curl wget git \
    portaudio19-dev python3-pyaudio \
    sqlite3

# Install Ollama
tmp_ollama="$(mktemp /tmp/clawos-ollama.XXXXXX.sh)"
curl -fsSL https://ollama.ai/install.sh -o "$tmp_ollama"
sh "$tmp_ollama"
rm -f "$tmp_ollama"

# Copy ClawOS to /opt/clawos
mkdir -p /opt/clawos
cp -r /tmp/clawos/* /opt/clawos/ 2>/dev/null || echo "  (copy from /tmp/clawos skipped)"

# Build the canonical frontend so /setup and the new command center shell exist
cd /opt/clawos/dashboard/frontend
npm install --no-fund --no-audit
npm run build
rm -rf node_modules
cd /opt/clawos

# Python deps
pip3 install --break-system-packages \
    fastapi uvicorn pyyaml aiohttp click \
    chromadb json_repair pypdf python-docx \
    openwakeword pystray Pillow pyaudio \
    gitpython ollama rich

# Wake word model
mkdir -p /opt/clawos/services/voiced/models
wget -q -O /opt/clawos/services/voiced/models/hey_jarvis.onnx \
    https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/hey_jarvis.onnx \
    || echo "  (wake word model download skipped — will retry at runtime)"

# First-run autostart
mkdir -p /etc/xdg/autostart
cp /opt/clawos/packaging/autostart/clawos-setup.desktop /etc/xdg/autostart/clawos-setup.desktop
mkdir -p /usr/share/applications
cp /opt/clawos/packaging/autostart/clawos-command-center.desktop /usr/share/applications/clawos-command-center.desktop

# symlink nexus command
ln -sf /opt/clawos/nexus/cli.py /usr/local/bin/nexus
chmod +x /opt/clawos/nexus/cli.py

# systemd user service for non-first-boot
mkdir -p /etc/skel/.config/systemd/user
cp /opt/clawos/systemd/clawos.service /etc/skel/.config/systemd/user/

echo "  ClawOS $EDITION ISO chroot complete."
