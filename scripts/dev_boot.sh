#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS Development Boot Script
=============================
One-command startup for all ClawOS services.

Usage:
    ./scripts/dev_boot.sh [options]

Options:
    --full          Start all services (default)
    --core          Start only core services
    --ai            Start only AI services  
    --api           Start only API services
    --agents        Start only agent services
    --tools         Start only tool services
    --stop          Stop all running services
    --restart       Restart all services
    --status        Show service status
    --logs          Show service logs
    --doctor        Run diagnostics
"""

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Service definitions
# Format: name:port:module:description
CORE_SERVICES=(
    "dashd:7070:services.dashd.api:Dashboard & Control Center"
    "clawd:7071:services.clawd.main:Core ClawOS Service"
    "memd:7073:services.memd.main:Memory Service"
    "policyd:7074:services.policyd.main:Policy Service"
)

AI_SERVICES=(
    "modeld:7075:services.modeld.main:Model Management"
    "mcpd:7077:services.mcpd.protocol:MCP Protocol Service"
    "voiced:7079:services.voiced.main:Voice Pipeline"
)

AGENT_SERVICES=(
    "agentd:7072:services.agentd.main:Agent Service"
    "agentd_v2:7081:services.agentd.v2.main:Multi-Agent Framework"
    "a2ad:7083:services.a2ad.main:A2A Protocol"
)

TOOL_SERVICES=(
    "desktopd:7080:services.desktopd.main:Desktop Automation"
    "braind:7082:services.braind.main:Second Brain"
    "sandboxd:7085:services.sandboxd.v2.main:Secure Sandbox"
    "visuald:7086:services.visuald.main:Visual Workflow Builder"
)

OBSERVABILITY_SERVICES=(
    "metricd:7076:services.metricd.main:Metrics Collection"
    "observd:7078:services.observd.main:Observability"
    "reminderd:7087:services.reminderd.main:Reminder Daemon"
    "waketrd:7088:services.waketrd.main:Wake Word Trigger"
)

ALL_SERVICES=("${CORE_SERVICES[@]}" "${AI_SERVICES[@]}" "${AGENT_SERVICES[@]}" "${TOOL_SERVICES[@]}" "${OBSERVABILITY_SERVICES[@]}")

# PID file
PID_DIR="${CLAWOS_DIR:-$HOME/.clawos}/run"
mkdir -p "$PID_DIR"
PID_FILE="$PID_DIR/dev_boot.pid"

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

is_running() {
    local port=$1
    lsof -Pi :"$port" -sTCP:LISTEN -t >/dev/null 2>&1
}

check_port() {
    local port=$1
    if is_running "$port"; then
        log_warn "Port $port already in use"
        return 1
    fi
    return 0
}

start_service() {
    local name=$1
    local port=$2
    local module=$3
    local desc=$4
    
    if is_running "$port"; then
        log_warn "$name already running on port $port"
        return 0
    fi
    
    log_info "Starting $name on port $port..."
    
    # Create log file
    local log_file="$PID_DIR/${name}.log"
    
    # Start service in background
    python3 -m "$module" run >"$log_file" 2>&1 &
    local pid=$!
    
    # Save PID
    echo "$name:$pid:$port" >> "$PID_FILE"
    
    # Wait a bit for startup
    sleep 2
    
    # Check if still running
    if kill -0 $pid 2>/dev/null; then
        log_success "$name started (PID: $pid, Port: $port)"
        return 0
    else
        log_error "$name failed to start"
        return 1
    fi
}

stop_service() {
    local name=$1
    local pid=$2
    
    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        log_info "Stopped $name (PID: $pid)"
    fi
}

stop_all() {
    log_info "Stopping all ClawOS services..."
    
    if [[ -f "$PID_FILE" ]]; then
        while IFS=: read -r name pid port; do
            stop_service "$name" "$pid"
        done < "$PID_FILE"
        rm -f "$PID_FILE"
    fi
    
    # Kill any remaining Python processes on ClawOS ports
    for port in 7070 7071 7072 7073 7074 7075 7076 7077 7078 7079 7080 7081 7082 7083 7085 7086; do
        local pids
        pids=$(lsof -Pi :"$port" -sTCP:LISTEN -t 2>/dev/null) || true
        if [[ -n "$pids" ]]; then
            echo "$pids" | xargs kill -9 2>/dev/null || true
        fi
    done
    
    log_success "All services stopped"
}

start_services() {
    local services=("$@")
    local failed=0
    
    log_info "Starting ${#services[@]} services..."
    
    for svc in "${services[@]}"; do
        IFS=: read -r name port module desc <<< "$svc"
        if ! start_service "$name" "$port" "$module" "$desc"; then
            ((failed++)) || true
        fi
        sleep 0.5
    done
    
    if [[ $failed -eq 0 ]]; then
        log_success "All services started successfully"
        return 0
    else
        log_error "$failed services failed to start"
        return 1
    fi
}

show_status() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║           ClawOS Service Status                            ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    
    local all_services=("${ALL_SERVICES[@]}")
    local running=0
    local stopped=0
    
    for svc in "${all_services[@]}"; do
        IFS=: read -r name port module desc <<< "$svc"
        
        if is_running "$port"; then
            printf "  ${GREEN}●${NC} %-12s Port %s - %s\n" "$name" "$port" "$desc"
            ((running++)) || true
        else
            printf "  ${RED}○${NC} %-12s Port %s - %s\n" "$name" "$port" "$desc"
            ((stopped++)) || true
        fi
    done
    
    echo ""
    echo "  Running: $running | Stopped: $stopped"
    echo ""
}

show_logs() {
    local service=$1
    local log_file="$PID_DIR/${service}.log"
    
    if [[ -f "$log_file" ]]; then
        tail -f "$log_file"
    else
        log_error "No log file for $service"
    fi
}

run_diagnostics() {
    log_info "Running ClawOS diagnostics..."
    echo ""
    
    # Check Python
    if command -v python3 &> /dev/null; then
        log_success "Python: $(python3 --version)"
    else
        log_error "Python 3 not found"
        return 1
    fi
    
    # Check Ollama
    if command -v ollama &> /dev/null; then
        log_success "Ollama: $(ollama --version 2>&1 | head -1)"
    else
        log_warn "Ollama not installed (optional)"
    fi
    
    # Check Node.js
    if command -v node &> /dev/null; then
        log_success "Node.js: $(node --version)"
    else
        log_warn "Node.js not installed (optional)"
    fi
    
    # Check dependencies
    log_info "Checking Python dependencies..."
    python3 -c "import fastapi" 2>/dev/null && log_success "FastAPI: OK" || log_warn "FastAPI: Not installed"
    python3 -c "import uvicorn" 2>/dev/null && log_success "Uvicorn: OK" || log_warn "Uvicorn: Not installed"
    python3 -c "import pydantic" 2>/dev/null && log_success "Pydantic: OK" || log_warn "Pydantic: Not installed"
    
    # Check directories
    log_info "Checking directories..."
    [[ -d "$PROJECT_ROOT/clawos_core" ]] && log_success "Core modules: OK" || log_error "Core modules: Missing"
    [[ -d "$PROJECT_ROOT/services" ]] && log_success "Services: OK" || log_error "Services: Missing"
    [[ -d "$PROJECT_ROOT/skills" ]] && log_success "Skills: OK" || log_error "Skills: Missing"
    
    # Check port availability
    log_info "Checking port availability..."
    local ports_in_use=0
    for port in 7070 7071 7072 7073 7074 7075 7076 7077 7078 7079 7080 7081 7082 7083 7085 7086; do
        if is_running "$port"; then
            log_warn "Port $port: In use"
            ((ports_in_use++)) || true
        fi
    done
    
    if [[ $ports_in_use -eq 0 ]]; then
        log_success "All ClawOS ports available"
    fi
    
    echo ""
    log_success "Diagnostics complete"
}

print_usage() {
    cat << 'EOF'
ClawOS Development Boot Script

Usage:
    ./scripts/dev_boot.sh [options]

Options:
    --full          Start all services (default)
    --core          Start core services only
    --ai            Start AI services only
    --api           Start API services only
    --agents        Start agent services only
    --tools         Start tool services only
    --stop          Stop all services
    --restart       Restart all services
    --status        Show service status
    --logs <svc>    Show logs for service
    --doctor        Run diagnostics

Examples:
    ./scripts/dev_boot.sh --full
    ./scripts/dev_boot.sh --core
    ./scripts/dev_boot.sh --stop
    ./scripts/dev_boot.sh --status
    ./scripts/dev_boot.sh --logs clawd

EOF
}

# Main
main() {
    local cmd="${1:---full}"
    
    case "$cmd" in
        --full)
            log_info "Starting full ClawOS stack..."
            start_services "${ALL_SERVICES[@]}"
            sleep 2
            show_status
            ;;
        --core)
            log_info "Starting core services..."
            start_services "${CORE_SERVICES[@]}"
            ;;
        --ai)
            log_info "Starting AI services..."
            start_services "${AI_SERVICES[@]}"
            ;;
        --api)
            log_info "Starting API services..."
            local api_services=("${CORE_SERVICES[@]}" "${AI_SERVICES[@]}")
            start_services "${api_services[@]}"
            ;;
        --agents)
            log_info "Starting agent services..."
            start_services "${AGENT_SERVICES[@]}"
            ;;
        --tools)
            log_info "Starting tool services..."
            start_services "${TOOL_SERVICES[@]}"
            ;;
        --stop)
            stop_all
            ;;
        --restart)
            stop_all
            sleep 2
            log_info "Restarting..."
            start_services "${ALL_SERVICES[@]}"
            ;;
        --status)
            show_status
            ;;
        --logs)
            show_logs "${2:-}"
            ;;
        --doctor)
            run_diagnostics
            ;;
        --help|-h)
            print_usage
            ;;
        *)
            log_error "Unknown option: $cmd"
            print_usage
            exit 1
            ;;
    esac
}

main "$@"
