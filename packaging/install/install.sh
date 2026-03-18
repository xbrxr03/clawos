#!/bin/bash
# ClawOS Installer — for existing Ubuntu 22.04/24.04
# Usage: curl -fsSL https://raw.githubusercontent.com/you/clawos/main/install.sh | bash
set -e

G="\033[0;32m" N="\033[0m" R="\033[0;31m"
ok()  { echo -e "  ${G}✓${N}  $1"; }
die() { echo -e "  ${R}✗${N}  $1"; exit 1; }

cat << 'BANNER'

  ██████╗██╗      █████╗ ██╗    ██╗ ██████╗ ███████╗
 ██╔════╝██║     ██╔══██╗██║    ██║██╔═══██╗██╔════╝
 ██║     ██║     ███████║██║ █╗ ██║██║   ██║███████╗
 ██║     ██║     ██╔══██║██║███╗██║██║   ██║╚════██║
 ╚██████╗███████╗██║  ██║╚███╔███╔╝╚██████╔╝███████║
  ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝  ╚═════╝ ╚══════╝

BANNER

INSTALL_DIR="${CLAWOS_DIR:-$HOME/clawos}"
PROFILE="${CLAWOS_PROFILE:-balanced}"

echo "  Installing to ${INSTALL_DIR} ..."
echo ""

# Deps
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip git curl wget sqlite3 2>/dev/null
ok "System deps"

# Python packages
pip3 install -q pyyaml aiohttp fastapi uvicorn ollama click \
  --break-system-packages 2>/dev/null || true
ok "Python packages"

# Ollama
if ! command -v ollama &>/dev/null; then
  echo "  Installing Ollama ..."
  curl -fsSL https://ollama.com/install.sh | sh >/dev/null 2>&1
fi
ok "Ollama"

# Clone
if [[ -d "$INSTALL_DIR/.git" ]]; then
  echo "  Updating existing install ..."
  git -C "$INSTALL_DIR" pull --ff-only -q
else
  git clone -q https://github.com/you/clawos "$INSTALL_DIR"
fi
ok "ClawOS source"

cd "$INSTALL_DIR"
export PYTHONPATH="$INSTALL_DIR"

# Bootstrap
python3 -m bootstrap.bootstrap --profile "$PROFILE" --yes
ok "Bootstrap complete"

# clawctl in PATH
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/clawctl" << CMD
#!/bin/bash
PYTHONPATH="$INSTALL_DIR" python3 "$INSTALL_DIR/clawctl/main.py" "\$@"
CMD
chmod +x "$HOME/.local/bin/clawctl"

# PATH
if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
  echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$HOME/.bashrc"
  echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$HOME/.zshrc" 2>/dev/null || true
  export PATH="$HOME/.local/bin:$PATH"
fi
ok "clawctl installed"

echo ""
echo -e "  ${G}ClawOS installed!${N}"
echo ""
echo "  Start:          clawctl chat"
echo "  All services:   clawctl start"
echo "  Dashboard:      http://localhost:7070"
echo "  Setup wizard:   clawctl wizard"
echo "  OpenClaw:       clawctl openclaw install"
echo ""
