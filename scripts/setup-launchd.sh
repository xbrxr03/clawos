#!/usr/bin/env bash
# ClawOS launchd installer for macOS user agents.
# Installs LaunchAgents for ClawOS and Ollama, and optionally OpenClaw gateway.

set -uo pipefail

CLAWOS_HOME="${CLAWOS_HOME:-$HOME/clawos}"
WORKSPACE="${CLAWOS_WORKSPACE:-nexus_default}"
AGENT_DIR="${HOME}/Library/LaunchAgents"
LOG_DIR="${CLAWOS_HOME}/logs"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"
OLLAMA_BIN="${OLLAMA_BIN:-$(command -v ollama || true)}"
OPENCLAW_BIN="${OPENCLAW_BIN:-$(command -v openclaw || true)}"
OPENCLAW_GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
UID_STR="$(id -u)"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
err()  { echo -e "  ${RED}✗${NC} $1"; }
hdr()  { echo -e "\n${BOLD}$1${NC}"; }

DAEMON_LABEL="io.clawos.daemon"
OLLAMA_LABEL="io.clawos.ollama"
OPENCLAW_LABEL="io.clawos.openclaw-gateway"

daemon_plist="${AGENT_DIR}/${DAEMON_LABEL}.plist"
ollama_plist="${AGENT_DIR}/${OLLAMA_LABEL}.plist"
openclaw_plist="${AGENT_DIR}/${OPENCLAW_LABEL}.plist"

mkdir -p "$AGENT_DIR" "$LOG_DIR"

bootstrap_agent() {
  local label="$1"
  local plist="$2"
  launchctl bootout "gui/${UID_STR}" "$plist" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/${UID_STR}" "$plist" >/dev/null 2>&1 || return 1
  launchctl kickstart -k "gui/${UID_STR}/${label}" >/dev/null 2>&1 || return 1
  return 0
}

write_common_header() {
  cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$1</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>WorkingDirectory</key>
  <string>${CLAWOS_HOME}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>HOME</key>
    <string>${HOME}</string>
    <key>PATH</key>
    <string>${HOME}/.local/bin:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/local/sbin:${PATH}</string>
    <key>CLAWOS_DIR</key>
    <string>${CLAWOS_HOME}</string>
EOF
}

write_daemon_agent() {
  cat > "$daemon_plist" <<EOF
$(write_common_header "$DAEMON_LABEL")
    <key>PYTHONPATH</key>
    <string>${CLAWOS_HOME}</string>
  </dict>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON_BIN}</string>
    <string>${CLAWOS_HOME}/clients/daemon/daemon.py</string>
    <string>${WORKSPACE}</string>
  </array>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/clawos.stdout.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/clawos.stderr.log</string>
</dict>
</plist>
EOF
}

write_ollama_agent() {
  [ -n "$OLLAMA_BIN" ] || return 0
  cat > "$ollama_plist" <<EOF
$(write_common_header "$OLLAMA_LABEL")
  </dict>
  <key>ProgramArguments</key>
  <array>
    <string>${OLLAMA_BIN}</string>
    <string>serve</string>
  </array>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/ollama.stdout.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/ollama.stderr.log</string>
</dict>
</plist>
EOF
}

write_openclaw_agent() {
  [ -n "$OPENCLAW_BIN" ] || return 0
  cat > "$openclaw_plist" <<EOF
$(write_common_header "$OPENCLAW_LABEL")
  </dict>
  <key>ProgramArguments</key>
  <array>
    <string>${OPENCLAW_BIN}</string>
    <string>gateway</string>
    <string>--port</string>
    <string>${OPENCLAW_GATEWAY_PORT}</string>
  </array>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/openclaw-gateway.stdout.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/openclaw-gateway.stderr.log</string>
</dict>
</plist>
EOF
}

remove_agents() {
  hdr "Removing ClawOS launchd agents..."
  for plist in "$daemon_plist" "$ollama_plist" "$openclaw_plist"; do
    [ -f "$plist" ] || continue
    launchctl bootout "gui/${UID_STR}" "$plist" >/dev/null 2>&1 || true
    rm -f "$plist"
    ok "Removed $(basename "$plist")"
  done
}

install_agents() {
  hdr "Installing ClawOS launchd agents..."
  write_daemon_agent
  ok "Wrote $(basename "$daemon_plist")"

  if [ -n "$OLLAMA_BIN" ]; then
    write_ollama_agent
    ok "Wrote $(basename "$ollama_plist")"
  else
    warn "ollama not found — skipping launchd agent"
  fi

  if [ -n "$OPENCLAW_BIN" ]; then
    write_openclaw_agent
    ok "Wrote $(basename "$openclaw_plist")"
  fi

  bootstrap_agent "$DAEMON_LABEL" "$daemon_plist" && ok "ClawOS daemon loaded" || warn "Could not load ClawOS daemon"
  if [ -f "$ollama_plist" ]; then
    bootstrap_agent "$OLLAMA_LABEL" "$ollama_plist" && ok "Ollama loaded" || warn "Could not load Ollama"
  fi
  if [ -f "$openclaw_plist" ]; then
    bootstrap_agent "$OPENCLAW_LABEL" "$openclaw_plist" && ok "OpenClaw gateway loaded" || warn "Could not load OpenClaw gateway"
  fi

  echo ""
  echo "  Start:   launchctl bootstrap gui/${UID_STR} ${daemon_plist}"
  echo "  Stop:    launchctl bootout gui/${UID_STR} ${daemon_plist}"
  echo "  Status:  launchctl print gui/${UID_STR}/${DAEMON_LABEL}"
  echo ""
}

case "${1:-}" in
  --remove) remove_agents ;;
  --reload)
    remove_agents
    install_agents
    ;;
  *) install_agents ;;
esac
