#!/usr/bin/env bash
# ClawOS Dashboard — install and start script
# Usage: bash install.sh [--dev]
set -uo pipefail

CLAWOS_DIR="$HOME/clawos"
DASH_DIR="$CLAWOS_DIR/dashboard"
BACKEND_DIR="$DASH_DIR/backend"
FRONTEND_DIR="$DASH_DIR/frontend"
DEV_MODE="${1:-}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ClawOS Dashboard — Phase 3"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Backend deps ───────────────────────────────────────────────────────────────
echo "→ Installing backend dependencies..."
pip install fastapi uvicorn httpx aiofiles websockets --break-system-packages -q

# ── Frontend build ─────────────────────────────────────────────────────────────
if [[ "$DEV_MODE" == "--dev" ]]; then
  echo "→ Dev mode: skipping frontend build (run 'npm run dev' in frontend/)"
else
  echo "→ Building frontend..."
  cd "$FRONTEND_DIR"
  npm install --silent
  npm run build
  cd "$CLAWOS_DIR"
  echo "✓ Frontend built → backend/static/"
fi

# ── Serve static files from FastAPI ───────────────────────────────────────────
# Add StaticFiles mount if not already present
python3 - << 'PYEOF'
import re
from pathlib import Path

svc = Path.home() / "clawos/dashboard/backend/service.py"
content = svc.read_text()

if "StaticFiles" in content and "mount" not in content:
    mount = '''
# Serve built React frontend
from fastapi.staticfiles import StaticFiles
_static = Path(__file__).parent / "static"
if _static.exists():
    app.mount("/", StaticFiles(directory=str(_static), html=True), name="static")
'''
    content += mount
    svc.write_text(content)
    print("✓ Static file serving configured")
else:
    print("✓ Static serving already configured")
PYEOF

# ── systemd user service ───────────────────────────────────────────────────────
echo "→ Installing systemd user service..."
mkdir -p "$HOME/.config/systemd/user"
UNIT_SRC="$BACKEND_DIR/dashd@.service"
UNIT_DST="$HOME/.config/systemd/user/dashd.service"

# Substitute %h and %i with real home/user
sed "s|%h|$HOME|g; s|%i|$(whoami)|g" "$UNIT_SRC" > "$UNIT_DST"

systemctl --user daemon-reload
systemctl --user enable dashd.service 2>/dev/null || true

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ Dashboard installed"
echo ""
echo "  Start:   systemctl --user start dashd"
echo "  Dev:     cd dashboard/frontend && npm run dev"
echo "  URL:     http://localhost:7070"
echo "  WS:      ws://localhost:7070/ws"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
