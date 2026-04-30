#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DIST_DIR="${PROJECT_DIR}/dist"
BUILD_ROOT="${PROJECT_DIR}/.build/appimage"
APP_DIR="${BUILD_ROOT}/AppDir"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }
}

require_cmd python3
require_cmd rsync

VERSION="$(python3 -c 'from clawos_core.constants import VERSION; print(VERSION)')"
ARCH="amd64"
OUTPUT="${DIST_DIR}/ClawOS-${VERSION}-${ARCH}.AppImage"

# Download appimagetool if not present
APPIMAGETOOL="${BUILD_ROOT}/appimagetool"
if [ ! -f "$APPIMAGETOOL" ]; then
  mkdir -p "$BUILD_ROOT"
  curl -L -o "$APPIMAGETOOL" "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
  chmod +x "$APPIMAGETOOL"
fi

rm -rf "${APP_DIR}"
mkdir -p "${APP_DIR}/usr/bin" "${APP_DIR}/usr/share/applications" "${APP_DIR}/opt/clawos"

# Copy project files
rsync -a \
  --delete \
  --exclude '.git' \
  --exclude '.github' \
  --exclude '.build' \
  --exclude 'dist' \
  --exclude 'desktop' \
  --exclude 'tests' \
  --exclude 'node_modules' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude '.venv' \
  "${PROJECT_DIR}/" "${APP_DIR}/opt/clawos/"

# Create wrapper scripts
cat > "${APP_DIR}/usr/bin/clawos" <<'EOF'
#!/usr/bin/env bash
export PYTHONPATH="${APPDIR}/opt/clawos"
exec python3 "${APPDIR}/opt/clawos/clients/cli/repl.py" "$@"
EOF

cat > "${APP_DIR}/usr/bin/clawctl" <<'EOF'
#!/usr/bin/env bash
export PYTHONPATH="${APPDIR}/opt/clawos"
exec python3 "${APPDIR}/opt/clawos/clawctl/main.py" "$@"
EOF

chmod +x "${APP_DIR}/usr/bin/clawos" "${APP_DIR}/usr/bin/clawctl"

# Create desktop entry
cat > "${APP_DIR}/usr/share/applications/clawos.desktop" <<EOF
[Desktop Entry]
Name=ClawOS
Exec=clawos
Type=Application
Categories=Development;AI;
Comment=Local AI agent for your laptop
Version=${VERSION}
EOF

# Create AppRun
cat > "${APP_DIR}/AppRun" <<'EOF'
#!/bin/bash
export PYTHONPATH="${APPDIR}/opt/clawos"
exec "${APPDIR}/usr/bin/clawos" "$@"
EOF
chmod +x "${APP_DIR}/AppRun"

mkdir -p "$DIST_DIR"
"$APPIMAGETOOL" "$APP_DIR" "$OUTPUT" 2>/dev/null || echo "AppImage build requires appimagetool"

echo "Built ${OUTPUT}"
