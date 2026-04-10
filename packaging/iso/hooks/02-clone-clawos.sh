#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# ClawOS ISO hook 02 — Clone and bootstrap ClawOS
set -uo pipefail

CLAWOS_REPO="${CLAWOS_REPO:-https://github.com/xbrxr03/clawos}"
CLAWOS_BRANCH="${CLAWOS_BRANCH:-main}"
INSTALL_DIR="/opt/clawos"

echo "[ClawOS hook 02] Cloning ClawOS from $CLAWOS_REPO ($CLAWOS_BRANCH)..."

if [ -d "$INSTALL_DIR/.git" ]; then
    echo "[hook 02] Existing install found, pulling latest..."
    git -C "$INSTALL_DIR" fetch origin
    git -C "$INSTALL_DIR" reset --hard "origin/$CLAWOS_BRANCH"
else
    git clone --depth 1 --branch "$CLAWOS_BRANCH" "$CLAWOS_REPO" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# Install Python packages
echo "[hook 02] Installing Python packages..."
python3 -m pip install -q -r requirements.txt --break-system-packages 2>/dev/null \
    || python3 -m pip install -q -r requirements.txt --user

# Build frontend
echo "[hook 02] Building dashboard frontend..."
if [ -d "$INSTALL_DIR/dashboard/frontend" ]; then
    cd "$INSTALL_DIR/dashboard/frontend"
    npm ci --silent
    npm run build --silent
    cd "$INSTALL_DIR"
fi

# Install systemd service
echo "[hook 02] Installing clawos.service..."
if [ -f "$INSTALL_DIR/packaging/clawos.service" ]; then
    cp "$INSTALL_DIR/packaging/clawos.service" /etc/systemd/system/
    systemctl enable clawos.service 2>/dev/null || true
fi

echo "[hook 02] ClawOS installed to $INSTALL_DIR"
