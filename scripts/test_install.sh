#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# test_install.sh — end-to-end install test for ClawOS on Linux
#
# Usage:
#   sudo ./scripts/test_install.sh [--deb <path>] [--skip-uninstall]
#
# Requirements: bash >=4, dpkg, systemctl (systemd), python3
set -euo pipefail

DEB_PATH=""
SKIP_UNINSTALL=false
PASS=0
FAIL=0
WARN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --deb) DEB_PATH="$2"; shift 2 ;;
    --skip-uninstall) SKIP_UNINSTALL=true; shift ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

pass()    { echo "  [PASS] $1"; ((PASS++)); }
fail()    { echo "  [FAIL] $1"; ((FAIL++)); }
warn()    { echo "  [WARN] $1"; ((WARN++)); }
section() { echo; echo "=== $1 ==="; }

# ---------------------------------------------------------------------------
# 0. Pre-flight
# ---------------------------------------------------------------------------
section "Pre-flight checks"

if [[ $EUID -ne 0 ]]; then
  fail "Must run as root (use sudo)"
  exit 1
else
  pass "Running as root"
fi

for cmd in dpkg systemctl python3; do
  if command -v "$cmd" &>/dev/null; then
    pass "Command available: $cmd"
  else
    fail "Command not found: $cmd"
  fi
done

# ---------------------------------------------------------------------------
# 1. Package install
# ---------------------------------------------------------------------------
section "Package installation"

if [[ -n "$DEB_PATH" ]]; then
  if [[ ! -f "$DEB_PATH" ]]; then
    fail "DEB not found: $DEB_PATH"
    exit 1
  fi
  echo "  Installing $DEB_PATH ..."
  if dpkg -i "$DEB_PATH" 2>&1 | tail -5; then
    pass "dpkg -i succeeded"
  else
    fail "dpkg -i failed"
    exit 1
  fi

  # Resolve any broken deps
  if apt-get install -f -y -q 2>/dev/null; then
    pass "apt-get install -f (dep resolution)"
  else
    warn "apt-get install -f unavailable or failed (continuing)"
  fi
else
  warn "No --deb specified; skipping package install (testing already-installed ClawOS)"
fi

# ---------------------------------------------------------------------------
# 2. Binary / filesystem checks
# ---------------------------------------------------------------------------
section "Filesystem checks"

check_exists() {
  local path="$1"
  if [[ -e "$path" ]]; then
    pass "Exists: $path"
  else
    fail "Missing: $path"
  fi
}

check_executable() {
  local path="$1"
  if [[ -x "$path" ]]; then
    pass "Executable: $path"
  else
    fail "Not executable: $path"
  fi
}

check_exists    "/usr/bin/clawctl"
check_executable "/usr/bin/clawctl"
check_exists    "/usr/lib/clawos"
check_exists    "/usr/share/doc/clawos"
check_exists    "/lib/systemd/system/clawos.service"

# ---------------------------------------------------------------------------
# 3. clawctl smoke test
# ---------------------------------------------------------------------------
section "clawctl CLI"

CLAWCTL_VERSION=$(clawctl --version 2>&1 || true)
if echo "$CLAWCTL_VERSION" | grep -qiE "clawos|clawctl|[0-9]+\.[0-9]+"; then
  pass "clawctl --version: $CLAWCTL_VERSION"
else
  fail "clawctl --version returned unexpected output: $CLAWCTL_VERSION"
fi

CLAWCTL_HELP=$(clawctl --help 2>&1 || true)
if echo "$CLAWCTL_HELP" | grep -qi "usage\|commands\|options"; then
  pass "clawctl --help shows usage"
else
  fail "clawctl --help output unexpected: $(echo "$CLAWCTL_HELP" | head -3)"
fi

# ---------------------------------------------------------------------------
# 4. Systemd service
# ---------------------------------------------------------------------------
section "Systemd service"

systemctl daemon-reload 2>/dev/null && pass "systemctl daemon-reload" || warn "daemon-reload failed (non-fatal)"

if systemctl enable clawos 2>/dev/null; then
  pass "systemctl enable clawos"
else
  fail "systemctl enable clawos"
fi

if systemctl start clawos 2>/dev/null; then
  pass "systemctl start clawos"
else
  fail "systemctl start clawos"
fi

sleep 2

SERVICE_STATUS=$(systemctl is-active clawos 2>/dev/null || true)
if [[ "$SERVICE_STATUS" == "active" ]]; then
  pass "Service is active"
else
  fail "Service status: $SERVICE_STATUS"
  echo "  --- journalctl tail ---"
  journalctl -u clawos -n 20 --no-pager 2>/dev/null || true
  echo "  -----------------------"
fi

# ---------------------------------------------------------------------------
# 5. API health check
# ---------------------------------------------------------------------------
section "Dashboard API"

API_BASE="http://127.0.0.1:7474"
API_READY=false

for i in {1..10}; do
  if curl -sf "$API_BASE/api/health" -o /dev/null 2>/dev/null; then
    API_READY=true
    break
  fi
  sleep 1
done

if $API_READY; then
  pass "API /api/health reachable"
else
  fail "API not reachable at $API_BASE after 10s"
fi

if $API_READY; then
  HEALTH=$(curl -sf "$API_BASE/api/health" 2>/dev/null || echo '{}')
  if echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('status')=='ok'" 2>/dev/null; then
    pass "API health status=ok"
  else
    fail "API health payload unexpected: $HEALTH"
  fi

  SESSION=$(curl -sf "$API_BASE/api/session" 2>/dev/null || echo '{}')
  if echo "$SESSION" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
    pass "GET /api/session returns valid JSON"
  else
    fail "GET /api/session returned invalid JSON"
  fi
fi

# ---------------------------------------------------------------------------
# 6. Python package check
# ---------------------------------------------------------------------------
section "Python package"

if python3 -c "import clawos_core" 2>/dev/null; then
  pass "import clawos_core"
else
  fail "import clawos_core (package not importable)"
fi

if python3 -c "from clawos_core.catalog import list_workflow_programs; list_workflow_programs()" 2>/dev/null; then
  pass "clawos_core.catalog.list_workflow_programs() OK"
else
  warn "clawos_core.catalog not importable (non-fatal if installed as binary-only)"
fi

# ---------------------------------------------------------------------------
# 7. Uninstall (optional)
# ---------------------------------------------------------------------------
if ! $SKIP_UNINSTALL && [[ -n "$DEB_PATH" ]]; then
  section "Uninstall"

  systemctl stop clawos 2>/dev/null && pass "systemctl stop clawos" || warn "stop failed (may already be stopped)"
  systemctl disable clawos 2>/dev/null && pass "systemctl disable clawos" || warn "disable failed"

  PKG_NAME=$(dpkg-deb --field "$DEB_PATH" Package 2>/dev/null || echo "clawos")
  if dpkg -r "$PKG_NAME" 2>/dev/null; then
    pass "dpkg -r $PKG_NAME"
  else
    fail "dpkg -r $PKG_NAME"
  fi

  if [[ ! -x "/usr/bin/clawctl" ]]; then
    pass "clawctl removed after uninstall"
  else
    fail "clawctl still present after uninstall"
  fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
section "Summary"
echo "  Passed:   $PASS"
echo "  Warned:   $WARN"
echo "  Failed:   $FAIL"

if (( FAIL > 0 )); then
  echo
  echo "INSTALL TEST FAILED — $FAIL check(s) did not pass."
  exit 1
else
  echo
  echo "All checks passed. ClawOS installs and runs correctly."
fi
