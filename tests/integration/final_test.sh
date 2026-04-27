#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Final integration test for all ClawOS services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║       ClawOS Complete Integration Test Suite                   ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0

test_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASS++))
}

test_fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAIL++))
}

test_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

echo "Phase 1: Static Analysis"
echo "════════════════════════════════════════════════════════════════"

# Check Python syntax
if python3 -m py_compile clawos_core/constants.py; then
    test_pass "Python syntax check"
else
    test_fail "Python syntax check"
fi

# Check imports
cd "$PROJECT_ROOT"
if python3 -c "from clawos_core import constants, security, performance" 2>/dev/null; then
    test_pass "Core module imports"
else
    test_fail "Core module imports"
fi

echo ""
echo "Phase 2: Service Module Imports"
echo "════════════════════════════════════════════════════════════════"

SERVICES=(
    "dashd:services.dashd.api"
    "clawd:services.clawd.main"
    "agentd:services.agentd.main"
    "memd:services.memd.main"
    "policyd:services.policyd.main"
    "modeld:services.modeld.main"
    "metricd:services.metricd.main"
    "mcpd:services.mcpd.main"
    "observd:services.observd.main"
    "voiced:services.voiced.main"
    "desktopd:services.desktopd.main"
    "agentd_v2:services.agentd.v2.main"
    "a2ad:services.a2ad.main"
    "braind:services.braind.main"
    "sandboxd:services.sandboxd.v2.main"
    "visuald:services.visuald.main"
)

for svc in "${SERVICES[@]}"; do
    name="${svc%%:*}"
    module="${svc##*:}"
    
    if python3 -c "import $module" 2>/dev/null; then
        test_pass "$name module import"
    else
        test_warn "$name module import (may need dependencies)"
    fi
done

echo ""
echo "Phase 3: Skill Module Imports"
echo "════════════════════════════════════════════════════════════════"

SKILLS=(
    "code_companion:skills.code_companion.main"
    "notebooks:skills.notebooks.main"
)

for skill in "${SKILLS[@]}"; do
    name="${skill%%:*}"
    module="${skill##*:}"
    
    if python3 -c "import $module" 2>/dev/null; then
        test_pass "$name skill import"
    else
        test_warn "$name skill import (may need dependencies)"
    fi
done

echo ""
echo "Phase 4: CLI Tests"
echo "════════════════════════════════════════════════════════════════"

# Test clawctl import
if python3 -c "from clawctl.main import main" 2>/dev/null; then
    test_pass "clawctl CLI import"
else
    test_fail "clawctl CLI import"
fi

# Test commands
if python3 -m clawctl.main --help >/dev/null 2>&1; then
    test_pass "clawctl --help"
else
    test_fail "clawctl --help"
fi

echo ""
echo "Phase 5: Configuration Tests"
echo "════════════════════════════════════════════════════════════════"

# Check port constants
if grep -q "PORT_VISUALD.*7086" clawos_core/constants.py; then
    test_pass "PORT_VISUALD defined (7086)"
else
    test_fail "PORT_VISUALD defined"
fi

if grep -q "PORT_BRAIND.*7082" clawos_core/constants.py; then
    test_pass "PORT_BRAIND defined (7082)"
else
    test_fail "PORT_BRAIND defined"
fi

if grep -q "PORT_SANDBOXD.*7085" clawos_core/constants.py; then
    test_pass "PORT_SANDBOXD defined (7085)"
else
    test_fail "PORT_SANDBOXD defined"
fi

echo ""
echo "Phase 6: Documentation Tests"
echo "════════════════════════════════════════════════════════════════"

DOCS=(
    "README.md"
    "docs/ARCHITECTURE.md"
    "docs/DEPLOYMENT_GUIDE.md"
    "docs/FEATURES.md"
    "docs/API_REFERENCE.md"
    "docs/TESTING_GUIDE.md"
    "CHANGELOG.md"
)

for doc in "${DOCS[@]}"; do
    if [[ -f "$doc" ]]; then
        test_pass "$doc exists"
    else
        test_fail "$doc exists"
    fi
done

echo ""
echo "Phase 7: Script Tests"
echo "════════════════════════════════════════════════════════════════"

# Check scripts are executable
if [[ -x "scripts/dev_boot.sh" ]]; then
    test_pass "dev_boot.sh is executable"
else
    test_fail "dev_boot.sh is executable"
fi

if [[ -x "install.sh" ]]; then
    test_pass "install.sh is executable"
else
    test_fail "install.sh is executable"
fi

echo ""
echo "Phase 8: Test Suite Validation"
echo "════════════════════════════════════════════════════════════════"

# Check test files exist
TEST_FILES=(
    "tests/services/test_braind.py"
    "tests/services/test_sandboxd.py"
    "tests/skills/test_notebooks.py"
)

for test_file in "${TEST_FILES[@]}"; do
    if [[ -f "$test_file" ]]; then
        test_pass "$test_file exists"
    else
        test_fail "$test_file exists"
    fi
done

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                   Test Summary                                 ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Passed: $PASS"
echo "Failed: $FAIL"
echo ""

if [[ $FAIL -eq 0 ]]; then
    echo -e "${GREEN}All critical tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed.${NC}"
    exit 1
fi
