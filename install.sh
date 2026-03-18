#!/bin/bash
# ClawOS — one-command installer
# curl -fsSL https://clawos.dev/install.sh | bash
#
# Installs on Ubuntu 22.04/24.04, Debian 12+, Raspberry Pi OS
# Requirements: 8GB RAM minimum, internet for first run only
set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
  BOLD="\033[1m"; RESET="\033[0m"
  G="\033[38;5;84m"; R="\033[38;5;203m"; B="\033[38;5;75m"
  P="\033[38;5;141m"; D="\033[2m\033[38;5;245m"; Y="\033[38;5;220m"
else
  BOLD=""; RESET=""; G=""; R=""; B=""; P=""; D=""; Y=""
fi

step()  { echo -e "\n${B}${BOLD}  ──${RESET}  $1"; }
ok()    { echo -e "  ${G}✓${RESET}  $1"; }
info()  { echo -e "  ${D}·  $1${RESET}"; }
warn()  { echo -e "  ${Y}!${RESET}  $1"; }
die()   { echo -e "\n  ${R}✗${RESET}  $1\n"; exit 1; }

# ── Banner ────────────────────────────────────────────────────────────────────
echo -e "${P}${BOLD}"
cat << 'BANNER'

  ██████╗██╗      █████╗ ██╗    ██╗ ██████╗ ███████╗
 ██╔════╝██║     ██╔══██╗██║    ██║██╔═══██╗██╔════╝
 ██║     ██║     ███████║██║ █╗ ██║██║   ██║███████╗
 ██║     ██║     ██╔══██║██║███╗██║██║   ██║╚════██║
 ╚██████╗███████╗██║  ██║╚███╔███╔╝╚██████╔╝███████║
  ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝  ╚═════╝ ╚══════╝

BANNER
echo -e "${RESET}${D}  Local AI agent OS — offline, private, free${RESET}"
echo -e "${D}  ──────────────────────────────────────────────${RESET}"
echo ""

# ── Config ────────────────────────────────────────────────────────────────────
CLAWOS_REPO="${CLAWOS_REPO:-https://github.com/xbrxr03/clawos}"
INSTALL_DIR="${CLAWOS_DIR:-$HOME/clawos}"
CLAWOS_BRANCH="${CLAWOS_BRANCH:-main}"
SKIP_MODEL="${SKIP_MODEL:-false}"
SKIP_OPENCLAW="${SKIP_OPENCLAW:-false}"
MIN_RAM_GB=7

# ── Preflight ────────────────────────────────────────────────────────────────
step "Checking system"

# OS check
if [ -f /etc/os-release ]; then
  . /etc/os-release
  case "$ID" in
    ubuntu|debian|raspbian|linuxmint|pop) ;;
    *) warn "Untested OS: $ID. Proceeding anyway — may need manual fixes." ;;
  esac
else
  warn "Cannot detect OS. Proceeding."
fi

# RAM check
RAM_KB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}' || echo 0)
RAM_GB=$((RAM_KB / 1024 / 1024))
if [ "$RAM_GB" -lt "$MIN_RAM_GB" ]; then
  die "Not enough RAM: ${RAM_GB}GB detected, ${MIN_RAM_GB}GB required."
fi
ok "RAM: ${RAM_GB}GB"

# Disk check — need at least 10GB free
DISK_FREE=$(df -BG "$HOME" | awk 'NR==2 {gsub("G",""); print $4}')
if [ "${DISK_FREE:-0}" -lt 10 ]; then
  die "Not enough disk: ${DISK_FREE}GB free, need 10GB."
fi
ok "Disk: ${DISK_FREE}GB free"

# Python check
if ! command -v python3 &>/dev/null; then
  die "python3 not found. Install it: sudo apt-get install -y python3"
fi
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Python $PY_VER"
ok "Preflight passed"

# ── System packages ───────────────────────────────────────────────────────────
step "Installing system dependencies"

sudo apt-get update -qq 2>/dev/null || warn "apt update had errors — continuing"
sudo apt-get install -y -qq \
  python3-pip python3-venv \
  git curl wget \
  sqlite3 \
  2>/dev/null || die "Failed to install system packages"
ok "System packages"

# ── Ollama ────────────────────────────────────────────────────────────────────
step "Setting up Ollama (local model runtime)"

if command -v ollama &>/dev/null; then
  ok "Ollama already installed"
else
  info "Downloading Ollama..."
  curl -fsSL https://ollama.com/install.sh | sh >/dev/null 2>&1 \
    || die "Ollama install failed. Try: curl -fsSL https://ollama.com/install.sh | sh"
  ok "Ollama installed"
fi

# Start Ollama if not running
if ! curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
  info "Starting Ollama..."
  nohup ollama serve >/dev/null 2>&1 &
  sleep 3
  if ! curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
    warn "Ollama not responding — will retry after install"
  else
    ok "Ollama running"
  fi
else
  ok "Ollama running"
fi

# ── Clone / update ClawOS ─────────────────────────────────────────────────────
step "Installing ClawOS"

if [ -d "$INSTALL_DIR/clawos_core" ]; then
  info "ClawOS already present at $INSTALL_DIR"
  ok "Using existing install"
elif [ -d "$INSTALL_DIR/.git" ]; then
  info "Updating existing install at $INSTALL_DIR"
  git -C "$INSTALL_DIR" pull --ff-only -q 2>/dev/null \
    || warn "Git pull failed — using existing version"
  ok "Updated"
else
  info "Cloning from $CLAWOS_REPO"
  git clone -q --branch "$CLAWOS_BRANCH" --depth 1 \
    "$CLAWOS_REPO" "$INSTALL_DIR" \
    || die "Clone failed. Check: $CLAWOS_REPO"
  ok "Cloned to $INSTALL_DIR"
fi

cd "$INSTALL_DIR"
export PYTHONPATH="$INSTALL_DIR"

# ── Python packages ───────────────────────────────────────────────────────────
step "Installing Python packages"

pip3 install -q \
  pyyaml \
  aiohttp \
  fastapi \
  "uvicorn[standard]" \
  ollama \
  click \
  chromadb \
  json_repair \
  --break-system-packages 2>/dev/null \
|| pip3 install -q \
  pyyaml \
  aiohttp \
  fastapi \
  "uvicorn[standard]" \
  ollama \
  click \
  chromadb \
  json_repair \
  --user 2>/dev/null \
|| warn "Some Python packages may have failed — proceeding"

ok "Python packages"

# ── Bootstrap ────────────────────────────────────────────────────────────────
step "Bootstrapping ClawOS"

# Detect RAM tier for profile
if [ "$RAM_GB" -ge 32 ]; then
  PROFILE="performance"
elif [ "$RAM_GB" -ge 14 ]; then
  PROFILE="balanced"
else
  PROFILE="lowram"
fi
info "Profile: $PROFILE (${RAM_GB}GB RAM)"

python3 -m bootstrap.bootstrap --profile "$PROFILE" --yes \
  || die "Bootstrap failed. Try: cd $INSTALL_DIR && python3 -m bootstrap.bootstrap"

ok "Bootstrap complete"

# ── Pull model ────────────────────────────────────────────────────────────────
step "Pulling AI model"

if [ "$SKIP_MODEL" = "true" ]; then
  warn "Skipping model pull (SKIP_MODEL=true)"
else
  # Pick model based on RAM
  if [ "$RAM_GB" -ge 32 ]; then
    MODEL="gemma3:12b"
  else
    MODEL="gemma3:4b"
  fi

  info "Pulling $MODEL (~3GB, takes 5-10 min on first run)..."

  # Ensure Ollama is running
  if ! curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
    nohup ollama serve >/dev/null 2>&1 &
    sleep 4
  fi

  if ollama pull "$MODEL" 2>&1 | tail -1; then
    ok "Model ready: $MODEL"
  else
    warn "Model pull failed — run manually: ollama pull $MODEL"
  fi
fi

# ── OpenClaw offline config ───────────────────────────────────────────────────
step "Configuring OpenClaw for offline use"

if [ "$SKIP_OPENCLAW" = "true" ]; then
  info "Skipping OpenClaw (SKIP_OPENCLAW=true)"
elif ! command -v node &>/dev/null; then
  warn "Node.js not found — skipping OpenClaw. Install later: clawctl openclaw install"
else
  # Check if openclaw is installed
  if command -v openclaw &>/dev/null; then
    ok "OpenClaw already installed"
  else
    info "Installing OpenClaw..."
    npm install -g openclaw@latest --quiet 2>/dev/null \
      || warn "OpenClaw npm install failed — try: sudo npm install -g openclaw"
  fi

  # Write OpenClaw offline config for Ollama
  OC_DIR="$HOME/.openclaw"
  mkdir -p "$OC_DIR/agents/main/agent"

  # Auth profile — required to avoid OpenClaw cloud auth
  cat > "$OC_DIR/agents/main/agent/auth-profiles.json" << 'JSON'
{
  "ollama:local": {
    "type": "token",
    "provider": "ollama",
    "token": "ollama-local"
  },
  "lastGood": {
    "ollama": "ollama:local"
  }
}
JSON

  # Main config — point at local Ollama, disable cloud
  # Pick best openclaw model (needs tool-calling support — not gemma3)
  if [ "$RAM_GB" -ge 32 ]; then
    OC_MODEL="qwen2.5:14b"
  else
    OC_MODEL="qwen2.5:7b"
  fi

  cat > "$OC_DIR/openclaw.json" << JSON
{
  "models": {
    "providers": {
      "ollama": {
        "baseUrl": "http://127.0.0.1:11434/v1",
        "apiKey": "ollama-local",
        "api": "openai-completions",
        "models": [
          {
            "id": "${OC_MODEL}",
            "name": "${OC_MODEL}",
            "contextWindow": 8192,
            "maxOutput": 4096,
            "inputCostPer1M": 0,
            "outputCostPer1M": 0
          }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "ollama/${OC_MODEL}"
      }
    }
  },
  "cloud": {
    "enabled": false,
    "fallback": false
  },
  "network": {
    "mode": "offline",
    "allow_local_network": true
  }
}
JSON

  ok "OpenClaw configured for offline Ollama (model: $OC_MODEL)"

  # Pull OpenClaw model if we have the RAM for it
  if [ "$RAM_GB" -ge 14 ]; then
    info "Pulling OpenClaw model: $OC_MODEL"
    if ollama pull "$OC_MODEL" 2>&1 | tail -1; then
      ok "OpenClaw model ready: $OC_MODEL"
    else
      warn "Pull failed — run: ollama pull $OC_MODEL"
    fi
  else
    warn "Only ${RAM_GB}GB RAM — skipping OpenClaw model (needs 16GB+)"
    warn "To enable: ollama pull $OC_MODEL && clawctl openclaw start"
  fi
fi

# ── clawctl in PATH ───────────────────────────────────────────────────────────
step "Installing clawctl"

mkdir -p "$HOME/.local/bin"

cat > "$HOME/.local/bin/clawctl" << CMD
#!/bin/bash
export PYTHONPATH="${INSTALL_DIR}"
exec python3 "${INSTALL_DIR}/clawctl/main.py" "\$@"
CMD
chmod +x "$HOME/.local/bin/clawctl"

# Also create a direct chat alias
cat > "$HOME/.local/bin/claw" << CMD
#!/bin/bash
export PYTHONPATH="${INSTALL_DIR}"
exec python3 "${INSTALL_DIR}/clients/cli/repl.py" "\$@"
CMD
chmod +x "$HOME/.local/bin/claw"

# Add to PATH in shell profiles
_add_to_path() {
  local profile="$1"
  if [ -f "$profile" ] && ! grep -q '.local/bin' "$profile" 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$profile"
  fi
}
_add_to_path "$HOME/.bashrc"
_add_to_path "$HOME/.zshrc"
_add_to_path "$HOME/.profile"
export PATH="$HOME/.local/bin:$PATH"

ok "clawctl and claw installed"

# ── Autostart (optional) ──────────────────────────────────────────────────────
step "Setting up autostart"

# Create a systemd user service for Ollama (keep it running)
if command -v systemctl &>/dev/null && systemctl --user status >/dev/null 2>&1; then
  mkdir -p "$HOME/.config/systemd/user"
  cat > "$HOME/.config/systemd/user/ollama.service" << UNIT
[Unit]
Description=Ollama AI Runtime
After=network.target

[Service]
ExecStart=/usr/local/bin/ollama serve
Restart=always
RestartSec=3
Environment=HOME=${HOME}

[Install]
WantedBy=default.target
UNIT

  systemctl --user daemon-reload 2>/dev/null || true
  systemctl --user enable ollama.service 2>/dev/null || true
  systemctl --user start ollama.service 2>/dev/null || true
  ok "Ollama autostart enabled"
else
  info "systemd user services not available — start Ollama manually: ollama serve"
fi

# ── Done ─────────────────────────────────────────────────────────────────────
ELAPSED=$SECONDS
echo ""
echo -e "  ${G}${BOLD}✓  ClawOS installed in ${ELAPSED}s${RESET}"
echo ""
echo -e "  ${D}──────────────────────────────────────────────${RESET}"
echo ""
echo -e "  ${BOLD}Start chatting:${RESET}"
echo -e "  ${B}  claw${RESET}                  interactive chat"
echo ""
echo -e "  ${BOLD}All services + dashboard:${RESET}"
echo -e "  ${B}  clawctl start${RESET}         start everything"
echo -e "  ${B}  clawctl status${RESET}        check health"
echo -e "  ${B}  http://localhost:7070${RESET}  dashboard"
echo ""
echo -e "  ${BOLD}OpenClaw (optional, 16GB+ RAM):${RESET}"
echo -e "  ${B}  clawctl openclaw start${RESET}"
echo -e "  ${B}  openclaw onboard${RESET}      connect WhatsApp"
echo ""
echo -e "  ${D}Restart your shell or run: source ~/.bashrc${RESET}"
echo ""
echo -e "  ${D}GitHub:  https://github.com/xbrxr03/clawos${RESET}"
echo -e "  ${D}Docs:    https://clawos.dev${RESET}"
echo ""
