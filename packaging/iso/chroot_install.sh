#!/bin/bash
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
curl -fsSL https://ollama.ai/install.sh | sh

# Copy ClawOS to /opt/clawos
mkdir -p /opt/clawos
cp -r /tmp/clawos/* /opt/clawos/ 2>/dev/null || echo "  (copy from /tmp/clawos skipped)"

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
cat > /etc/xdg/autostart/clawos-setup.desktop << 'DESKTOP'
[Desktop Entry]
Type=Application
Name=ClawOS Setup
Comment=First-run wizard for ClawOS
Exec=python3 /opt/clawos/setup/first_run/gtk_wizard.py
Icon=system-software-install
X-GNOME-Autostart-enabled=true
NotShowIn=
DESKTOP

# symlink nexus command
ln -sf /opt/clawos/nexus/cli.py /usr/local/bin/nexus
chmod +x /opt/clawos/nexus/cli.py

# systemd user service for non-first-boot
mkdir -p /etc/skel/.config/systemd/user
cp /opt/clawos/systemd/clawos.service /etc/skel/.config/systemd/user/

echo "  ClawOS $EDITION ISO chroot complete."
