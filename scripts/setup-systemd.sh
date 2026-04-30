#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# ClawOS Phase 4 — systemd unit installer
# Copies unit files to ~/.config/systemd/user/ and enables clawos.service
#
# Usage:
#   bash ~/clawos/scripts/setup-systemd.sh           # install + enable
#   bash ~/clawos/scripts/setup-systemd.sh --remove  # uninstall + disable
#   bash ~/clawos/scripts/setup-systemd.sh --reload  # reinstall after unit changes

set -uo pipefail

CLAWOS_HOME="${CLAWOS_HOME:-$HOME/.clawos-runtime}"
UNIT_SRC="$CLAWOS_HOME/systemd"
UNIT_DST="$HOME/.config/systemd/user"
LOG_DIR="$CLAWOS_HOME/logs"
SCRIPTS_DIR="$CLAWOS_HOME/scripts"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
err()  { echo -e "  ${RED}✗${NC} $1"; }
hdr()  { echo -e "\n${BOLD}$1${NC}"; }

ALL_UNITS=(
    clawos-policyd.service
    clawos-memd.service
    clawos-modeld.service
    clawos-toolbridge.service
    clawos-agentd.service
    clawos-voiced.service
    clawos-clawd.service
    clawos-dashd.service
    clawos-scheduler.service
    clawos-reminderd.service
    clawos-waketrd.service
    clawos.service
)

remove_units() {
    hdr "Removing ClawOS systemd units..."
    systemctl --user stop clawos.service 2>/dev/null || true
    systemctl --user disable clawos.service 2>/dev/null || true
    for unit in "${ALL_UNITS[@]}"; do
        rm -f "$UNIT_DST/$unit"
        # Remove any drop-in overrides that may shadow our unit
        rm -rf "$UNIT_DST/${unit%.service}.service.d"
        ok "Removed $unit"
    done
    systemctl --user daemon-reload
    ok "Daemon reloaded"
    echo -e "\n${GREEN}ClawOS units removed.${NC}"
}

install_units() {
    hdr "Installing ClawOS systemd units..."

    if ! loginctl show-user "$USER" 2>/dev/null | grep -q "Linger=yes"; then
        warn "Enabling lingering for $USER (services survive logout)..."
        loginctl enable-linger "$USER" 2>/dev/null || \
            warn "Could not enable lingering — run: sudo loginctl enable-linger $USER"
    fi

    mkdir -p "$UNIT_DST" "$LOG_DIR"

    if [ ! -d "$UNIT_SRC" ]; then
        err "Unit directory not found: $UNIT_SRC"
        exit 1
    fi

    chmod +x "$SCRIPTS_DIR/clawos-start.sh" \
              "$SCRIPTS_DIR/clawos-stop.sh"  \
              "$SCRIPTS_DIR/clawos-status.sh" 2>/dev/null || true

    for unit in "${ALL_UNITS[@]}"; do
        # Remove stale drop-in overrides before installing so they can't shadow our ExecStart
        rm -rf "$UNIT_DST/${unit%.service}.service.d" 2>/dev/null || true
        if [ -f "$UNIT_SRC/$unit" ]; then
            # Substitute /home/user placeholder with the actual home directory
            sed "s|/home/user|${HOME}|g" "$UNIT_SRC/$unit" > "$UNIT_DST/$unit"
            ok "Installed $unit"
        else
            warn "Missing $UNIT_SRC/$unit — skipping"
        fi
    done

    systemctl --user daemon-reload
    ok "Daemon reloaded"

    systemctl --user enable clawos.service
    ok "clawos.service enabled (auto-starts at login)"

    echo -e "\n${GREEN}${BOLD}Done.${NC}"
    echo ""
    echo "  Start:   systemctl --user start clawos"
    echo "  Stop:    systemctl --user stop clawos"
    echo "  Status:  clawos status"
    echo "  Logs:    journalctl --user -u clawos-policyd -f"
    echo ""
}

case "${1:-}" in
    --remove) remove_units ;;
    --reload)
        hdr "Reloading ClawOS units..."
        systemctl --user stop clawos.service 2>/dev/null || true
        install_units
        systemctl --user start clawos.service
        ok "ClawOS restarted" ;;
    *) install_units ;;
esac
