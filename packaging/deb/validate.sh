#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# validate.sh — deb-specific validation for the ClawOS Command Center package
#
# Thin wrapper around ../../scripts/validate_package.sh with deb-specific
# path expectations for the clawos-command-center package.
#
# Usage: ./packaging/deb/validate.sh <path-to-clawos-command-center.deb>
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

DEB_PATH="${1:-}"
if [[ -z "$DEB_PATH" ]]; then
  echo "Usage: $0 <path-to-clawos-command-center.deb>"
  exit 1
fi

# Run generic validation first
bash "$ROOT_DIR/scripts/validate_package.sh" "$DEB_PATH"

echo
echo "=== deb-specific checks ==="

PASS=0
FAIL=0
pass() { echo "  [PASS] $1"; ((PASS++)); }
fail() { echo "  [FAIL] $1"; ((FAIL++)); }

CONTENTS=$(dpkg-deb --contents "$DEB_PATH")
CONTROL=$(dpkg-deb --field "$DEB_PATH")

# Package name must match
PKG_NAME=$(dpkg-deb --field "$DEB_PATH" Package)
if [[ "$PKG_NAME" == "clawos-command-center" ]]; then
  pass "Package name: clawos-command-center"
else
  fail "Package name '$PKG_NAME' != 'clawos-command-center'"
fi

# Desktop entry
if echo "$CONTENTS" | grep -q "clawos-command-center.desktop"; then
  pass "Desktop entry present"
else
  fail "Missing .desktop entry"
fi

# postinst script
if echo "$CONTENTS" | grep -q "postinst"; then
  pass "postinst script present"
else
  fail "Missing postinst script"
fi

# Depends must include python3
if echo "$CONTROL" | grep -q "^Depends:.*python3"; then
  pass "Depends includes python3"
else
  fail "Depends does not include python3"
fi

# Section should be utils or misc
SECTION=$(echo "$CONTROL" | grep "^Section:" | awk '{print $2}')
if [[ "$SECTION" == "utils" || "$SECTION" == "misc" ]]; then
  pass "Section: $SECTION"
else
  fail "Unexpected Section: $SECTION"
fi

echo
echo "  Passed: $PASS"
echo "  Failed: $FAIL"

if (( FAIL > 0 )); then
  echo
  echo "DEB-SPECIFIC VALIDATION FAILED."
  exit 1
else
  echo
  echo "deb-specific checks passed."
fi
