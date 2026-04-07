#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DIST_DIR="${PROJECT_DIR}/dist"
BUILD_ROOT="${PROJECT_DIR}/.build/deb"
PKG_ROOT="${BUILD_ROOT}/pkgroot"
ARCH="${DEB_ARCH:-$(dpkg --print-architecture 2>/dev/null || echo amd64)}"
PACKAGE_NAME="${PACKAGE_NAME:-clawos-command-center}"
SKIP_FRONTEND=false

for arg in "$@"; do
  case "$arg" in
    --skip-frontend-build) SKIP_FRONTEND=true ;;
    *) echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }
}

require_cmd python3
require_cmd dpkg-deb
require_cmd rsync

VERSION="$(
  python3 - <<'PY'
from clawos_core.constants import VERSION
print(VERSION)
PY
)"

OUTPUT_DEB="${DIST_DIR}/${PACKAGE_NAME}_${VERSION}_${ARCH}.deb"

if [ "${SKIP_FRONTEND}" != "true" ]; then
  require_cmd npm
  pushd "${PROJECT_DIR}/dashboard/frontend" >/dev/null
  npm install
  npm run build
  popd >/dev/null
fi

rm -rf "${BUILD_ROOT}"
mkdir -p "${PKG_ROOT}/DEBIAN" \
         "${PKG_ROOT}/opt/clawos" \
         "${PKG_ROOT}/usr/bin" \
         "${PKG_ROOT}/usr/share/applications" \
         "${PKG_ROOT}/etc/xdg/autostart"

rsync -a \
  --delete \
  --exclude '.git' \
  --exclude '.github' \
  --exclude '.build' \
  --exclude 'dist' \
  --exclude 'desktop' \
  --exclude 'tests' \
  --exclude 'dashboard/frontend/node_modules' \
  --exclude 'dashboard/frontend/.storybook' \
  --exclude 'dashboard/frontend/tests' \
  --exclude 'dashboard/frontend/playwright.config.ts' \
  --exclude 'dashboard/frontend/storybook-static' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude '.venv' \
  "${PROJECT_DIR}/" "${PKG_ROOT}/opt/clawos/"

sed \
  -e "s/__VERSION__/${VERSION}/g" \
  -e "s/__ARCH__/${ARCH}/g" \
  "${SCRIPT_DIR}/control" > "${PKG_ROOT}/DEBIAN/control"

install -m 755 "${SCRIPT_DIR}/postinst" "${PKG_ROOT}/DEBIAN/postinst"

cat > "${PKG_ROOT}/usr/bin/clawos-command-center" <<'EOF'
#!/usr/bin/env bash
export PYTHONPATH=/opt/clawos
exec python3 /opt/clawos/clients/desktop/launch_command_center.py "$@"
EOF

cat > "${PKG_ROOT}/usr/bin/clawos-setup" <<'EOF'
#!/usr/bin/env bash
export PYTHONPATH=/opt/clawos
exec python3 /opt/clawos/clients/desktop/launch_command_center.py --route /setup "$@"
EOF

cat > "${PKG_ROOT}/usr/bin/clawos" <<'EOF'
#!/usr/bin/env bash
export PYTHONPATH=/opt/clawos
exec python3 /opt/clawos/clients/cli/repl.py "$@"
EOF

cat > "${PKG_ROOT}/usr/bin/clawctl" <<'EOF'
#!/usr/bin/env bash
export PYTHONPATH=/opt/clawos
exec python3 /opt/clawos/clawctl/main.py "$@"
EOF

cat > "${PKG_ROOT}/usr/bin/nexus" <<'EOF'
#!/usr/bin/env bash
export PYTHONPATH=/opt/clawos
exec python3 /opt/clawos/nexus/cli.py "$@"
EOF

chmod 755 \
  "${PKG_ROOT}/usr/bin/clawos-command-center" \
  "${PKG_ROOT}/usr/bin/clawos-setup" \
  "${PKG_ROOT}/usr/bin/clawos" \
  "${PKG_ROOT}/usr/bin/clawctl" \
  "${PKG_ROOT}/usr/bin/nexus"

install -m 644 "${SCRIPT_DIR}/clawos-command-center.desktop" \
  "${PKG_ROOT}/usr/share/applications/clawos-command-center.desktop"
install -m 644 "${PROJECT_DIR}/packaging/autostart/clawos-setup.desktop" \
  "${PKG_ROOT}/etc/xdg/autostart/clawos-setup.desktop"

mkdir -p "${DIST_DIR}"
dpkg-deb --build "${PKG_ROOT}" "${OUTPUT_DEB}" >/dev/null
sha256sum "${OUTPUT_DEB}" > "${OUTPUT_DEB}.sha256"

echo "Built ${OUTPUT_DEB}"
