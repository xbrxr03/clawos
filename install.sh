#!/usr/bin/env bash
# ClawOS — one-command installer
# curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh -o /tmp/clawos.sh && bash /tmp/clawos.sh

set -uo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
  BOLD="\033[1m"; RESET="\033[0m"
  G="\033[38;5;84m"; R="\033[38;5;203m"; B="\033[38;5;75m"
  P="\033[38;5;141m"; D="\033[2m\033[38;5;245m"
  Y="\033[38;5;220m"; W="\033[38;5;255m"
else
  BOLD=""; RESET=""; G=""; R=""; B=""; P=""; D=""; Y=""; W=""
fi

# ── Helpers ───────────────────────────────────────────────────────────────────
divider() { echo -e "${D}  ──────────────────────────────────────────────────────${RESET}"; }
step()    { echo -e "\n${B}${BOLD}  ◆${RESET}  ${W}${BOLD}$1${RESET}"; }
ok()      { echo -e "  ${G}✓${RESET}  $1"; }
info()    { echo -e "  ${D}·  $1${RESET}"; }
warn()    { echo -e "  ${Y}▲${RESET}  ${Y}$1${RESET}"; }
die()     { echo -e "\n  ${R}✗  $1${RESET}\n"; exit 1; }

spinner() {
  local pid=$1
  local msg=$2
  local frames=("⠋" "⠙" "⠹" "⠸" "⠼" "⠴" "⠦" "⠧" "⠇" "⠏")
  local i=0
  while kill -0 "$pid" 2>/dev/null; do
    printf "\r  ${B}${frames[$i]}${RESET}  ${D}%s${RESET}   " "$msg"
    i=$(( (i + 1) % ${#frames[@]} ))
    sleep 0.08
  done
  printf "\r\033[K"
}

run_with_spinner() {
  local msg=$1
  shift
  ("$@") >/tmp/clawos-install.$$ 2>&1 &
  local pid=$!
  spinner "$pid" "$msg"
  wait "$pid"
  local status=$?
  if [ "$status" -ne 0 ]; then
    sed 's/^/    /' /tmp/clawos-install.$$ >&2
  fi
  rm -f /tmp/clawos-install.$$
  return "$status"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Required command missing: $1"
}

systemd_user_ready() {
  command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1
}

ensure_path_line() {
  local file=$1
  [ -f "$file" ] || touch "$file"
  grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$file" 2>/dev/null || \
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$file"
}

write_file_if_changed() {
  local path=$1
  local mode=$2
  local tmp
  tmp="$(mktemp)"
  cat > "$tmp"
  if [ ! -f "$path" ] || ! cmp -s "$tmp" "$path"; then
    mkdir -p "$(dirname "$path")"
    cp "$tmp" "$path"
    chmod "$mode" "$path"
  fi
  rm -f "$tmp"
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

# ── Ollama account prompt (required for Kimi K2.5) ───────────────────────────
if [ -t 0 ] && [ -t 1 ]; then
  echo -e "  ${W}${BOLD}Before we begin — Ollama account required${RESET}"
  echo ""
  echo -e "  ClawOS comes with ${B}Kimi K2.5${RESET} — a free cloud AI model."
  echo -e "  You need a free Ollama account to use it."
  echo ""
  echo -e "  ${B}  → https://ollama.com/signup${RESET}"
  echo ""
  echo -e "  Sign up (or log in) in your browser, then come back here."
  echo -e "  ${D}  Press Enter when ready, or Ctrl+C to cancel.${RESET}"
  echo ""
  read -r _OLLAMA_READY
fi

# ── Config ────────────────────────────────────────────────────────────────────
CLAWOS_REPO="${CLAWOS_REPO:-https://github.com/xbrxr03/clawos}"
INSTALL_DIR="${CLAWOS_DIR:-$HOME/clawos}"
CLAWOS_BRANCH="${CLAWOS_BRANCH:-main}"
SKIP_MODEL="${SKIP_MODEL:-false}"
OPENCLAW_GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
MIN_RAM_GB=7
START_TIME=$SECONDS
MODEL=""
MODEL_SIZE=""
MODEL_NOTE=""

# ── Preflight ─────────────────────────────────────────────────────────────────
step "Checking your system"

if [ -f /etc/os-release ]; then
  . /etc/os-release
  case "$ID" in
    ubuntu|debian|raspbian|linuxmint|pop) ok "OS: $PRETTY_NAME" ;;
    *) warn "Untested OS: $ID — proceeding anyway" ;;
  esac
fi

if [ -f /proc/meminfo ]; then
  RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
  RAM_GB=$((RAM_KB / 1024 / 1024))
elif command -v sysctl >/dev/null 2>&1; then
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

require_cmd python3
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
ok "Python $PY_VER"

ARCH=$(uname -m)
case "$ARCH" in
  aarch64|armv7l|armv8l) IS_ARM=true ;;
  *) IS_ARM=false ;;
esac

# Detect GPU VRAM for Tier D
VRAM_GB=0
if command -v nvidia-smi &>/dev/null; then
  VRAM_GB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null     | awk '{printf "%.0f", $1/1024}' || echo 0)
fi

if [ "${VRAM_GB:-0}" -ge 10 ] && [ "$RAM_GB" -ge 30 ]; then
  PROFILE="gaming"; TIER="Tier D  GPU gaming workstation (${VRAM_GB}GB VRAM)"
elif [ "$RAM_GB" -ge 30 ]; then
  PROFILE="performance"; TIER="Tier C  GPU workstation"
elif [ "$RAM_GB" -ge 14 ]; then
  PROFILE="balanced"; TIER="Tier B  workstation"
else
  PROFILE="lowram"; TIER="Tier A  mini PC / ARM"
fi

if [ "$IS_ARM" = "true" ] && [ "$PROFILE" != "lowram" ]; then
  PROFILE="lowram"
  TIER="Tier A  ARM device"
  warn "ARM CPU detected — using lightweight model for faster local responses"
fi
ok "Hardware: $TIER"

# Export tier letter for wizard and bootstrap
case "$PROFILE" in
  lowram)      TIER_LETTER="A" ;;
  balanced)    TIER_LETTER="B" ;;
  performance) TIER_LETTER="C" ;;
  gaming)      TIER_LETTER="C" ;;
  *)           TIER_LETTER="B" ;;
esac
export CLAWOS_DETECTED_TIER="$TIER_LETTER"

# Set runtime bundle based on tier (can be overridden with CLAWOS_RUNTIMES env)
CLAWOS_RUNTIMES="${CLAWOS_RUNTIMES:-}"
if [ -z "$CLAWOS_RUNTIMES" ]; then
  case "$PROFILE" in
    lowram)      CLAWOS_RUNTIMES="nexus,picoclaw" ;;
    balanced)    CLAWOS_RUNTIMES="nexus,picoclaw,openclaw" ;;
    performance) CLAWOS_RUNTIMES="nexus,picoclaw,openclaw" ;;
    gaming)      CLAWOS_RUNTIMES="nexus,picoclaw,openclaw" ;;
  esac
fi
export CLAWOS_RUNTIMES

case "$PROFILE" in
  lowram)
    MODEL="qwen2.5:1.5b"
    MODEL_SIZE="~1.1GB"
    MODEL_NOTE="ARM/CPU optimised"
    ;;
  balanced)
    MODEL="qwen2.5:3b"
    MODEL_SIZE="~2.0GB"
    MODEL_NOTE="balanced speed/quality"
    ;;
  gaming)
    MODEL="qwen2.5:7b"
    MODEL_SIZE="~4.7GB"
    MODEL_NOTE="full capability · GPU · multi-agent Tier D"
    ;;
  performance)
    MODEL="qwen2.5:7b"
    MODEL_SIZE="~4.7GB"
    MODEL_NOTE="full capability · GPU"
    ;;
  *)
    MODEL="qwen2.5:3b"
    MODEL_SIZE="~2.0GB"
    MODEL_NOTE="balanced speed/quality"
    ;;
esac

if [ -n "${CLAWOS_MODEL:-}" ]; then
  MODEL="$CLAWOS_MODEL"
  MODEL_SIZE="custom"
  MODEL_NOTE="from CLAWOS_MODEL env"
fi

# ── System packages ───────────────────────────────────────────────────────────
step "Installing system packages"

run_with_spinner "Updating apt and installing dependencies" \
  bash -lc 'sudo apt-get update -qq && sudo apt-get install -y -qq python3-pip python3-venv git curl wget sqlite3 ca-certificates'
ok "git  curl  sqlite3  python3-pip"

# ── Ollama ────────────────────────────────────────────────────────────────────
step "Setting up Ollama"

if command -v ollama >/dev/null 2>&1; then
  ok "Ollama already installed"
else
  run_with_spinner "Downloading and installing Ollama" \
    bash -lc 'curl -fsSL https://ollama.com/install.sh | sh'
  ok "Ollama installed"
fi

OLLAMA_BIN="$(command -v ollama || true)"
[ -n "$OLLAMA_BIN" ] || die "Ollama install finished but binary was not found in PATH"

# ── Ollama login (required for cloud models like Kimi K2.5) ──────────────────
OLLAMA_LOGGED_IN=false
if [ -t 0 ] && [ -t 1 ]; then
  step "Sign in to Ollama"
  echo ""
  echo -e "  ${W}${BOLD}Kimi K2.5 runs on Ollama's cloud — sign in to unlock it.${RESET}"
  echo -e "  ${D}A link will appear below. Open it, create a free account, then${RESET}"
  echo -e "  ${D}return here. Press Ctrl+C at any time to skip and use local models.${RESET}"
  echo ""
  if "$OLLAMA_BIN" login 2>&1; then
    OLLAMA_LOGGED_IN=true
    ok "Signed in to Ollama"
  else
    warn "Ollama login skipped — OpenClaw will use local model instead"
  fi
fi

if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  nohup "$OLLAMA_BIN" serve >/dev/null 2>&1 &
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    sleep 1
    curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
  done
fi

curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1 \
  && ok "Ollama server running" \
  || warn "Ollama not responding yet — user service will still be installed"

# ── Node.js ───────────────────────────────────────────────────────────────────
step "Installing Node.js"

if command -v node >/dev/null 2>&1; then
  ok "Node.js $(node --version) already installed"
else
  run_with_spinner "Installing Node.js LTS" \
    bash -lc 'curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && sudo apt-get install -y -qq nodejs'
  ok "Node.js $(node --version)"
fi

# ── OpenClaw ──────────────────────────────────────────────────────────────────
step "Installing OpenClaw"

OPENCLAW_OK=false
if ! command -v node >/dev/null 2>&1; then
  warn "Skipping OpenClaw — Node.js not available"
else
  if command -v openclaw >/dev/null 2>&1; then
    ok "OpenClaw already installed"
    OPENCLAW_OK=true
  else
    if [ -d "/usr/lib/node_modules" ]; then sudo chmod -R 755 /usr/lib/node_modules 2>/dev/null || true; fi
    if run_with_spinner "Installing OpenClaw via npm" sudo npm install -g openclaw@latest --quiet; then
      :
    elif run_with_spinner "Retrying OpenClaw install (user scope)" npm install -g openclaw@latest --quiet; then
      :
    else
      warn "OpenClaw install failed"
    fi

    if command -v openclaw >/dev/null 2>&1 && openclaw --version >/dev/null 2>&1; then
      ok "OpenClaw installed"
      OPENCLAW_OK=true
    else
      warn "OpenClaw binary not found after install"
    fi
  fi
fi

# ── Clone ClawOS ──────────────────────────────────────────────────────────────
step "Installing Nexus"

if [ -d "$INSTALL_DIR/clawos_core" ]; then
  ok "Nexus already present at $INSTALL_DIR"
elif [ -d "$INSTALL_DIR/.git" ]; then
  run_with_spinner "Updating existing install" git -C "$INSTALL_DIR" pull --ff-only -q || \
    warn "Git pull failed — using existing version"
  ok "Nexus updated"
else
  run_with_spinner "Cloning from GitHub" \
    git clone -q --branch "$CLAWOS_BRANCH" --depth 1 "$CLAWOS_REPO" "$INSTALL_DIR"
  ok "Nexus cloned to $INSTALL_DIR"
fi

cd "$INSTALL_DIR" || die "Install directory not found after clone: $INSTALL_DIR"
export PYTHONPATH="$INSTALL_DIR"

# ── Python packages ───────────────────────────────────────────────────────────
step "Installing Python packages"

PYTHON_PACKAGES=(
  pyyaml aiohttp fastapi "uvicorn[standard]"
  ollama click chromadb json_repair
  pypdf python-docx aiofiles httpx gitpython rich openai-whisper
)

if run_with_spinner "Installing Python dependencies" \
  python3 -m pip install -q "${PYTHON_PACKAGES[@]}" --break-system-packages; then
  :
elif run_with_spinner "Retrying Python install in user scope" \
  python3 -m pip install -q "${PYTHON_PACKAGES[@]}" --user; then
  :
else
  warn "Some Python packages may have failed"
fi
ok "pyyaml  fastapi  chromadb  ollama  json_repair  pypdf  python-docx"

# ── Bootstrap ─────────────────────────────────────────────────────────────────
step "Bootstrapping Nexus"

# Optional: prompt for OpenRouter key during non-interactive curl|bash installs
if [ -t 0 ] && [ -z "${OPENROUTER_API_KEY:-}" ]; then
  step "API Keys (optional)"
  echo ""
  echo -e "  ${D}OpenRouter gives you 200+ cloud models including Kimi k2.5.${RESET}"
  echo -e "  ${D}Get a key at: https://openrouter.ai/keys${RESET}"
  echo -e "  ${D}Press Enter to skip and use local models only.${RESET}"
  echo ""
  read -s -p "  OpenRouter API key: " OPENROUTER_KEY
  echo ""
  if [ -n "$OPENROUTER_KEY" ]; then
    export OPENROUTER_API_KEY="$OPENROUTER_KEY"
    ok "OpenRouter key saved"
  else
    info "Skipped — using local models. Run 'nexus setup' to add keys later."
  fi
fi

run_with_spinner "Running bootstrap ($PROFILE profile)" \
  python3 -m bootstrap.bootstrap --profile "$PROFILE" --yes
ok "Bootstrap complete"

# ── Pull model ────────────────────────────────────────────────────────────────
step "Pulling AI model"

if [ "$SKIP_MODEL" = "true" ]; then
  warn "Skipping model pull (SKIP_MODEL=true)"
else
  OLLAMA_URL="${OLLAMA_HOST:-http://127.0.0.1:11434}"

  if [ "$OLLAMA_URL" != "http://localhost:11434" ] && [ "$OLLAMA_URL" != "http://127.0.0.1:11434" ]; then
    info "Remote Ollama detected: $OLLAMA_URL"
    info "Skipping local model pull — model '$MODEL' must exist on remote server"
    info "Run on remote:  ollama pull $MODEL"
    ok "Remote Ollama configured: $OLLAMA_URL"
  else
    info "Pulling $MODEL ($MODEL_SIZE) — $MODEL_NOTE..."
    echo ""
    "$OLLAMA_BIN" pull "$MODEL" 2>&1 | while IFS= read -r line; do
      printf "    ${D}%s${RESET}\n" "$line"
    done
    echo ""
    ok "Model ready: $MODEL ($MODEL_SIZE · $MODEL_NOTE · offline)"
  fi
fi

# ── Pull embedding model ──────────────────────────────────────────────────────
step "Pulling embedding model"

if [ "$SKIP_MODEL" = "true" ]; then
  warn "Skipping embedding model pull (SKIP_MODEL=true)"
else
  EMBED_MODEL="nomic-embed-text"
  OLLAMA_URL="${OLLAMA_HOST:-http://127.0.0.1:11434}"

  if [ "$OLLAMA_URL" != "http://localhost:11434" ] && [ "$OLLAMA_URL" != "http://127.0.0.1:11434" ]; then
    info "Remote Ollama — skipping embedding model pull"
    info "Run on remote:  ollama pull $EMBED_MODEL"
  elif ! curl -sf "$OLLAMA_URL/api/tags" 2>/dev/null | grep -q '"name":"nomic-embed-text'; then
    info "Pulling $EMBED_MODEL (~274MB) — needed for document RAG..."
    echo ""
    "$OLLAMA_BIN" pull "$EMBED_MODEL" 2>&1 | while IFS= read -r line; do
      printf "    ${D}%s${RESET}\n" "$line"
    done
    echo ""
    ok "Embedding model ready: $EMBED_MODEL"
  else
    ok "Embedding model already present: $EMBED_MODEL"
  fi
fi

# ── Pull Kimi K2.5 (cloud model via Ollama) ──────────────────────────────────
OPENCLAW_MODEL="$MODEL"   # default: local model
if [ "$OLLAMA_LOGGED_IN" = "true" ]; then
  step "Registering Kimi K2.5"
  info "Kimi K2.5 streams from Ollama's cloud — no large local download."
  echo ""
  if "$OLLAMA_BIN" pull kimi-k2.5:cloud 2>&1 | while IFS= read -r line; do
    printf "    ${D}%s${RESET}\n" "$line"
  done; then
    OPENCLAW_MODEL="kimi-k2.5:cloud"
    ok "Kimi K2.5 ready — OpenClaw will use it as its model"
  else
    warn "Could not register Kimi K2.5 — OpenClaw will use local model ($MODEL)"
  fi
fi

# ── Configure OpenClaw ────────────────────────────────────────────────────────
step "Configuring OpenClaw"

if [ "$OPENCLAW_OK" = "true" ]; then
  mkdir -p "$HOME/.openclaw" "$HOME/.openclaw/agents/main/sessions"

  write_file_if_changed "$HOME/.openclaw/openclaw.json" 600 <<EOF
{
  "gateway": {
    "mode": "local"
  },
  "models": {
    "providers": {
      "ollama": {
        "baseUrl": "http://127.0.0.1:11434",
        "models": [
          {
            "id": "$OPENCLAW_MODEL",
            "name": "$OPENCLAW_MODEL",
            "contextWindow": 262144
          },
          {
            "id": "$MODEL",
            "name": "$MODEL (local fallback)",
            "contextWindow": 32768
          },
          {
            "id": "nomic-embed-text",
            "name": "nomic-embed-text",
            "contextWindow": 8192
          }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "ollama/$OPENCLAW_MODEL"
      },
      "memorySearch": {
        "enabled": false
      }
    }
  }
}
EOF

  ok "OpenClaw configured — model: $OPENCLAW_MODEL"
  ok "OpenClaw config permissions tightened"
  ok "OpenClaw session store ready"
else
  warn "Skipping OpenClaw config — binary is not installed"
fi

# ── Install clawos command ────────────────────────────────────────────────────
step "Installing clawos command"

mkdir -p "$HOME/.local/bin"

write_file_if_changed "$HOME/.local/bin/nexus" 755 <<EOF
#!/usr/bin/env bash
export PYTHONPATH="${INSTALL_DIR}"
exec python3 "${INSTALL_DIR}/nexus/cli.py" "\$@"
EOF

write_file_if_changed "$HOME/.local/bin/clawos" 755 <<EOF
#!/usr/bin/env bash
export PYTHONPATH="${INSTALL_DIR}"
exec python3 "${INSTALL_DIR}/clients/cli/repl.py" "\$@"
EOF

write_file_if_changed "$HOME/.local/bin/clawctl" 755 <<EOF
#!/usr/bin/env bash
export PYTHONPATH="${INSTALL_DIR}"
exec python3 "${INSTALL_DIR}/clawctl/main.py" "\$@"
EOF

ensure_path_line "$HOME/.bashrc"
ensure_path_line "$HOME/.zshrc"
ensure_path_line "$HOME/.profile"
export PATH="$HOME/.local/bin:$PATH"
ok "clawos  clawctl"

# ── Autostart ─────────────────────────────────────────────────────────────────

# ── PicoClaw (Tier A ARM only) ────────────────────────────────────────────────
if [ "$IS_ARM" = "true" ] && [ "$PROFILE" = "lowram" ]; then
  step "Installing PicoClaw edge runtime (Tier A ARM)"
  PICOCLAW_ARCH="arm64"
  case "$(uname -m)" in
    armv7l|armv8l|armhf) PICOCLAW_ARCH="arm32" ;;
    aarch64|arm64)        PICOCLAW_ARCH="arm64" ;;
    riscv64)              PICOCLAW_ARCH="riscv64" ;;
  esac
  PICOCLAW_URL="https://github.com/sipeed/picoclaw/releases/download/v0.2.4/picoclaw-linux-${PICOCLAW_ARCH}"
  if command -v picoclaw &>/dev/null; then
    ok "PicoClaw already installed"
  else
    run_with_spinner "Downloading PicoClaw (${PICOCLAW_ARCH})" \
      wget -q -O /tmp/picoclaw "$PICOCLAW_URL" && \
      sudo mv /tmp/picoclaw /usr/local/bin/picoclaw && \
      sudo chmod +x /usr/local/bin/picoclaw
    if command -v picoclaw &>/dev/null; then
      ok "PicoClaw installed"
    else
      warn "PicoClaw download failed — will retry on first boot"
    fi
  fi
  mkdir -p "$HOME/.picoclaw"
  cat > "$HOME/.picoclaw/config.json" <<'PCEOF'
{
  "provider": "ollama",
  "endpoint": "http://localhost:11434",
  "model": "qwen2.5:1.5b",
  "timeout": 300
}
PCEOF
  ok "PicoClaw configured"
fi

step "Enabling autostart"

if systemd_user_ready; then
  mkdir -p "$HOME/.config/systemd/user"

  write_file_if_changed "$HOME/.config/systemd/user/ollama.service" 644 <<EOF
[Unit]
Description=Ollama AI Runtime
After=network.target

[Service]
ExecStart=${OLLAMA_BIN} serve
Restart=always
RestartSec=3
Environment=HOME=${HOME}

[Install]
WantedBy=default.target
EOF

  # Kill any background ollama started with nohup so systemd can own the port cleanly
  pkill -f "ollama serve" >/dev/null 2>&1 || true
  sleep 1

  systemctl --user daemon-reload
  systemctl --user enable ollama.service >/dev/null 2>&1 || true
  systemctl --user restart ollama.service >/dev/null 2>&1 || true
  # Wait for ollama to be ready before continuing
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    sleep 1
    curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
  done
  ok "Ollama starts on boot"

  bash "${INSTALL_DIR}/scripts/setup-systemd.sh" >/dev/null 2>&1 && ok "ClawOS starts on boot" || warn "ClawOS autostart setup failed"
  systemctl --user restart clawos.service >/dev/null 2>&1 && ok "ClawOS service started" || warn "Start manually: systemctl --user start clawos.service"

  if [ "$OPENCLAW_OK" = "true" ]; then
    OPENCLAW_BIN="$(command -v openclaw)"
    write_file_if_changed "$HOME/.config/systemd/user/openclaw-gateway.service" 644 <<EOF
[Unit]
Description=OpenClaw Gateway
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
ExecStart=${OPENCLAW_BIN} gateway --port ${OPENCLAW_GATEWAY_PORT}
Restart=always
RestartSec=5
Environment=HOME=${HOME}

[Install]
WantedBy=default.target
EOF

    if [ -f "$HOME/.config/systemd/user/clawos-gatewayd.service" ]; then
      systemctl --user disable --now clawos-gatewayd.service >/dev/null 2>&1 || true
      ok "Disabled duplicate ClawOS gateway unit"
    fi

    systemctl --user daemon-reload
    systemctl --user enable openclaw-gateway.service >/dev/null 2>&1 || true
    systemctl --user restart openclaw-gateway.service >/dev/null 2>&1 || true

    if systemctl --user is-active --quiet openclaw-gateway.service; then
      ok "OpenClaw gateway starts on boot"
      ok "OpenClaw gateway service started"
    else
      warn "OpenClaw gateway service did not stay up — check: journalctl --user -u openclaw-gateway.service -n 100 --no-pager"
    fi
  fi
else
  info "systemd user session not available — start manually: ollama serve"
  if [ "$OPENCLAW_OK" = "true" ]; then
    info "Start OpenClaw gateway manually: openclaw gateway --port ${OPENCLAW_GATEWAY_PORT}"
  fi
fi

# ── Final verification ────────────────────────────────────────────────────────
step "Final verification"

command -v clawos >/dev/null 2>&1 && ok "clawos command available"
if [ "$OPENCLAW_OK" = "true" ]; then
  command -v openclaw >/dev/null 2>&1 && ok "openclaw command available"
  openclaw --version >/dev/null 2>&1 && ok "OpenClaw version check passed"
fi

curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1 \
  && ok "Ollama API reachable" \
  || warn "Ollama API not reachable yet"

if systemd_user_ready; then
  systemctl --user is-active --quiet clawos.service \
    && ok "clawos.service active" \
    || warn "clawos.service is not active"

  if [ "$OPENCLAW_OK" = "true" ]; then
    systemctl --user is-active --quiet openclaw-gateway.service \
      && ok "openclaw-gateway.service active" \
      || warn "openclaw-gateway.service is not active"
  fi
fi

# ── First-run summary ─────────────────────────────────────────────────────────
ELAPSED=$((SECONDS - START_TIME))
echo ""
divider
echo ""
echo -e "  ${G}${BOLD}✓  ClawOS installed in ${ELAPSED}s${RESET}"
echo ""
divider
echo ""

echo -e "  ${W}${BOLD}Ready now${RESET}"
echo ""

echo -e "  ${B}  clawos${RESET}"
echo -e "  ${D}  Native ClawOS runtime · ${MODEL} · fully local${RESET}"
echo ""

if [ "$OPENCLAW_OK" = "true" ]; then
  echo -e "  ${B}  openclaw tui${RESET}"
  echo -e "  ${D}  OpenClaw TUI · gateway local:${OPENCLAW_GATEWAY_PORT} · model ${OPENCLAW_MODEL}${RESET}"
  echo ""
  echo -e "  ${B}  openclaw configure --section channels${RESET}"
  echo -e "  ${D}  Connect WhatsApp or other channels${RESET}"
  echo ""
fi

echo -e "  ${B}  nexus use-kimi${RESET}"
echo -e "  ${D}  Switch OpenClaw to Kimi K2.5 (Ollama account required)${RESET}"
echo ""
echo -e "  ${D}  Reload shell if needed:  ${RESET}${B}source ~/.bashrc${RESET}"
echo -e "  ${D}  Re-run wizard:           ${RESET}${B}python3 -m setup.first_run.wizard --reset${RESET}"

# ── Launch wizard if running interactively ────────────────────────────────────
if [ -t 0 ] && [ -t 1 ]; then
  echo ""
  echo -e "  ${B}Starting setup wizard...${RESET}"
  echo ""
  cd "${INSTALL_DIR}" && python3 -m setup.first_run.wizard
else
  echo ""
  echo -e "  ${D}  Non-interactive install detected.${RESET}"
  echo -e "  ${D}  Run the setup wizard manually:  ${RESET}${B}nexus setup${RESET}"
  echo ""
fi
echo -e "  ${D}  GitHub:                  ${RESET}${D}github.com/xbrxr03/clawos${RESET}"
echo ""

# ── Ensure ollama + gateway are fresh before TUI launch ──────────────────────
if [ "$OLLAMA_LOGGED_IN" = "true" ] && systemd_user_ready; then
  systemctl --user restart ollama.service >/dev/null 2>&1 || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    sleep 1
    curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
  done
  systemctl --user restart openclaw-gateway.service >/dev/null 2>&1 || true
  sleep 3
fi

# ── Launch OpenClaw TUI (Kimi K2.5 first response) ───────────────────────────
if [ -t 0 ] && [ -t 1 ] && [ "$OPENCLAW_OK" = "true" ] && [ "$OLLAMA_LOGGED_IN" = "true" ]; then
  divider
  echo ""
  echo -e "  ${G}${BOLD}Launching OpenClaw · Kimi K2.5${RESET}"
  echo -e "  ${D}Your AI is ready. Type anything to start.${RESET}"
  echo ""
  sleep 1
  openclaw tui
fi