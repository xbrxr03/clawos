#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# validate_package.sh — validate a ClawOS .deb package before publishing
set -euo pipefail

DEB_PATH="${1:-}"
if [[ -z "$DEB_PATH" ]]; then
  echo "Usage: $0 <path-to-clawos.deb>"
  exit 1
fi

if [[ ! -f "$DEB_PATH" ]]; then
  echo "ERROR: File not found: $DEB_PATH"
  exit 1
fi

PASS=0
FAIL=0

pass() { echo "  [PASS] $1"; ((PASS++)); }
fail() { echo "  [FAIL] $1"; ((FAIL++)); }
section() { echo; echo "=== $1 ==="; }

section "Package integrity"
if dpkg-deb --info "$DEB_PATH" > /dev/null 2>&1; then
  pass "dpkg-deb --info"
else
  fail "dpkg-deb --info (corrupt package)"
fi

if dpkg-deb --contents "$DEB_PATH" > /dev/null 2>&1; then
  pass "dpkg-deb --contents"
else
  fail "dpkg-deb --contents"
fi

section "Control fields"
CONTROL=$(dpkg-deb --field "$DEB_PATH")

check_field() {
  local field="$1"
  if echo "$CONTROL" | grep -q "^${field}:"; then
    pass "Field present: $field"
  else
    fail "Missing field: $field"
  fi
}

check_field "Package"
check_field "Version"
check_field "Architecture"
check_field "Maintainer"
check_field "Description"
check_field "Depends"

PKG_NAME=$(dpkg-deb --field "$DEB_PATH" Package)
PKG_VERSION=$(dpkg-deb --field "$DEB_PATH" Version)
PKG_ARCH=$(dpkg-deb --field "$DEB_PATH" Architecture)

echo "  Package:  $PKG_NAME"
echo "  Version:  $PKG_VERSION"
echo "  Arch:     $PKG_ARCH"

section "Package contents"
CONTENTS=$(dpkg-deb --contents "$DEB_PATH")

check_path() {
  local path="$1"
  if echo "$CONTENTS" | grep -q "$path"; then
    pass "Contains: $path"
  else
    fail "Missing:  $path"
  fi
}

check_path "usr/bin/clawctl"
check_path "usr/lib/clawos"
check_path "usr/share/doc/clawos"
check_path "lib/systemd/system/clawos"

section "File size sanity"
SIZE_BYTES=$(stat -c%s "$DEB_PATH")
SIZE_KB=$((SIZE_BYTES / 1024))
if (( SIZE_KB > 50 )); then
  pass "Package size reasonable: ${SIZE_KB}KB"
else
  fail "Package suspiciously small: ${SIZE_KB}KB"
fi
if (( SIZE_KB < 500000 )); then
  pass "Package size not bloated: ${SIZE_KB}KB"
else
  fail "Package unexpectedly large: ${SIZE_KB}KB (>500MB)"
fi

section "lintian checks"
if command -v lintian &>/dev/null; then
  if lintian --no-tag-display-limit "$DEB_PATH" 2>&1 | grep -q "^E:"; then
    fail "lintian reported errors (run: lintian $DEB_PATH)"
  else
    pass "lintian: no errors"
  fi
  if lintian --no-tag-display-limit "$DEB_PATH" 2>&1 | grep -q "^W:"; then
    echo "  [WARN] lintian warnings present (run: lintian $DEB_PATH)"
  fi
else
  echo "  [SKIP] lintian not installed"
fi

section "Summary"
echo "  Passed: $PASS"
echo "  Failed: $FAIL"

if (( FAIL > 0 )); then
  echo
  echo "VALIDATION FAILED — fix the issues above before publishing."
  exit 1
else
  echo
  echo "All checks passed. Package looks valid."
fi
