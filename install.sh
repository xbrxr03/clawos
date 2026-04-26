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

link_into_system_bin() {
  local source=$1
  local name=${2:-$(basename "$source")}
  local sys_bin="/usr/local/bin"
  [ -n "$source" ] || return 0
  [ -e "$source" ] || return 0
  if [ -d "$sys_bin" ]; then
    if [ -w "$sys_bin" ]; then
      ln -sf "$source" "$sys_bin/$name" >/dev/null 2>&1 || true
    elif command -v sudo >/dev/null 2>&1; then
      sudo ln -sf "$source" "$sys_bin/$name" >/dev/null 2>&1 || true
    fi
  fi
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

  # Ensure npm is available — NodeSource includes it but Ubuntu apt node may not
  if ! command -v npm >/dev/null 2>&1; then
    run_with_spinner "Installing npm" \
      sudo apt-get install -y npm || warn "npm install failed — frontend build may be skipped"
  fi
}

install_openclaw() {
  step "Installing OpenClaw"
  if sudo npm install -g openclaw 2>/dev/null; then
    ok "OpenClaw installed"
  else
    warn "OpenClaw install failed — run: sudo npm install -g openclaw"
  fi
}

install_python_packages() {
  step "Installing Python packages"

  PYTHON_PACKAGES=(
    pyyaml aiohttp fastapi "uvicorn[standard]"
    ollama click chromadb json_repair
    pypdf python-docx aiofiles httpx gitpython rich openai-whisper
    openwakeword cryptography icalendar ptyprocess
  )

  # Create a virtualenv so services have a clean, isolated Python environment
  if [ ! -x "${INSTALL_DIR}/venv/bin/python3" ]; then
    if [ "$PLATFORM" != "macos" ]; then
      sudo apt-get install -y python3-venv >/dev/null 2>&1 || true
    fi
    run_with_spinner "Creating Python virtualenv" \
      python3 -m venv "${INSTALL_DIR}/venv" \
      || die "Failed to create virtualenv at ${INSTALL_DIR}/venv"
  fi

  VENV_PIP="${INSTALL_DIR}/venv/bin/pip"

  run_with_spinner "Installing Python packages" \
    "$VENV_PIP" install -q "${PYTHON_PACKAGES[@]}" \
    || warn "Some Python packages may have failed"

  ok "pyyaml  fastapi  chromadb  ollama  pypdf  python-docx"
}

install_wake_word_model() {
  local MODEL_DIR="$INSTALL_DIR/services/voiced/models"
  local MODEL_FILE="$MODEL_DIR/hey_jarvis.onnx"
  mkdir -p "$MODEL_DIR"
  if [ -f "$MODEL_FILE" ]; then
    ok "Wake word model ready"
    return 0
  fi
  step "Downloading wake word model"
  if python3 -c "
import sys, shutil
from pathlib import Path
dest = Path('$MODEL_FILE')
try:
    import openwakeword
    from openwakeword.utils import download_models
    download_models()
    pkg = Path(openwakeword.__file__).parent
    candidates = sorted(pkg.glob('**/*hey_jarvis*.onnx'))
    if not candidates:
        candidates = sorted(pkg.glob('**/*.onnx'))
    if candidates:
        shutil.copy2(candidates[0], dest)
        sys.exit(0)
    sys.exit(1)
except Exception as e:
    print(f'error: {e}', file=sys.stderr)
    sys.exit(1)
" 2>/dev/null
  then
    ok "Wake word model ready"
  else
    warn "Wake word model unavailable — voice degrades to push-to-talk"
  fi
}

install_piper_voice() {
  # Bundles the Piper Lessac (medium) voice so Jarvis can speak out of the box.
  # Without this, voiced.speak() silently degrades — tts_ok reports false and
  # the first-run handoff greeting is muted. Model source: HuggingFace rhasspy/piper-voices.
  local VOICE_DIR="${HOME}/clawos/voice"
  local MODEL_FILE="${VOICE_DIR}/en_US-lessac-medium.onnx"
  local MODEL_CFG="${VOICE_DIR}/en_US-lessac-medium.onnx.json"
  local BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"
  mkdir -p "$VOICE_DIR"

  if [ -s "$MODEL_FILE" ] && [ -s "$MODEL_CFG" ]; then
    ok "Piper voice model ready (Lessac medium)"
    return 0
  fi

  step "Downloading Piper voice model (Lessac · 63 MB)"

  # Prefer curl, fall back to wget. Silently continues if neither works — voice will
  # degrade to text-only but install doesn't fail (mirrors install_wake_word_model).
  local dl=""
  if command -v curl >/dev/null 2>&1; then
    dl="curl -fsSL --retry 2 --connect-timeout 10"
  elif command -v wget >/dev/null 2>&1; then
    dl="wget -qO-"
  else
    warn "Neither curl nor wget is available — Piper voice unavailable, Jarvis will be silent"
    return 0
  fi

  if $dl "${BASE}/en_US-lessac-medium.onnx" > "${MODEL_FILE}.part" 2>/dev/null \
     && [ -s "${MODEL_FILE}.part" ]; then
    mv "${MODEL_FILE}.part" "$MODEL_FILE"
  else
    rm -f "${MODEL_FILE}.part"
    warn "Piper voice model download failed — Jarvis will degrade to text-only"
    return 0
  fi

  if $dl "${BASE}/en_US-lessac-medium.onnx.json" > "${MODEL_CFG}.part" 2>/dev/null \
     && [ -s "${MODEL_CFG}.part" ]; then
    mv "${MODEL_CFG}.part" "$MODEL_CFG"
  else
    rm -f "${MODEL_CFG}.part"
    warn "Piper voice config download failed — Jarvis will degrade to text-only"
    return 0
  fi

  ok "Piper voice model ready (Lessac medium)"
}

install_playwright() {
  if [ "$IS_ARM" = "true" ]; then
    return 0
  fi
  if python3 -c "import playwright" 2>/dev/null; then
    ok "Playwright already installed"
    return 0
  fi
  step "Installing Playwright browser engine"
  if [ "$PLATFORM" = "macos" ]; then
    python3 -m pip install -q playwright --user 2>/dev/null || true
  else
    python3 -m pip install -q playwright --break-system-packages 2>/dev/null || \
      python3 -m pip install -q playwright --user 2>/dev/null || true
  fi
  python3 -m playwright install chromium --with-deps 2>/dev/null || true
  ok "Playwright ready"
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

# OpenClaw config is written by the setup wizard GUI (/api/setup/openclaw/configure).

install_wrapper_commands() {
  step "Installing command wrappers"

  mkdir -p "$HOME/.local/bin"
  local py_bin="${INSTALL_DIR}/venv/bin/python3"

  write_file_if_changed "$HOME/.local/bin/nexus" 755 <<EOF
#!/usr/bin/env bash
export PYTHONPATH="${INSTALL_DIR}"
exec "${py_bin}" "${INSTALL_DIR}/nexus/cli.py" "\$@"
EOF

  write_file_if_changed "$HOME/.local/bin/clawos" 755 <<EOF
#!/usr/bin/env bash
export PYTHONPATH="${INSTALL_DIR}"
exec "${py_bin}" "${INSTALL_DIR}/clients/cli/repl.py" "\$@"
EOF

  write_file_if_changed "$HOME/.local/bin/clawctl" 755 <<EOF
#!/usr/bin/env bash
export PYTHONPATH="${INSTALL_DIR}"
exec "${py_bin}" "${INSTALL_DIR}/clawctl/main.py" "\$@"
EOF

  write_file_if_changed "$HOME/.local/bin/clawos-command-center" 755 <<EOF
#!/usr/bin/env bash
export PYTHONPATH="${INSTALL_DIR}"
exec "${py_bin}" "${INSTALL_DIR}/clients/desktop/launch_command_center.py" "\$@"
EOF

  write_file_if_changed "$HOME/.local/bin/clawos-setup" 755 <<EOF
#!/usr/bin/env bash
export PYTHONPATH="${INSTALL_DIR}"
route="/setup?fresh=\$(date +%s)"
exec "${py_bin}" "${INSTALL_DIR}/clients/desktop/launch_command_center.py" --route "\${route}" "\$@"
EOF

  for _cmd in nexus clawos clawctl clawos-command-center clawos-setup; do
    link_into_system_bin "$HOME/.local/bin/$_cmd" "$_cmd"
  done

  ensure_path_line "$HOME/.bashrc"
  ensure_path_line "$HOME/.zshrc"
  ensure_path_line "$HOME/.zprofile"
  ensure_path_line "$HOME/.profile"
  export PATH="$HOME/.local/bin:$PATH"

  ok "clawos  clawctl  nexus  clawos-command-center  clawos-setup"
}

enable_autostart() {
  step "Enabling autostart"

  if [ "$PLATFORM" = "macos" ]; then
    OPENCLAW_BIN="$(command -v openclaw 2>/dev/null || true)"
    CLAWOS_HOME="$INSTALL_DIR" \
    CLAWOS_WORKSPACE="nexus_default" \
    PYTHON_BIN="${INSTALL_DIR}/venv/bin/python3" \
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

  else
    info "No systemd user session - start manually with clawctl start"
  fi
}

verify_install() {
  step "Final verification"

  command -v clawos >/dev/null 2>&1 && ok "clawos command available"
  command -v clawctl >/dev/null 2>&1 && ok "clawctl command available"

  curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1 \
    && ok "Ollama API reachable" \
    || warn "Ollama API not reachable yet"

  if [ "$PLATFORM" = "macos" ]; then
    launchctl print "gui/$(id -u)/io.clawos.daemon" >/dev/null 2>&1 \
      && ok "io.clawos.daemon active" \
      || warn "io.clawos.daemon is not active"
  elif systemd_user_ready; then
    systemctl --user is-active --quiet clawos.service \
      && ok "clawos.service active" \
      || warn "clawos.service is not active"
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
INSTALL_DIR="${CLAWOS_DIR:-$HOME/.clawos-runtime}"
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

# ── Live install streaming ───────────────────────────────────────────────────
# emit_milestone appends to a local JSONL buffer (durable) and also tries to
# POST the milestone to dashd. Dashd is not up until enable_autostart later
# in the script, so pre-dashd milestones are simply queued in the buffer —
# drain_install_buffer replays them via POST once dashd is alive, so the
# browser's /setup page shows the full install history in its BootLog.
CLAWOS_STATE_DIR="${CLAWOS_STATE_DIR:-$HOME/.clawos/install}"
CLAWOS_INSTALL_BUFFER="${CLAWOS_STATE_DIR}/install-milestones.buffer.jsonl"

# Escape a string for safe inclusion inside a JSON string literal.
_json_escape() {
  # shellcheck disable=SC2001
  echo -n "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/\t/\\t/g' -e 's/\r/\\r/g' -e 's/\n/\\n/g'
}

# emit_milestone <id> <status> <label> [detail] [duration_ms]
#   id:        stable phase key (preflight, deps, core, bootstrap, model,
#              memory, voice, services, verify, ready)
#   status:    pending | running | done | error
#   label:     human-readable text shown in the browser BootLog
#   detail:    optional sub-text (e.g. model name, tier)
#   duration_ms: optional timing info
emit_milestone() {
  local id="$1"
  local status="$2"
  local label="$3"
  local detail="${4:-}"
  local duration_ms="${5:-0}"

  mkdir -p "$CLAWOS_STATE_DIR" 2>/dev/null || true

  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%S.000Z 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)"

  local e_label e_detail
  e_label="$(_json_escape "$label")"
  e_detail="$(_json_escape "$detail")"

  local json
  json=$(printf '{"id":"%s","status":"%s","label":"%s","detail":"%s","duration_ms":%s,"ts":"%s"}' \
    "$id" "$status" "$e_label" "$e_detail" "${duration_ms:-0}" "$ts")

  # Durable local record
  echo "$json" >> "$CLAWOS_INSTALL_BUFFER" 2>/dev/null || true

  # Best-effort live POST — dashd may not be up yet; silent on failure.
  if command -v curl >/dev/null 2>&1; then
    curl -sf -m 2 \
      -H "Content-Type: application/json" \
      -H "x-clawos-setup: 1" \
      -X POST \
      -d "$json" \
      "http://127.0.0.1:7070/api/setup/install-milestone" \
      >/dev/null 2>&1 || true
  fi
}

# drain_install_buffer — replay all queued milestones via POST. Called once
# dashd is up so accumulated pre-dashd milestones are visible to the browser.
drain_install_buffer() {
  [ -f "$CLAWOS_INSTALL_BUFFER" ] || return 0
  command -v curl >/dev/null 2>&1 || return 0
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    curl -sf -m 2 \
      -H "Content-Type: application/json" \
      -H "x-clawos-setup: 1" \
      -X POST \
      -d "$line" \
      "http://127.0.0.1:7070/api/setup/install-milestone" \
      >/dev/null 2>&1 || true
  done < "$CLAWOS_INSTALL_BUFFER"
}

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
      echo "  --skip-model  Deprecated. The browser wizard now provisions models after install."
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
emit_milestone preflight running "Checking your system" "CPU · RAM · disk"

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
emit_milestone preflight done "System checked" "$TIER · ${RAM_GB}GB RAM"

# Staying on qwen2.5 — qwen3 / qwen3.5 tool-calling is broken on Ollama as of 2026-04.
# Ollama's registry ships qwen3.5 with the Qwen3 Hermes JSON parser template, but the
# model was trained to emit Qwen3-Coder XML, so tool calls come out as plain text
# (often inside unclosed <think> blocks) instead of executing. Tracking upstream:
#   Ollama #14745, #14493 · llama.cpp #20837 · QwenLM/Qwen3.5 #12
# The rest of the codebase (setupd defaults, ModelScreen catalog, README, tests) is
# already on qwen2.5 — keep this file in sync. Revisit once Ollama ships the fix.
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
    balanced)    CLAWOS_RUNTIMES="nexus,picoclaw" ;;
    performance) CLAWOS_RUNTIMES="nexus,picoclaw" ;;
    gaming)      CLAWOS_RUNTIMES="nexus,picoclaw" ;;
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
  echo -e "  ${W}Hardware   :${RESET} ${PROFILE} (Tier ${CLAWOS_DETECTED_TIER})"
  echo -e "  ${W}Model      :${RESET} ${MODEL} (${MODEL_SIZE}) — ${MODEL_NOTE}"
  echo -e "  ${W}Runtimes   :${RESET} ${CLAWOS_RUNTIMES} (recommended defaults)"
  echo -e "  ${W}Install to :${RESET} ${INSTALL_DIR}"
  echo ""
  echo -e "  ${G}${BOLD}✓ Ready to install.${RESET} Run without --check to proceed."
  echo ""
  exit 0
fi

emit_milestone deps running "Installing system packages" "Python · Ollama · Node"
install_system_packages
require_cmd python3
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
ok "Python $PY_VER"

install_ollama
install_node
install_openclaw
emit_milestone deps done "Dependencies installed" "Python $PY_VER · Ollama · Node · OpenClaw"

step "Installing Nexus"
emit_milestone core running "Installing Nexus" "cloning clawos + python deps"
if [ -d "$INSTALL_DIR/clawos_core" ]; then
  ok "ClawOS already present at $INSTALL_DIR"
elif [ -d "$INSTALL_DIR/.git" ]; then
  run_with_spinner "Updating existing install" git -C "$INSTALL_DIR" pull --ff-only -q || warn "Git pull failed - using existing checkout"
  ok "ClawOS updated"
else
  rm -rf "$INSTALL_DIR"
  run_with_spinner "Cloning from GitHub" \
    git clone -q --branch "$CLAWOS_BRANCH" --depth 1 "$CLAWOS_REPO" "$INSTALL_DIR" \
    || die "Clone failed. Check: $CLAWOS_REPO"
  ok "ClawOS cloned to $INSTALL_DIR"
fi

cd "$INSTALL_DIR" || die "Install directory not found: $INSTALL_DIR"
export PYTHONPATH="$INSTALL_DIR"

install_python_packages
emit_milestone voice running "Provisioning voice pipeline" "Whisper + Piper + wake word"
install_wake_word_model
install_piper_voice
install_playwright
emit_milestone voice done "Voice pipeline ready" "offline STT/TTS"
build_command_center
emit_milestone core done "Nexus installed" "clawos + dashboard built"
step "Preparing machine foundation"
emit_milestone bootstrap running "Preparing machine foundation" "hardware: $PROFILE"
BOOTSTRAP_PROFILE="$PROFILE"
[ "$BOOTSTRAP_PROFILE" = "gaming" ] && BOOTSTRAP_PROFILE="performance"
run_with_spinner "Running bootstrap foundation (${BOOTSTRAP_PROFILE} hardware profile)" \
  bash -c "cd \"${INSTALL_DIR}\" && PYTHONPATH=\"${INSTALL_DIR}\" \"${INSTALL_DIR}/venv/bin/python3\" -m bootstrap.bootstrap --profile \"$BOOTSTRAP_PROFILE\" --yes --skip-model" \
  || { emit_milestone bootstrap error "Bootstrap failed" "see terminal"; die "Bootstrap failed. Run: cd $INSTALL_DIR && python3 -m bootstrap.bootstrap"; }
ok "Machine foundation ready"
emit_milestone bootstrap done "Machine foundation ready" "finish setup in the browser wizard"

# Keep dashd loopback-only during first-run setup. The setup wizard's
# unauthenticated access path is intentionally restricted to trusted local
# browser sessions, so binding 0.0.0.0 here can strand the UI on the
# "Warming up the wizard" shell.
CLAWOS_YAML="${INSTALL_DIR}/config/clawos.yaml"
if [ -f "$CLAWOS_YAML" ]; then
  if grep -q "^dashboard:" "$CLAWOS_YAML" 2>/dev/null; then
    sed -i 's/^\([[:space:]]*host:[[:space:]]*\)0\.0\.0\.0$/\1127.0.0.1/' "$CLAWOS_YAML" 2>/dev/null || true
  else
    printf '\ndashboard:\n  host: 127.0.0.1\n  port: 7070\n' >> "$CLAWOS_YAML"
  fi
else
  mkdir -p "${INSTALL_DIR}/config"
  printf '_profile: %s\ndashboard:\n  host: 127.0.0.1\n  port: 7070\n' "$BOOTSTRAP_PROFILE" > "$CLAWOS_YAML"
fi



emit_milestone services running "Enabling daemons" "nexus · memd · policyd · dashd"
install_wrapper_commands
enable_autostart
# Now that dashd is up (or starting), drain any buffered milestones so the
# browser's /setup page can show the full install history in its BootLog.
# We give dashd a moment to accept connections before draining.
for _i in 1 2 3 4 5; do
  if curl -sf -m 1 "http://127.0.0.1:7070/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
drain_install_buffer
emit_milestone services done "Daemons enabled" "autostart configured"
emit_milestone verify running "Verifying install" "health + config"
verify_install
emit_milestone verify done "Install verified" "all checks passed"

ELAPSED=$((SECONDS - START_TIME))
echo ""
divider
echo ""
echo -e "  ${G}${BOLD}ClawOS installed in ${ELAPSED}s${RESET}"
echo ""
echo -e "  ${W}Persona:${RESET}          ${B}Choose in browser wizard${RESET}"
echo -e "  ${W}Hardware profile:${RESET} ${B}${BOOTSTRAP_PROFILE}${RESET}"
echo -e "  ${W}Recommended model:${RESET} ${B}${MODEL}${RESET} ${D}(${MODEL_NOTE})${RESET}"
echo ""
echo -e "  ${B}clawos${RESET}"
echo -e "  ${D}Native ClawOS runtime (model is finalized in setup)${RESET}"
echo ""
echo -e "  ${B}clawctl wf list${RESET}"
echo -e "  ${D}Browse 29 built-in workflows${RESET}"
echo ""
echo -e "  ${B}clawctl framework install openclaw${RESET}"
echo -e "  ${D}Install OpenClaw from the setup wizard or this command${RESET}"
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
echo -e "  ${W}Dashboard:${RESET}        ${B}http://localhost:7070${RESET}"
echo ""
CLAWOS_ROUTE="/setup?fresh=$(date +%s)"
CLAWOS_URL="http://localhost:7070${CLAWOS_ROUTE}"
echo -e "  ${D}Waiting for dashboard to come online...${RESET}"

READY=0
for i in $(seq 1 30); do
  if curl -sf "http://localhost:7070/api/health" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 1
done

if [ "$READY" = "1" ]; then
  emit_milestone ready done "ClawOS online" "dashboard @ :7070 · ${ELAPSED}s total"
  if [ "${NO_BROWSER:-0}" = "1" ] || [ ! -t 1 ]; then
    echo -e "  ${G}Command Center ready:${RESET} ${B}${CLAWOS_URL}${RESET}"
  elif "${INSTALL_DIR}/venv/bin/python3" "${INSTALL_DIR}/clients/desktop/launch_command_center.py" --route "${CLAWOS_ROUTE}" --timeout 5 >/dev/null 2>&1; then
    echo -e "  ${G}Command Center opening in your browser...${RESET}"
    echo -e "  ${D}If the browser doesn't open, visit:${RESET} ${B}${CLAWOS_URL}${RESET}"
  else
    echo -e "  ${Y}Could not auto-open your browser.${RESET}"
    echo -e "  ${D}Open this URL manually:${RESET} ${B}${CLAWOS_URL}${RESET}"
  fi
else
  emit_milestone ready error "Dashboard did not start" "timed out after 30s"
  warn "Dashboard did not come online within 30s"
  echo -e "  ${D}Once the service is up, open:${RESET} ${B}${CLAWOS_URL}${RESET}"
  echo -e "  ${D}Or open manually:${RESET} ${B}http://localhost:7070/setup${RESET}"
fi
echo ""

