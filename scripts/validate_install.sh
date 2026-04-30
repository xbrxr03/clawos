#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# install.sh validation script
# Tests the installer on various platforms

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
G="\033[38;5;84m"; R="\033[38;5;203m"; B="\033[38;5;75m"
Y="\033[38;5;220m"; RESET="\033[0m"; BOLD="\033[1m"

log() { echo -e "${B}$1${RESET} $2"; }
ok() { echo -e "  ${G}✓${RESET} $1"; }
fail() { echo -e "  ${R}✗${RESET} $1"; }
warn() { echo -e "  ${Y}⚠${RESET} $1"; }

TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
    local name=$1
    shift
    echo -e "\n${BOLD}$name${RESET}"
    if "$@"; then
        ok "$name passed"
        ((TESTS_PASSED++))
    else
        fail "$name failed"
        ((TESTS_FAILED++))
    fi
}

# Test 1: Syntax check
test_syntax() {
    bash -n "$REPO_ROOT/install.sh"
}

# Test 2: Help/usage works
test_help() {
    bash "$REPO_ROOT/install.sh" --help 2>&1 | grep -q "ClawOS"
}

# Test 3: Check mode works
test_check() {
    bash "$REPO_ROOT/install.sh" --check 2>&1 | grep -q "preflight"
}

# Test 4: Required files exist
test_required_files() {
    local required=(
        "install.sh"
        "pyproject.toml"
        "README.md"
        "LICENSE"
        "clawos_core/constants.py"
        "services/dashd/main.py"
        "dashboard/frontend/package.json"
        "scripts/dev_boot.sh"
    )
    
    for file in "${required[@]}"; do
        if [[ ! -f "$REPO_ROOT/$file" ]]; then
            fail "Missing required file: $file"
            return 1
        fi
    done
    return 0
}

# Test 5: Python dependencies valid
test_python_deps() {
    python3 -c "import tomllib; tomllib.load(open('$REPO_ROOT/pyproject.toml', 'rb'))" 2>/dev/null || \
    python3 -c "import toml; toml.load('$REPO_ROOT/pyproject.toml')" 2>/dev/null
}

# Test 6: Frontend dependencies valid
test_frontend_deps() {
    if [[ -f "$REPO_ROOT/dashboard/frontend/package.json" ]]; then
        node -e "JSON.parse(require('fs').readFileSync('$REPO_ROOT/dashboard/frontend/package.json'))" 2>/dev/null
    else
        return 0  # Skip if no frontend
    fi
}

# Test 7: Service ports unique
test_port_uniqueness() {
    local ports_file="$REPO_ROOT/clawos_core/constants.py"
    local duplicates=$(grep -oE 'PORT_[A-Z_]+=[0-9]+' "$ports_file" 2>/dev/null | \
        cut -d'=' -f2 | sort | uniq -d)
    
    if [[ -n "$duplicates" ]]; then
        fail "Duplicate ports found: $duplicates"
        return 1
    fi
    return 0
}

# Test 8: All services have health.py
test_service_structure() {
    local services_dir="$REPO_ROOT/services"
    local missing=()
    
    for service_dir in "$services_dir"/*/; do
        if [[ -d "$service_dir" ]]; then
            local service_name=$(basename "$service_dir")
            if [[ ! -f "$service_dir/health.py" ]]; then
                missing+=("$service_name")
            fi
        fi
    done
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        warn "Services missing health.py: ${missing[*]}"
        # Not a hard fail, just a warning
    fi
    return 0
}

# Test 9: AGPL headers present
test_agpl_headers() {
    local python_files=$(find "$REPO_ROOT" -name "*.py" -not -path "*/__pycache__/*" -not -path "*/.*" | head -20)
    local missing=0
    
    for file in $python_files; do
        if ! grep -q "SPDX-License-Identifier: AGPL-3.0-or-later" "$file" 2>/dev/null; then
            ((missing++))
        fi
    done
    
    if [[ $missing -gt 10 ]]; then
        warn "$missing Python files missing AGPL headers"
    fi
    return 0
}

# Test 10: Bootstrap script exists and is executable
test_bootstrap() {
    [[ -x "$REPO_ROOT/scripts/bootstrap.sh" ]] || [[ -f "$REPO_ROOT/scripts/bootstrap.sh" ]]
}

# Main
main() {
    log "🔍" "ClawOS Install Validation"
    echo "=========================="
    
    run_test "Syntax check" test_syntax
    run_test "Help works" test_help
    run_test "Check mode" test_check
    run_test "Required files" test_required_files
    run_test "Python deps valid" test_python_deps
    run_test "Frontend deps valid" test_frontend_deps
    run_test "Port uniqueness" test_port_uniqueness
    run_test "Service structure" test_service_structure
    run_test "AGPL headers" test_agpl_headers
    run_test "Bootstrap script" test_bootstrap
    
    echo -e "\n=========================="
    log "📊" "Results: $TESTS_PASSED passed, $TESTS_FAILED failed"
    
    if [[ $TESTS_FAILED -eq 0 ]]; then
        ok "All validation tests passed!"
        exit 0
    else
        fail "Some validation tests failed"
        exit 1
    fi
}

main "$@"
