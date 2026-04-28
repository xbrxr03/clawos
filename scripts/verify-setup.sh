#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# ClawOS Setup Verification Script
# Run after installation to verify everything works

set -uo pipefail

BOLD="\033[1m"
RESET="\033[0m"
G="\033[38;5;84m"
Y="\033[38;5;220m"
R="\033[38;5;203m"
PASS=0
FAIL=0

echo ""
echo -e "  ${BOLD}ClawOS Setup Verification${RESET}"
echo ""

# Helper functions
pass() {
    echo -e "  ${G}✓${RESET} $1"
    ((PASS++))
}

fail() {
    echo -e "  ${R}✗${RESET} $1"
    ((FAIL++))
}

warn() {
    echo -e "  ${Y}⚠${RESET} $1"
}

# Test 1: Installation directory exists
echo "Checking installation..."
if [ -d "$HOME/.clawos-runtime" ]; then
    pass "Installation directory exists"
else
    fail "Installation directory missing"
fi

# Test 2: Python venv exists
if [ -d "$HOME/.clawos-runtime/venv" ]; then
    pass "Python virtualenv exists"
else
    fail "Python virtualenv missing"
fi

# Test 3: Config exists
if [ -f "$HOME/clawos/config/clawos.yaml" ]; then
    pass "Configuration file exists"
    PROFILE=$(grep '_profile:' "$HOME/clawos/config/clawos.yaml" | awk '{print $2}')
    echo "    Profile: $PROFILE"
else
    fail "Configuration missing - bootstrap incomplete"
fi

# Test 4: Ollama running
echo ""
echo "Checking Ollama..."
if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
    pass "Ollama is running"
    MODELS=$(curl -sf http://localhost:11434/api/tags 2>/dev/null | grep -o '"name":"[^"]*"' | wc -l)
    echo "    Models available: $MODELS"
else
    fail "Ollama not running - start with: ollama serve"
fi

# Test 5: Dashboard running
echo ""
echo "Checking dashboard..."
HEALTH=$(curl -sf http://localhost:7070/api/health 2>/dev/null)
if [ $? -eq 0 ]; then
    pass "Dashboard responding on :7070"
    
    # Check individual services
    echo ""
    echo "  Service status:"
    for service in dashd agentd memd modeld policyd setupd; do
        STATUS=$(echo "$HEALTH" | grep -o "\"$service\":{[^}]*}" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
        if [ "$STATUS" = "up" ]; then
            pass "$service is up"
        else
            fail "$service is $STATUS"
        fi
    done
else
    fail "Dashboard not responding"
    echo "    Start with: bash scripts/dev_boot.sh"
fi

# Test 6: Check modeld can reach Ollama
echo ""
echo "Checking model connectivity..."
if echo "$HEALTH" | grep -q '"modeld":{[^}]*"status":"up"'; then
    pass "modeld connected to Ollama"
    DEFAULT_MODEL=$(echo "$HEALTH" | grep -o '"name":"[^"]*"' | head -1 | cut -d'"' -f4)
    echo "    Default model: $DEFAULT_MODEL"
else
    fail "modeld cannot connect to Ollama"
fi

# Test 7: Workspace exists
echo ""
echo "Checking workspace..."
if [ -d "$HOME/clawos/workspace/nexus_default" ]; then
    pass "Default workspace exists"
else
    fail "Default workspace missing"
fi

# Test 8: Memory backends
echo ""
echo "Checking memory system..."
if [ -f "$HOME/clawos/memory/nexus_default.db" ]; then
    pass "SQLite memory database exists"
else
    warn "SQLite memory not initialized yet"
fi

# Summary
echo ""
echo "═══════════════════════════════════════"
echo ""
if [ $FAIL -eq 0 ]; then
    echo -e "  ${G}${BOLD}All checks passed!${RESET}"
    echo ""
    echo "  ClawOS is ready to use:"
    echo "    http://localhost:7070/setup"
    echo ""
    echo "  Quick start:"
    echo "    nexus              - Start chatting"
    echo "    clawctl wf list    - See workflows"
    echo ""
    exit 0
else
    echo -e "  ${R}${BOLD}Some checks failed${RESET}"
    echo ""
    echo "  Passed: $PASS"
    echo "  Failed: $FAIL"
    echo ""
    echo "  See TROUBLESHOOTING.md for help"
    echo ""
    exit 1
fi
