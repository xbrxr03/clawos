#!/bin/bash
# ClawOS — one-command installer
# curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh -o /tmp/clawos.sh && bash /tmp/clawos.sh
set -uo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
  BOLD="\033[1m"; RESET="\033[0m"
  G="\033[38;5;84m";  R="\033[38;5;203m"; B="\033[38;5;75m"
  P="\033[38;5;141m"; D="\033[2m\033[38;5;245m"
  Y="\033[38;5;220m"; W="\033[38;5;255m"
else
  BOLD=""; RESET=""; G=""; R=""; B=""; P=""; D=""; Y=""; W=""
fi

# ── Helpers ───────────────────────────────────────────────────────────────────
divider() { echo -e "${D}  ──────────────────────────────────────────────────────${RESET}"; }
step()  { echo -e "\n${B}${BOLD}  ◆${RESET}  ${W}${BOLD}$1${RESET}"; }
ok()    { echo -e "  ${G}✓${RESET}  $1"; }
info()  { echo -e "  ${D}·  $1${RESET}"; }
warn()  { echo -e "  ${Y}▲${RESET}  ${Y}$1${RESET}"; }
die()   { echo -e "\n  ${R}✗  $1${RESET}\n"; exit 1; }

spinner() {
  local pid=$1 msg=$2
  local frames=("⠋" "⠙" "⠹" "⠸" "⠼" "⠴" "⠦" "⠧" "⠇" "⠏")
  local i=0
  while kill -0 "$pid" 2>/dev/null; do
    printf "\r  ${B}${frames[$i]}${RESET}  ${D}%s${RESET}   " "$msg"
    i=$(( (i+1) % ${#frames[@]} ))
    sleep 0.08
  done
  printf "\r\033[K"
}

# ── Banner ────────────────────────────────────────────────────────────────────
clear
echo ""
echo -e "${P}${BOLD}"
cat << 'BANNER'
   ██████╗██╗      █████╗ ██╗    ██╗ ██████╗ ███████╗
  ██╔════╝██║     ██╔══██╗██║    ██║██╔═══██╗██╔════╝
  ██║     ██║     ███████║██║ █╗ ██║██║   ██║███████╗
  ██║     ██║     ██╔══██║██║███╗██║██║   ██║╚════██║
  ╚██████╗███████╗██║  ██║╚███╔███╔╝╚██████╔╝███████║
   ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝  ╚═════╝ ╚══════╝
BANNER
echo -e "${RESET}"
echo -e "  ${W}${BOLD}Agent-native OS. Offline. Private. Free.${RESET}"
echo -e "  ${D}github.com/xbrxr03/clawos${RESET}"
echo ""
divider
echo ""

# ── Config ────────────────────────────────────────────────────────────────────
CLAWOS_REPO="${CLAWOS_REPO:-https://github.com/xbrxr03/clawos}"
INSTALL_DIR="${CLAWOS_DIR:-$HOME/clawos}"
CLAWOS_BRANCH="${CLAWOS_BRANCH:-main}"
SKIP_MODEL="${SKIP_MODEL:-false}"
MIN_RAM_GB=7
START_TIME=$SECONDS

# ── Preflight ─────────────────────────────────────────────────────────────────
step "Checking your system"

if [ -f /etc/os-release ]; then
  . /etc/os-release
  case "$ID" in
    ubuntu|debian|raspbian|linuxmint|pop) ok "OS: $PRETTY_NAME" ;;
    *) warn "Untested OS: $ID — proceeding anyway" ;;
  esac
fi

# RAM detection — Linux, macOS, fallback
if [ -f /proc/meminfo ]; then
  RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
  RAM_GB=$((RAM_KB / 1024 / 1024))
elif command -v sysctl &>/dev/null; then
  RAM_BYTES=$(sysctl -n hw.memsize 2>/dev/null || echo 0)
  RAM_GB=$((RAM_BYTES / 1024 / 1024 / 1024))
else
  warn "Cannot detect RAM — assuming 8GB and continuing"
  RAM_GB=8
fi
[ "$RAM_GB" -lt "$MIN_RAM_GB" ] && die "Not enough RAM: ${RAM_GB}GB found, ${MIN_RAM_GB}GB required."
ok "RAM: ${RAM_GB}GB"

if df -BG "$HOME" >/dev/null 2>&1; then
  # Linux: df -BG prints sizes in gigabytes, available is column 4
  DISK_FREE=$(df -BG "$HOME" | awk 'NR==2 {gsub("G",""); print $4}')
else
  # macOS: df -g prints sizes in gigabytes, available is column 4
  DISK_FREE=$(df -g "$HOME" | awk 'NR==2 {print $4}')
fi
[ "${DISK_FREE:-0}" -lt 10 ] && die "Not enough disk: ${DISK_FREE}GB free, need 10GB."
ok "Disk: ${DISK_FREE}GB free"

command -v python3 &>/dev/null || die "python3 not found: sudo apt-get install -y python3"
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
ok "Python $PY_VER"

if   [ "$RAM_GB" -ge 32 ]; then PROFILE="performance"; TIER="Tier C  GPU workstation"
elif [ "$RAM_GB" -ge 14 ]; then PROFILE="balanced";    TIER="Tier B  workstation"
else                             PROFILE="lowram";      TIER="Tier A  mini PC"
fi
ok "Hardware: $TIER"

# ── System packages ───────────────────────────────────────────────────────────
step "Installing system packages"

(sudo apt-get update -qq 2>/dev/null && \
 sudo apt-get install -y -qq python3-pip python3-venv git curl wget sqlite3 2>/dev/null) \
  & spinner $! "Updating apt and installing dependencies"
wait $! || die "Failed to install system packages"
ok "git  curl  sqlite3  python3-pip"

# ── Ollama ────────────────────────────────────────────────────────────────────
step "Setting up Ollama"

if command -v ollama &>/dev/null; then
  ok "Ollama already installed"
else
  (curl -fsSL https://ollama.com/install.sh | sh >/dev/null 2>&1) \
    & spinner $! "Downloading and installing Ollama"
  wait $! || die "Ollama install failed. Run: curl -fsSL https://ollama.com/install.sh | sh"
  ok "Ollama installed"
fi

if ! curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
  nohup ollama serve >/dev/null 2>&1 &
  for i in 1 2 3 4 5; do
    sleep 1
    curl -sf http://localhost:11434/api/tags >/dev/null 2>&1 && break
  done
  curl -sf http://localhost:11434/api/tags >/dev/null 2>&1 \
    && ok "Ollama server running" \
    || warn "Ollama not responding — run 'ollama serve' manually if needed"
else
  ok "Ollama server running"
fi

# ── Node.js ───────────────────────────────────────────────────────────────────
step "Installing Node.js"

if command -v node &>/dev/null; then
  ok "Node.js $(node --version) already installed"
else
  (curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - >/dev/null 2>&1 \
    && sudo apt-get install -y -qq nodejs 2>/dev/null) \
    & spinner $! "Installing Node.js LTS"
  wait $! 2>/dev/null || true
  command -v node &>/dev/null \
    && ok "Node.js $(node --version)" \
    || warn "Node.js install failed — OpenClaw will be skipped"
fi

# ── OpenClaw ──────────────────────────────────────────────────────────────────
step "Installing OpenClaw"

if ! command -v node &>/dev/null; then
  warn "Skipping — Node.js not available"
elif command -v openclaw &>/dev/null; then
  ok "OpenClaw already installed"
else
  (npm install -g openclaw@latest --quiet 2>/dev/null) \
    & spinner $! "Installing OpenClaw via npm"
  wait $! || warn "OpenClaw npm install failed — try: sudo npm install -g openclaw"
  command -v openclaw &>/dev/null \
    && ok "OpenClaw installed" \
    || warn "OpenClaw not found after install"
fi

# ── Clone ClawOS ──────────────────────────────────────────────────────────────
step "Installing Nexus"

if [ -d "$INSTALL_DIR/clawos_core" ]; then
  ok "Nexus already present at $INSTALL_DIR"
elif [ -d "$INSTALL_DIR/.git" ]; then
  (git -C "$INSTALL_DIR" pull --ff-only -q 2>/dev/null) \
    & spinner $! "Updating existing install"
  wait $! || warn "Git pull failed — using existing version"
  ok "Nexus updated"
else
  (git clone -q --branch "$CLAWOS_BRANCH" --depth 1 "$CLAWOS_REPO" "$INSTALL_DIR") \
    & spinner $! "Cloning from GitHub"
  wait $! || die "Clone failed. Check: $CLAWOS_REPO"
  ok "Nexus cloned to $INSTALL_DIR"
fi

cd "$INSTALL_DIR"
export PYTHONPATH="$INSTALL_DIR"

# ── Python packages ───────────────────────────────────────────────────────────
step "Installing Python packages"

(pip3 install -q \
  pyyaml aiohttp fastapi "uvicorn[standard]" \
  ollama click chromadb json_repair \
  --break-system-packages 2>/dev/null \
|| pip3 install -q \
  pyyaml aiohttp fastapi "uvicorn[standard]" \
  ollama click chromadb json_repair \
  --user 2>/dev/null || true) \
  & spinner $! "Installing Python dependencies"
wait $! 2>/dev/null || warn "Some Python packages may have failed"
ok "pyyaml  fastapi  chromadb  ollama  json_repair"

# ── Bootstrap ─────────────────────────────────────────────────────────────────
step "Bootstrapping Nexus"

(python3 -m bootstrap.bootstrap --profile "$PROFILE" --yes 2>/dev/null) \
  & spinner $! "Running bootstrap ($PROFILE profile)"
wait $! || die "Bootstrap failed. Run: cd $INSTALL_DIR && python3 -m bootstrap.bootstrap"
ok "Bootstrap complete"

# ── Pull model ────────────────────────────────────────────────────────────────
step "Pulling AI model"

if [ "$SKIP_MODEL" = "true" ]; then
  warn "Skipping model pull (SKIP_MODEL=true)"
else
  MODEL="qwen2.5:7b"
  info "Pulling $MODEL (~4.7GB) — showing live progress..."
  echo ""

  if ! curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
    nohup ollama serve >/dev/null 2>&1 & sleep 4
  fi

  ollama pull "$MODEL" 2>&1 | while IFS= read -r line; do
    printf "    ${D}%s${RESET}\n" "$line"
  done

  echo ""
  ok "Model ready: $MODEL (4.7GB · GPU · offline)"
fi

# ── Install clawos command ────────────────────────────────────────────────────
step "Installing clawos command"

mkdir -p "$HOME/.local/bin"

cat > "$HOME/.local/bin/nexus" << CMD
#!/bin/bash
export PYTHONPATH="${INSTALL_DIR}"
exec python3 "${INSTALL_DIR}/nexus/cli.py" "\$@"
CMD
chmod +x "$HOME/.local/bin/nexus"

cat > "$HOME/.local/bin/clawos" << CMD
#!/bin/bash
export PYTHONPATH="${INSTALL_DIR}"
exec python3 "${INSTALL_DIR}/clients/cli/repl.py" "\$@"
CMD
chmod +x "$HOME/.local/bin/clawos"

cat > "$HOME/.local/bin/clawctl" << CMD
#!/bin/bash
export PYTHONPATH="${INSTALL_DIR}"
exec python3 "${INSTALL_DIR}/clawctl/main.py" "\$@"
CMD
chmod +x "$HOME/.local/bin/clawctl"

_add_to_path() {
  local f="$1"
  [ -f "$f" ] && ! grep -q '.local/bin' "$f" 2>/dev/null \
    && echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$f"
}
_add_to_path "$HOME/.bashrc"
_add_to_path "$HOME/.zshrc"
_add_to_path "$HOME/.profile"
export PATH="$HOME/.local/bin:$PATH"
ok "clawos  clawctl"

# ── Autostart ─────────────────────────────────────────────────────────────────
step "Enabling autostart"

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
  ok "Ollama starts on boot"
else
  info "systemd not available — start manually: ollama serve"
fi

# ── First-run wizard ──────────────────────────────────────────────────────────
ELAPSED=$((SECONDS - START_TIME))
echo ""
divider
echo ""
echo -e "  ${G}${BOLD}✓  ClawOS installed in ${ELAPSED}s${RESET}"
echo ""
divider
echo ""

WIZARD_STATE="${HOME}/clawos/config/wizard_state.json"

if [ ! -f "$WIZARD_STATE" ]; then
  echo -e "  ${W}${BOLD}Starting first-run setup wizard...${RESET}"
  echo -e "  ${D}Sets up your workspace, voice, and AI runtime preferences.${RESET}"
  echo ""
  sleep 1
  cd "$INSTALL_DIR"
  export PYTHONPATH="$INSTALL_DIR"
  python3 -m setup.first_run.wizard
else
  # Re-install / update case — wizard already completed, just show quick start
  echo -e "  ${W}${BOLD}Mode 1  —  Offline chat (works right now)${RESET}"
  echo ""
  echo -e "  ${B}  nexus${RESET}"
  echo ""
  echo -e "  ${D}  Nexus · qwen2.5:7b · fully local · no account needed${RESET}"
  echo ""
  divider
  echo ""
  echo -e "  ${W}${BOLD}Mode 2  —  Full OpenClaw power (free, Kimi k2.5)${RESET}"
  echo ""
  echo -e "  ${D}  Sign in to Ollama once — free cloud model, 256k context:${RESET}"
  echo ""
  echo -e "  ${B}  ollama signin${RESET}"
  echo -e "  ${B}  ollama launch openclaw --model kimi-k2.5:cloud${RESET}"
  echo ""
  echo -e "  ${D}  OpenClaw · Kimi k2.5 · 13,700+ skills · WhatsApp · free tier${RESET}"
  echo ""
  divider
  echo ""
  echo -e "  ${W}${BOLD}Connect WhatsApp${RESET}"
  echo ""
  echo -e "  ${B}  openclaw configure --section channels${RESET}"
  echo ""
  divider
  echo ""
  echo -e "  ${D}  Re-run wizard:  ${RESET}${B}clawos /setup${RESET}${D}  or  ${RESET}${B}python3 -m setup.first_run.wizard --reset${RESET}"
  echo -e "  ${D}  Reload shell:   ${RESET}${B}source ~/.bashrc${RESET}"
  echo -e "  ${D}  GitHub:         ${RESET}${D}github.com/xbrxr03/clawos${RESET}"
  echo ""
fi
