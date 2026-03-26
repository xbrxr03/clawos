#!/usr/bin/env bash
# clawos status — show ClawOS service health, model, memory, version
# Community request from r/selfhosted: "UX gold for non-tech users"
#
# Usage: clawos status
# Or via the clawos CLI dispatch: clawos status

CLAWOS_HOME="${CLAWOS_HOME:-$HOME/clawos}"

BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

dot_green="  ${GREEN}●${NC}"
dot_red="  ${RED}●${NC}"
dot_yellow="  ${YELLOW}●${NC}"

# --- Version ---
VERSION="0.3.0"
if [ -f "$CLAWOS_HOME/VERSION" ]; then
    VERSION=$(cat "$CLAWOS_HOME/VERSION")
fi

# --- Last update check ---
LAST_CHECK=""
if [ -f "$CLAWOS_HOME/.last-update-check" ]; then
    LAST_CHECK=$(cat "$CLAWOS_HOME/.last-update-check")
fi

# --- Service status check ---
check_service() {
    local unit="$1"
    local port="${2:--}"
    local label="$3"

    local active
    active=$(systemctl --user is-active "$unit" 2>/dev/null || echo "inactive")

    # Also try HTTP health if port given
    local healthy="no"
    if [ "$port" != "-" ]; then
        curl -sf "http://localhost:$port/health" > /dev/null 2>&1 && healthy="yes"
    fi

    if [ "$active" = "active" ]; then
        if [ "$port" = "-" ] || [ "$healthy" = "yes" ]; then
            printf "$dot_green %-14s ${DIM}running${NC}\n" "$label"
        else
            printf "$dot_yellow %-14s ${YELLOW}starting${NC}\n" "$label"
        fi
    elif [ "$active" = "activating" ]; then
        printf "$dot_yellow %-14s ${YELLOW}starting${NC}\n" "$label"
    else
        printf "$dot_red %-14s ${RED}stopped${NC}\n" "$label"
    fi
}

# --- Ollama / model info ---
get_model_info() {
    local model="unknown"
    local vram="—"
    local context="—"

    # Try getting running model from Ollama
    local ollama_resp
    ollama_resp=$(curl -sf http://localhost:11434/api/ps 2>/dev/null)
    if [ -n "$ollama_resp" ]; then
        model=$(echo "$ollama_resp" | python3 -c "
import sys, json
data = json.load(sys.stdin)
models = data.get('models', [])
if models:
    m = models[0]
    print(m.get('name', 'unknown'))
" 2>/dev/null || echo "unknown")
    fi

    # Fall back to config
    if [ "$model" = "unknown" ] && [ -f "$CLAWOS_HOME/clawos_core/constants.py" ]; then
        model=$(grep -oP "DEFAULT_MODEL\s*=\s*'?\K[^'\"]+" "$CLAWOS_HOME/clawos_core/constants.py" 2>/dev/null || echo "unknown")
    fi

    # VRAM from nvidia-smi
    if command -v nvidia-smi &>/dev/null; then
        vram=$(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null | \
               awk -F', ' '{printf "%dMB / %dMB", $1, $2}' || echo "—")
    fi

    echo "$model|$vram"
}

# --- Memory stats ---
get_memory_stats() {
    local pinned_lines=0
    local history_lines=0
    local fts_rows=0
    local chroma_items=0

    local pinned="$CLAWOS_HOME/workspace/jarvis_default/PINNED.md"
    [ -f "$pinned" ] && pinned_lines=$(wc -l < "$pinned" 2>/dev/null || echo 0)

    local history="$CLAWOS_HOME/workspace/jarvis_default/HISTORY.md"
    [ -f "$history" ] && history_lines=$(wc -l < "$history" 2>/dev/null || echo 0)

    # Try memd health endpoint for richer stats
    local memd_resp
    memd_resp=$(curl -sf http://localhost:7073/health 2>/dev/null)
    if [ -n "$memd_resp" ]; then
        fts_rows=$(echo "$memd_resp" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d.get('fts_rows', '—'))
" 2>/dev/null || echo "—")
        chroma_items=$(echo "$memd_resp" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d.get('chroma_items', '—'))
" 2>/dev/null || echo "—")
    fi

    echo "$pinned_lines|$history_lines|$chroma_items|$fts_rows"
}

# --- RAM usage ---
get_ram_usage() {
    free -h 2>/dev/null | awk '/^Mem:/ {printf "%s used / %s total", $3, $2}' || echo "—"
}

# --- Audit log ---
get_audit_count() {
    local audit="$CLAWOS_HOME/logs/audit.jsonl"
    [ -f "$audit" ] && wc -l < "$audit" 2>/dev/null || echo "0"
}

# =================== OUTPUT ===================

echo ""
echo -e "${BOLD}ClawOS${NC} ${DIM}v$VERSION${NC}"
[ -n "$LAST_CHECK" ] && echo -e "${DIM}  Last update check: $LAST_CHECK${NC}"
echo ""

# Services
echo -e "${BOLD}Services${NC}"
check_service "clawos-policyd"    "7074" "policyd"
check_service "clawos-memd"       "7073" "memd"
check_service "clawos-modeld"     "7075" "modeld"
check_service "clawos-toolbridge" "-"    "toolbridge"
check_service "clawos-agentd"     "7072" "agentd"
check_service "clawos-voiced"     "-"    "voiced"
check_service "clawos-clawd"      "7071" "clawd"
check_service "clawos-dashd"      "7070" "dashd"
check_service "clawos-gatewayd"   "-"    "gatewayd"
echo ""

# Model
IFS='|' read -r model vram <<< "$(get_model_info)"
echo -e "${BOLD}Model${NC}"
echo -e "  ${CYAN}$model${NC}"
[ "$vram" != "—" ] && echo -e "  ${DIM}VRAM: $vram${NC}"
echo ""

# Memory
IFS='|' read -r pinned_lines history_lines chroma_items fts_rows <<< "$(get_memory_stats)"
echo -e "${BOLD}Memory${NC}"
echo -e "  ${DIM}PINNED.md${NC}     $pinned_lines lines"
echo -e "  ${DIM}HISTORY.md${NC}    $history_lines entries"
echo -e "  ${DIM}ChromaDB${NC}      $chroma_items items"
echo -e "  ${DIM}SQLite FTS5${NC}   $fts_rows rows"
echo ""

# System
echo -e "${BOLD}System${NC}"
echo -e "  RAM:    $(get_ram_usage)"
echo -e "  Audit:  $(get_audit_count) entries"
echo -e "  Logs:   $CLAWOS_HOME/logs/"
echo ""

# Quick help
echo -e "${DIM}  start: systemctl --user start clawos"
echo -e "  stop:  systemctl --user stop clawos"
echo -e "  chat:  clawos${NC}"
echo ""
