#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# ClawOS ISO hook 01 — Install system dependencies
# Runs inside the chroot during ISO build.
set -uo pipefail

echo "[ClawOS hook 01] Installing system dependencies..."

export DEBIAN_FRONTEND=noninteractive

apt-get update -qq

# Core system packages
apt-get install -y -qq \
    git curl wget ca-certificates gnupg lsb-release \
    python3 python3-pip python3-venv python3-dev \
    build-essential pkg-config \
    portaudio19-dev libsndfile1 libsndfile1-dev \
    ffmpeg \
    nodejs npm \
    pipewire pipewire-audio-client-libraries wireplumber \
    aplay alsa-utils \
    jq \
    systemd \
    2>&1 | tail -5

# Node.js — use NodeSource 20.x if system node is too old
NODE_VERSION=$(node --version 2>/dev/null | sed 's/v//' | cut -d. -f1)
if [ -z "$NODE_VERSION" ] || [ "$NODE_VERSION" -lt 18 ]; then
    echo "[hook 01] Installing Node.js 20.x from NodeSource..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y -qq nodejs
fi

# Ollama
if ! command -v ollama &>/dev/null; then
    echo "[hook 01] Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
fi

echo "[hook 01] System dependencies installed."
