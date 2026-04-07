#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# ClawOS ordered teardown — called by clawos.service ExecStop
# Stops services in reverse boot order so nothing dies mid-task.

set -uo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $*"; }
info() { echo -e "  ${YELLOW}→${NC} $*"; }

echo ""
echo -e "${BOLD}Stopping ClawOS...${NC}"
echo ""

STOP_ORDER=(
    clawos-gatewayd
    clawos-dashd
    clawos-clawd
    clawos-voiced
    clawos-agentd
    clawos-toolbridge
    clawos-modeld
    clawos-memd
    clawos-policyd
)

for unit in "${STOP_ORDER[@]}"; do
    if systemctl --user is-active --quiet "$unit" 2>/dev/null; then
        info "Stopping $unit..."
        systemctl --user stop "$unit" 2>/dev/null || true
        ok "$unit stopped"
    fi
done

echo ""
echo -e "${GREEN}${BOLD}ClawOS stopped.${NC}"
echo ""
