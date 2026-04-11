#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# ClawOS one-command installer
# curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh -o /tmp/clawos.sh && bash /tmp/clawos.sh

set -uo pipefail

if [ -t 1 ]; then
  BOLD="\033[1m"; RESET="\033[0m"
  G="\033[38;5;84m"; R="\033[38;5;203m"; B="\033[38;5;75m"
  P="\033[38;5;141m"; D="\033[2m\033[38;5;245m"
  Y="\033[38;5;220m"; W="\033[38;5;255m"
else
  BOLD=""; RESET=""; G=""; R=""; B=""; P=""; D=""; Y=""; W=""
fi

divider() { echo -e "${D}  --------------------------------------------------------${RESET}"; }
step()    { echo -e "\n${B}${BOLD}  >${RESET}  ${W}${BOLD}$1${RESET}"; }
ok()      { echo -e "  ${G}✓${RESET}   $1"; }
info()    { echo -e "  ${D}..  $1${RESET}"; }
warn()    { echo -e "  ${Y}!!${RESET}  ${Y}$1${RESET}"; }
die()     { echo -e "\n  ${R}XX${RESET}  $1\n"; exit 1; }

spinner() {
  local pid=$1
  local msg=$2
  local frames=("|" "/" "-" "\\")
  local i=0
  while kill -0 "$pid" 2>/dev/null; do
    printf "\r  ${B}%s${RESET}  ${D}%s${RESET}   " "${frames[$i]}" "$msg"
    i=$(( (i + 1) % ${#frames[@]} ))
    sleep 0.1
  done
  printf "\r\033[K"
}

run_with_spinner() {
  local msg=$1
  shift
  local tmp
  tmp="$(mktemp)"
  ("$@") >"$tmp" 2>&1 &
  local pid=$!
  spinner "$pid" "$msg"
  wait "$pid"
  local status=$?
  if [ "$status" -ne 0 ]; then
    sed 's/^/    /' "$tmp" >&2
  fi
  rm -f "$tmp"
  return "$status"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Required command missing: $1"
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

ensure_path_line() {
  local file=$1
  [ -f "$file" ] || touch "$file"
  grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$file" 2>/dev/null || \
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$file"
}

systemd_user_ready() {
  command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1
}

platform_name() {
  case "$PLATFORM" in
    macos) echo "macOS" ;;
    linux) echo "Linux" ;;
    *) echo "$PLATFORM" ;;
  esac
}

refresh_shell_env() {
  if [ "$PLATFORM" = "macos" ] && [ -n "${BREW_BIN:-}" ]; then
    eval "$("$BREW_BIN" shellenv)"
  fi
  hash -r 2>/dev/null || true
}

detect_ollama_bin() {
  local bin
  bin="$(command -v ollama 2>/dev/null || true)"
  if [ -n "$bin" ]; then
    echo "$bin"
    return 0
  fi

  for candidate in \
    /opt/homebrew/bin/ollama \
    /usr/local/bin/ollama \
    /usr/bin/ollama \
    "$HOME/.local/bin/ollama" \
    /Applications/Ollama.app/Contents/Resources/ollama
  do
    if [ -x "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done

  return 1
}

ensure_homebrew() {
  if [ "$PLATFORM" != "macos" ]; then
    return 0
  fi

  BREW_BIN="$(command -v brew 2>/dev/null || true)"
  if [ -z "$BREW_BIN" ]; then
    step "Installing Homebrew"
    info "Homebrew is the supported package path for macOS dependencies."
    run_with_spinner "Running Homebrew installer" \
      bash -lc 'tmp="$(mktemp /tmp/clawos-homebrew.XXXXXX.sh)" && curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh -o "$tmp" && NONINTERACTIVE=1 /bin/bash "$tmp" && rm -f "$tmp"' \
      || die "Homebrew install failed"
    BREW_BIN="$(command -v brew 2>/dev/null || true)"
    if [ -z "$BREW_BIN" ]; then
      for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
        if [ -x "$candidate" ]; then
          BREW_BIN="$candidate"
          break
        fi
      done
    fi
  fi

  [ -n "$BREW_BIN" ] || die "Homebrew was installed but brew is still not on PATH"
  refresh_shell_env
  ok "Homebrew ready ($BREW_BIN)"
}

install_system_packages() {
  step "Installing system packages"

  if [ "$PLATFORM" = "linux" ]; then
    run_with_spinner "Updating apt and installing dependencies" \
      bash -lc 'sudo apt-get update -qq && sudo apt-get install -y -qq python3 python3-pip python3-venv git curl wget sqlite3 ca-certificates' \
      || die "Failed to install Linux dependencies"
    ok "git  curl  sqlite3  python3-pip"
    return 0
  fi

  ensure_homebrew
  run_with_spinner "Updating Homebrew" "$BREW_BIN" update || warn "brew update failed - continuing"
  run_with_spinner "Installing Homebrew packages" \
    bash -lc 'for pkg in git sqlite python node wget ollama; do brew list --formula "$pkg" >/dev/null 2>&1 || brew install "$pkg"; done' \
    || die "Failed to install macOS dependencies"
  refresh_shell_env
  ok "brew packages ready: git  sqlite  python  node  ollama"
}

install_ollama() {
  step "Setting up Ollama"

  OLLAMA_BIN="$(detect_ollama_bin || true)"
  if [ -n "$OLLAMA_BIN" ]; then
    ok "Ollama already installed ($OLLAMA_BIN)"
  else
    if [ "$PLATFORM" = "macos" ] && [ -n "${BREW_BIN:-}" ]; then
      run_with_spinner "Installing Ollama with Homebrew" "$BREW_BIN" install ollama \
        || run_with_spinner "Falling back to Ollama installer" bash -lc 'tmp="$(mktemp /tmp/clawos-ollama.XXXXXX.sh)" && curl -fsSL https://ollama.com/install.sh -o "$tmp" && sh "$tmp" && rm -f "$tmp"' \
        || die "Ollama install failed"
    else
      run_with_spinner "Downloading Ollama" bash -lc 'tmp="$(mktemp /tmp/clawos-ollama.XXXXXX.sh)" && curl -fsSL https://ollama.com/install.sh -o "$tmp" && sh "$tmp" && rm -f "$tmp"' \
        || die "Ollama install failed"
    fi
    refresh_shell_env
    OLLAMA_BIN="$(detect_ollama_bin || true)"
  fi

  [ -n "$OLLAMA_BIN" ] || die "Ollama install finished but binary was not found"

  if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    nohup "$OLLAMA_BIN" serve >/dev/null 2>&1 &
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      sleep 1
      curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
    done
  fi

  curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1 \
    && ok "Ollama server running" \
    || warn "Ollama is installed but not responding yet"

  # Generate ~/.ollama/id_ed25519 — required for model pulls, created on first list call
  "$OLLAMA_BIN" list >/dev/null 2>&1 || true
}

install_node() {
  step "Installing Node.js"

  if command -v node >/dev/null 2>&1; then
    NODE_MAJOR=$(node --version | sed 's/v\([0-9]*\).*/\1/')
    if [ "${NODE_MAJOR}" -ge 22 ] 2>/dev/null; then
      ok "Node.js $(node --version) already installed"
      return 0
    fi
    warn "Node.js $(node --version) is too old (openclaw needs v22+) — upgrading"
  fi

  if [ "$PLATFORM" = "macos" ]; then
    ensure_homebrew
    run_with_spinner "Installing Node.js with Homebrew" "$BREW_BIN" install node \
      || die "Node.js install failed"
  else
    # Remove any old system nodejs (Ubuntu 24.04 ships v18, openclaw needs v22+)
    sudo apt-get remove -y nodejs npm 2>/dev/null || true
    run_with_spinner "Installing Node.js 22 via NodeSource" \
      bash -lc 'curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt-get install -y nodejs' \
      || die "Node.js install failed"
  fi

  refresh_shell_env
  command -v node >/dev/null 2>&1 || die "Node.js install finished but node is missing"
  ok "Node.js $(node --version)"
}

# OpenClaw is installed by 'ollama launch openclaw' at the end of the install.

install_python_packages() {
  step "Installing Python packages"

  PYTHON_PACKAGES=(
    pyyaml aiohttp fastapi "uvicorn[standard]"
    ollama click chromadb json_repair
    pypdf python-docx aiofiles httpx gitpython rich openai-whisper
  )

  if [ "$PLATFORM" = "macos" ]; then
    run_with_spinner "Installing Python packages" \
      python3 -m pip install -q "${PYTHON_PACKAGES[@]}" --user \
      || warn "Some Python packages may have failed"
  else
    if run_with_spinner "Installing Python packages" \
      python3 -m pip install -q "${PYTHON_PACKAGES[@]}" --break-system-packages; then
      :
    elif run_with_spinner "Retrying in user scope" \
      python3 -m pip install -q "${PYTHON_PACKAGES[@]}" --user; then
      :
    else
      warn "Some Python packages may have failed"
    fi
  fi

  ok "pyyaml  fastapi  chromadb  ollama  pypdf  python-docx"
}

build_command_center() {
  step "Building Command Center"

  if [ ! -d "$INSTALL_DIR/dashboard/frontend" ]; then
    warn "dashboard/frontend not found - skipping frontend build"
    return 0
  fi

  if ! command -v npm >/dev/null 2>&1; then
    warn "npm not found - skipping frontend build"
    return 0
  fi

  if run_with_spinner "Installing frontend dependencies" \
    bash -lc "cd \"$INSTALL_DIR/dashboard/frontend\" && npm install"; then
    :
  else
    warn "npm install failed - skipping frontend build"
    return 0
  fi

  if run_with_spinner "Building frontend bundle" \
    bash -lc "cd \"$INSTALL_DIR/dashboard/frontend\" && npm run build"; then
    ok "Command Center frontend built"
  else
    warn "Frontend build failed - dashd will use the bundled static assets if they are already present"
  fi
}

configure_openclaw() {
  step "Configuring OpenClaw"

  OPENCLAW_MODEL="kimi-k2.5:cloud"

  # Config is written now; openclaw binary is installed later by 'ollama launch'

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

  ok "OpenClaw configured"
}

install_wrapper_commands() {
  step "Installing command wrappers"

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

  write_file_if_changed "$HOME/.local/bin/clawos-command-center" 755 <<EOF
#!/usr/bin/env bash
export PYTHONPATH="${INSTALL_DIR}"
exec python3 "${INSTALL_DIR}/clients/desktop/launch_command_center.py" "\$@"
EOF

  write_file_if_changed "$HOME/.local/bin/clawos-setup" 755 <<EOF
#!/usr/bin/env bash
export PYTHONPATH="${INSTALL_DIR}"
exec python3 "${INSTALL_DIR}/clients/desktop/launch_command_center.py" --route /setup "\$@"
EOF

  ensure_path_line "$HOME/.bashrc"
  ensure_path_line "$HOME/.zshrc"
  ensure_path_line "$HOME/.zprofile"
  ensure_path_line "$HOME/.profile"
  export PATH="$HOME/.local/bin:$PATH"

  ok "clawos  clawctl  nexus  clawos-command-center  clawos-setup"
}

install_picoclaw_if_needed() {
  if ! echo "${CLAWOS_RUNTIMES}" | grep -q "picoclaw"; then
    return 0
  fi

  step "Installing PicoClaw lightweight runtime"

  if [ "$PLATFORM" = "macos" ]; then
    warn "Skipping PicoClaw on macOS - only Linux release binaries are published today"
    return 0
  fi

  if command -v picoclaw >/dev/null 2>&1; then
    ok "PicoClaw already installed"
  else
    case "$(uname -m)" in
      armv7l|armv8l|armhf) _PC_ARCH="armv7" ;;
      aarch64|arm64)        _PC_ARCH="arm64" ;;
      riscv64)              _PC_ARCH="riscv64" ;;
      x86_64|amd64)         _PC_ARCH="x86_64" ;;
      *)                    _PC_ARCH="x86_64" ;;
    esac

    _PC_VER="$(curl -fsSL https://api.github.com/repos/sipeed/picoclaw/releases/latest 2>/dev/null | grep '"tag_name"' | head -1 | sed 's/.*"v\([^"]*\)".*/\1/')"
    _PC_VER="${_PC_VER:-0.2.5}"
    _PC_URL="https://github.com/sipeed/picoclaw/releases/download/v${_PC_VER}/picoclaw_Linux_${_PC_ARCH}.tar.gz"

    if run_with_spinner "Downloading PicoClaw" bash -lc "tmp=\$(mktemp /tmp/picoclaw.XXXXXX.tar.gz) && curl -fsSL --max-time 30 '$_PC_URL' -o \"\$tmp\" && tar -xzf \"\$tmp\" -C /tmp picoclaw && rm -f \"\$tmp\""; then
      sudo mv /tmp/picoclaw /usr/local/bin/picoclaw && sudo chmod +x /usr/local/bin/picoclaw
    fi

    if command -v picoclaw >/dev/null 2>&1; then
      ok "PicoClaw installed"
    else
      warn "PicoClaw download failed - skipping"
      return 0
    fi
  fi

  mkdir -p "$HOME/.picoclaw"
  cat > "$HOME/.picoclaw/config.json" <<'EOF'
{
  "provider": "ollama",
  "endpoint": "http://localhost:11434",
  "model": "qwen2.5:3b",
  "timeout": 300
}
EOF
  ok "PicoClaw configured"
}

enable_autostart() {
  step "Enabling autostart"

  if [ "$PLATFORM" = "macos" ]; then
    OPENCLAW_BIN="$(command -v openclaw 2>/dev/null || true)"
    CLAWOS_HOME="$INSTALL_DIR" \
    CLAWOS_WORKSPACE="nexus_default" \
    PYTHON_BIN="$(command -v python3)" \
    OLLAMA_BIN="$OLLAMA_BIN" \
    OPENCLAW_BIN="$OPENCLAW_BIN" \
    OPENCLAW_GATEWAY_PORT="$OPENCLAW_GATEWAY_PORT" \
    bash "${INSTALL_DIR}/scripts/setup-launchd.sh" >/dev/null 2>&1 \
      && ok "launchd agents installed" \
      || warn "launchd install failed - run scripts/setup-launchd.sh manually"
    return 0
  fi

  if systemd_user_ready; then
    mkdir -p "$HOME/.config/systemd/user"

    write_file_if_changed "$HOME/.config/systemd/user/ollama.service" 644 <<EOF
[Unit]
Description=Ollama AI Runtime
After=network.target

[Service]
ExecStart=/bin/sh -c 'nc -z localhost 11434 2>/dev/null && exit 0; exec ${OLLAMA_BIN} serve'
Restart=on-failure
RestartSec=5
StartLimitBurst=3
StartLimitIntervalSec=30
Environment=HOME=${HOME}

[Install]
WantedBy=default.target
EOF

    systemctl --user daemon-reload
    systemctl --user enable ollama.service >/dev/null 2>&1 || true
    ok "Ollama starts on boot"

    bash "${INSTALL_DIR}/scripts/setup-systemd.sh" >/dev/null 2>&1 \
      && ok "ClawOS starts on boot" \
      || warn "ClawOS autostart setup failed"
    systemctl --user restart clawos.service >/dev/null 2>&1 \
      && ok "ClawOS service started" \
      || warn "Start manually: systemctl --user start clawos.service"
    sleep 5  # wait for sub-services to initialize before verify check

    if command -v openclaw >/dev/null 2>&1; then
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

      systemctl --user daemon-reload
      systemctl --user enable openclaw-gateway.service >/dev/null 2>&1 || true
      systemctl --user restart openclaw-gateway.service >/dev/null 2>&1 || true
      if systemctl --user is-active --quiet openclaw-gateway.service; then
        ok "OpenClaw gateway starts on boot"
      else
        warn "OpenClaw gateway did not stay up"
      fi
    fi
  else
    info "No systemd user session - start manually with clawctl start"
  fi
}

verify_install() {
  step "Final verification"

  command -v clawos >/dev/null 2>&1 && ok "clawos command available"
  command -v clawctl >/dev/null 2>&1 && ok "clawctl command available"
  command -v openclaw >/dev/null 2>&1 && ok "openclaw command available" || true

  curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1 \
    && ok "Ollama API reachable" \
    || warn "Ollama API not reachable yet"

  if [ "$PLATFORM" = "macos" ]; then
    launchctl print "gui/$(id -u)/io.clawos.daemon" >/dev/null 2>&1 \
      && ok "io.clawos.daemon active" \
      || warn "io.clawos.daemon is not active"
    launchctl print "gui/$(id -u)/io.clawos.openclaw-gateway" >/dev/null 2>&1 \
        && ok "io.clawos.openclaw-gateway active" || true
  elif systemd_user_ready; then
    systemctl --user is-active --quiet clawos.service \
      && ok "clawos.service active" \
      || warn "clawos.service is not active"
    systemctl --user is-active --quiet openclaw-gateway.service \
      && ok "openclaw-gateway.service active" || true
  fi
}

clear || true
echo ""
echo -e "${P}${BOLD}"
cat <<'BANNER'
   C L A W O S
BANNER
echo -e "${RESET}"
echo -e "  ${W}${BOLD}Agent-native OS. Offline. Private. Free.${RESET}"
echo -e "  ${D}github.com/xbrxr03/clawos${RESET}"
echo ""
divider
echo ""

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
BREW_BIN=""
CHECK_ONLY=false

# ── Parse flags ───────────────────────────────────────────────────────────────
for _arg in "$@"; do
  case "$_arg" in
    --check)  CHECK_ONLY=true ;;
    --skip-model) SKIP_MODEL=true ;;
    --help|-h)
      echo "Usage: bash install.sh [--check] [--skip-model]"
      echo ""
      echo "  --check       Pre-flight only: detect hardware profile and report what would be"
      echo "                installed without changing anything on this machine."
      echo "  --skip-model  Skip pulling Ollama models (useful for CI or offline installs)."
      echo ""
      exit 0 ;;
  esac
done

OS_NAME="$(uname -s)"
case "$OS_NAME" in
  Linux)  PLATFORM="linux" ;;
  Darwin) PLATFORM="macos" ;;
  *) die "Unsupported OS: $OS_NAME. ClawOS currently supports Linux and macOS." ;;
esac

step "Checking your system"

if [ "$PLATFORM" = "linux" ] && [ -f /etc/os-release ]; then
  . /etc/os-release
  ok "OS: ${PRETTY_NAME:-Linux}"
elif [ "$PLATFORM" = "macos" ]; then
  ok "OS: macOS $(sw_vers -productVersion 2>/dev/null || echo unknown)"
fi

if [ -f /proc/meminfo ]; then
  RAM_KB=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
  RAM_GB=$((RAM_KB / 1024 / 1024))
elif command -v sysctl >/dev/null 2>&1; then
  RAM_BYTES=$(sysctl -n hw.memsize 2>/dev/null || echo 0)
  RAM_GB=$((RAM_BYTES / 1024 / 1024 / 1024))
else
  warn "Could not detect RAM - assuming 8GB"
  RAM_GB=8
fi
[ "$RAM_GB" -lt "$MIN_RAM_GB" ] && die "Not enough RAM: ${RAM_GB}GB found, ${MIN_RAM_GB}GB required."
ok "RAM: ${RAM_GB}GB"

DISK_KB="$(df -Pk "$HOME" | awk 'NR==2 {print $4}')"
DISK_FREE=$((DISK_KB / 1024 / 1024))
[ "${DISK_FREE:-0}" -lt 10 ] && die "Not enough disk: ${DISK_FREE}GB free, need 10GB."
ok "Disk: ${DISK_FREE}GB free"

ARCH="$(uname -m)"
case "$ARCH" in
  aarch64|arm64|armv7l|armv8l) IS_ARM=true ;;
  *) IS_ARM=false ;;
esac

VRAM_GB=0
if command -v nvidia-smi >/dev/null 2>&1; then
  VRAM_GB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | awk '{printf "%.0f", $1/1024}' || echo 0)
fi

if [ "${VRAM_GB:-0}" -ge 10 ] && [ "$RAM_GB" -ge 30 ]; then
  PROFILE="gaming"; TIER="Tier D GPU workstation (${VRAM_GB}GB VRAM)"
elif [ "$RAM_GB" -ge 30 ]; then
  PROFILE="performance"; TIER="Tier C workstation"
elif [ "$RAM_GB" -ge 14 ]; then
  PROFILE="balanced"; TIER="Tier B workstation"
else
  PROFILE="lowram"; TIER="Tier A mini PC"
fi

if [ "$IS_ARM" = "true" ] && [ "$PROFILE" != "lowram" ]; then
  PROFILE="lowram"
  TIER="Tier A ARM device"
  warn "ARM CPU detected - using lightweight local defaults"
fi
ok "Hardware: $TIER"

case "$PROFILE" in
  lowram)
    MODEL="qwen2.5:3b"
    MODEL_SIZE="~2.0GB"
    MODEL_NOTE="fast CPU-only model, optimised for 8GB RAM"
    ;;
  balanced)
    MODEL="qwen2.5:7b"
    MODEL_SIZE="~4.7GB"
    MODEL_NOTE="strong reasoning model, 16GB RAM recommended"
    ;;
  performance|gaming)
    MODEL="qwen2.5:7b"
    MODEL_SIZE="~4.7GB"
    MODEL_NOTE="full local capability, GPU recommended"
    ;;
  *)
    MODEL="qwen2.5:3b"
    MODEL_SIZE="~2.0GB"
    MODEL_NOTE="fast CPU-only model, optimised for 8GB RAM"
    ;;
esac

case "$PROFILE" in
  lowram)      export CLAWOS_DETECTED_TIER="A" ;;
  balanced)    export CLAWOS_DETECTED_TIER="B" ;;
  performance) export CLAWOS_DETECTED_TIER="C" ;;
  gaming)      export CLAWOS_DETECTED_TIER="D" ;;
  *)           export CLAWOS_DETECTED_TIER="B" ;;
esac
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

# ── --check mode: report and exit without installing anything ─────────────────
if [ "$CHECK_ONLY" = "true" ]; then
  echo ""
  divider
  echo ""
  echo -e "  ${P}${BOLD}ClawOS Pre-flight Report${RESET}"
  echo ""
  echo -e "  ${W}Platform   :${RESET} $(platform_name) (${ARCH})"
  echo -e "  ${W}RAM        :${RESET} ${RAM_GB}GB"
  echo -e "  ${W}Disk free  :${RESET} ${DISK_FREE}GB"
  echo -e "  ${W}Profile    :${RESET} ${PROFILE} (Tier ${CLAWOS_DETECTED_TIER})"
  echo -e "  ${W}Model      :${RESET} ${MODEL} (${MODEL_SIZE}) — ${MODEL_NOTE}"
  echo -e "  ${W}Runtimes   :${RESET} ${CLAWOS_RUNTIMES}"
  echo -e "  ${W}Install to :${RESET} ${INSTALL_DIR}"
  echo ""
  echo -e "  ${G}${BOLD}✓ Ready to install.${RESET} Run without --check to proceed."
  echo ""
  exit 0
fi

install_system_packages
require_cmd python3
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
ok "Python $PY_VER"

install_ollama
install_node

step "Installing Nexus"
if [ -d "$INSTALL_DIR/clawos_core" ]; then
  ok "ClawOS already present at $INSTALL_DIR"
elif [ -d "$INSTALL_DIR/.git" ]; then
  run_with_spinner "Updating existing install" git -C "$INSTALL_DIR" pull --ff-only -q || warn "Git pull failed - using existing checkout"
  ok "ClawOS updated"
else
  run_with_spinner "Cloning from GitHub" \
    git clone -q --branch "$CLAWOS_BRANCH" --depth 1 "$CLAWOS_REPO" "$INSTALL_DIR" \
    || die "Clone failed. Check: $CLAWOS_REPO"
  ok "ClawOS cloned to $INSTALL_DIR"
fi

cd "$INSTALL_DIR" || die "Install directory not found: $INSTALL_DIR"
export PYTHONPATH="$INSTALL_DIR"

install_python_packages
build_command_center

step "Bootstrapping Nexus"
if [ -t 0 ] && [ -z "${OPENROUTER_API_KEY:-}" ]; then
  echo ""
  echo -e "  ${D}Optional: add an OpenRouter key for cloud models. Press Enter to skip.${RESET}"
  read -r -s -p "  OpenRouter API key: " OPENROUTER_KEY
  echo ""
  if [ -n "$OPENROUTER_KEY" ]; then
    export OPENROUTER_API_KEY="$OPENROUTER_KEY"
    ok "OpenRouter key saved for this install session"
  fi
fi

run_with_spinner "Running bootstrap ($PROFILE profile)" \
  python3 -m bootstrap.bootstrap --profile "$PROFILE" --yes \
  || die "Bootstrap failed. Run: cd $INSTALL_DIR && python3 -m bootstrap.bootstrap"
ok "Bootstrap complete"

step "Pulling AI model"
if [ "$SKIP_MODEL" = "true" ]; then
  warn "Skipping model pull (SKIP_MODEL=true)"
else
  OLLAMA_URL="${OLLAMA_HOST:-http://127.0.0.1:11434}"
  if [ "$OLLAMA_URL" != "http://localhost:11434" ] && [ "$OLLAMA_URL" != "http://127.0.0.1:11434" ]; then
    info "Remote Ollama detected: $OLLAMA_URL"
    info "Run on remote: ollama pull $MODEL"
    ok "Remote Ollama configured"
  else
    info "Pulling $MODEL ($MODEL_SIZE) - $MODEL_NOTE"
    "$OLLAMA_BIN" pull "$MODEL" || warn "Model pull failed"
  fi
fi

step "Pulling embedding model"
if [ "$SKIP_MODEL" = "true" ]; then
  warn "Skipping embedding model pull (SKIP_MODEL=true)"
else
  EMBED_MODEL="nomic-embed-text"
  OLLAMA_URL="${OLLAMA_HOST:-http://127.0.0.1:11434}"
  if [ "$OLLAMA_URL" != "http://localhost:11434" ] && [ "$OLLAMA_URL" != "http://127.0.0.1:11434" ]; then
    info "Remote Ollama detected - run on remote: ollama pull $EMBED_MODEL"
  elif ! curl -sf "$OLLAMA_URL/api/tags" 2>/dev/null | grep -q '"name":"nomic-embed-text'; then
    "$OLLAMA_BIN" pull "$EMBED_MODEL" || warn "Embedding model pull failed"
  else
    ok "Embedding model already present"
  fi
fi

install_wrapper_commands
install_picoclaw_if_needed
enable_autostart
verify_install

ELAPSED=$((SECONDS - START_TIME))
echo ""
divider
echo ""
echo -e "  ${G}${BOLD}ClawOS installed in ${ELAPSED}s${RESET}"
echo ""
echo -e "  ${B}clawos${RESET}"
echo -e "  ${D}Native ClawOS runtime using ${MODEL}${RESET}"
echo ""
echo -e "  ${B}nexus workflow list${RESET}"
echo -e "  ${D}Browse built-in workflows${RESET}"
echo ""
echo -e "  ${B}openclaw tui${RESET}"
echo -e "  ${D}OpenClaw TUI with Kimi K2.5 on port ${OPENCLAW_GATEWAY_PORT}${RESET}"
echo ""

if [ "$PLATFORM" = "macos" ]; then
  echo -e "  ${D}Reload shell if needed:${RESET} ${B}source ~/.zprofile${RESET}"
else
  echo -e "  ${D}Reload shell if needed:${RESET} ${B}source ~/.bashrc${RESET}"
fi
echo -e "  ${D}Service manager:${RESET} ${B}$(platform_name)${RESET} (${D}$([ "$PLATFORM" = "macos" ] && echo launchd || echo systemd)${RESET}${B})${RESET}"
echo -e "  ${D}Open setup:${RESET} ${B}clawos-setup${RESET}"
echo -e "  ${D}Open home:${RESET} ${B}clawos-command-center${RESET}"
echo ""

# Print dashboard token so new users can log in
_CLAWOS_DIR="${CLAWOS_DIR:-$HOME/clawos}"
_TOKEN_FILE="$_CLAWOS_DIR/config/dashboard.token"
if [ -f "$_TOKEN_FILE" ]; then
  echo -e "  ${Y}Dashboard token:${RESET} ${B}$(cat "$_TOKEN_FILE")${RESET}"
  echo -e "  ${D}(saved at ${_TOKEN_FILE})${RESET}"
  echo ""
fi

play_jarvis_greeting() {
  local TEXT="Hello sir. All systems are online."
  if command -v piper >/dev/null 2>&1 && [ -f "$HOME/.local/share/piper/en_US-lessac-medium.onnx" ]; then
    echo "$TEXT" | piper --model "$HOME/.local/share/piper/en_US-lessac-medium.onnx" --output_raw 2>/dev/null | \
      aplay -r 22050 -f S16_LE -c 1 2>/dev/null || true
    return
  fi
  if command -v say >/dev/null 2>&1; then
    say -v "Samantha" "$TEXT" 2>/dev/null || true
    return
  fi
  if command -v espeak >/dev/null 2>&1; then
    espeak "$TEXT" 2>/dev/null || true
  fi
}

if [ -t 0 ] && [ -t 1 ]; then
  play_jarvis_greeting
  echo -e "  ${B}Launching OpenClaw + Kimi K2.5...${RESET}"
  echo ""
  ollama launch openclaw --model kimi-k2.5:cloud
else
  echo -e "  ${D}Run: ${RESET}${B}ollama launch openclaw --model kimi-k2.5:cloud${RESET}"
  echo ""
fi
