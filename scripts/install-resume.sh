#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# ClawOS Install Resume Script
# Resumes an interrupted ClawOS installation

set -uo pipefail

INSTALL_DIR="${INSTALL_DIR:-$HOME/.clawos-runtime}"
BOLD="\033[1m"
RESET="\033[0m"
G="\033[38;5;84m"
Y="\033[38;5;220m"
R="\033[38;5;203m"

echo ""
echo -e "  ${BOLD}ClawOS Install Resume${RESET}"
echo ""

# Check if already installed
if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "  ${R}No existing installation found at $INSTALL_DIR${RESET}"
    echo "  Run the full installer first:"
    echo "  curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh | bash"
    exit 1
fi

echo -e "  ${G}Found existing installation at $INSTALL_DIR${RESET}"
echo ""

# Check what steps are missing
cd "$INSTALL_DIR" || exit 1

# Step 1: Check Python venv
if [ ! -d "venv" ]; then
    echo -e "  ${Y}⚠ Python virtualenv missing - recreating...${RESET}"
    python3 -m venv venv
    source venv/bin/activate
    pip install -q -e .
else
    echo -e "  ${G}✓ Python virtualenv present${RESET}"
    source venv/bin/activate
fi

# Step 2: Check bootstrap config
if [ ! -f "$HOME/clawos/config/clawos.yaml" ]; then
    echo -e "  ${Y}⚠ Bootstrap not complete - running...${RESET}"
    python3 -m bootstrap.bootstrap --yes --skip-model
else
    echo -e "  ${G}✓ Bootstrap complete${RESET}"
fi

# Step 3: Check services
if ! curl -sf http://localhost:7070/api/health >/dev/null 2>&1; then
    echo -e "  ${Y}⚠ Services not running - starting...${RESET}"
    echo "  Run: bash scripts/dev_boot.sh"
else
    echo -e "  ${G}✓ Services running${RESET}"
fi

# Step 4: Check systemd
if [ ! -f "/etc/systemd/system/clawos.service" ]; then
    echo -e "  ${Y}⚠ Systemd service not installed${RESET}"
    echo "  To install: sudo cp systemd/*.service /etc/systemd/system/"
else
    echo -e "  ${G}✓ Systemd service installed${RESET}"
fi

echo ""
echo -e "  ${BOLD}Resume complete!${RESET}"
echo ""
echo "  Next steps:"
echo "    bash scripts/dev_boot.sh     - Start services"
echo "    bash scripts/clawos-status.sh - Check status"
echo "    http://localhost:7070/setup   - Complete setup wizard"
echo ""
