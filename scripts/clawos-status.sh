#!/usr/bin/env bash
# clawos status — show ClawOS service health, model, memory, version

CLAWOS_HOME="${CLAWOS_HOME:-$HOME/clawos}"
PIDS_DIR="$CLAWOS_HOME/run"

BOLD='\033[1m'; DIM='\033[2m'; GREEN='\033[0;32m'; RED='\033[0;31m'
YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

dot_green="  ${GREEN}●${NC}"
dot_red="  ${RED}●${NC}"
dot_yellow="  ${YELLOW}●${NC}"

# --- Version ---
VERSION="0.3.0"
[ -f "$CLAWOS_HOME/VERSION" ] && VERSION=$(cat "$CLAWOS_HOME/VERSION")

# --- Service check via PID file ---
check_service() {
    local name="$1"    # short name e.g. policyd
    local label="$2"
    local pidfile="$PIDS_DIR/$name.pid"

    if [ -f "$pidfile" ]; then
        local pid
        pid=$(cat "$pidfile" 2>/dev/null)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            printf "$dot_green %-14s ${DIM}running${NC}\n" "$label"
            return
        fi
    fi
    # Fallback: check if clawos.service itself is active (catches dashd/gatewayd)
    if systemctl --user is-active --quiet "clawos-${name}.service" 2>/dev/null; then
        printf "$dot_green %-14s ${DIM}running${NC}\n" "$label"
        return
    fi
    printf "$dot_red %-14s ${RED}stopped${NC}\n" "$label"
}

# --- Ollama / model info ---
get_model_info() {
    local model="unknown"
    local vram="—"

    local ollama_resp
    ollama_resp=$(curl -sf http://localhost:11434/api/ps 2>/dev/null)
    if [ -n "$ollama_resp" ]; then
        model=$(echo "$ollama_resp" | python3 -c "
import sys, json
data = json.load(sys.stdin)
models = data.get('models', [])
if models:
    print(models[0].get('name', 'unknown'))
else:
    print('idle')
" 2>/dev/null || echo "unknown")
    fi

    if [ "$model" = "unknown" ] && [ -f "$CLAWOS_HOME/clawos_core/constants.py" ]; then
        model=$(grep -oP "DEFAULT_MODEL\s*=\s*'?\K[^'\"]+" \
            "$CLAWOS_HOME/clawos_core/constants.py" 2>/dev/null || echo "unknown")
    fi

    if command -v nvidia-smi &>/dev/null; then
        vram=$(nvidia-smi --query-gpu=memory.used,memory.total \
            --format=csv,noheader,nounits 2>/dev/null | \
            awk -F', ' '{printf "%dMB / %dMB", $1, $2}' || echo "—")
    fi

    echo "$model|$vram"
}

# --- Memory stats ---
get_memory_stats() {
    local pinned_lines=0
    local history_lines=0

    local pinned="$CLAWOS_HOME/workspace/jarvis_default/PINNED.md"
    [ -f "$pinned" ] && pinned_lines=$(wc -l < "$pinned" 2>/dev/null || echo 0)

    local history="$CLAWOS_HOME/workspace/jarvis_default/HISTORY.md"
    [ -f "$history" ] && history_lines=$(wc -l < "$history" 2>/dev/null || echo 0)

    local chroma_items="—"
    local fts_rows="—"

    # Try memd log for last reported stats
    local memd_log="$CLAWOS_HOME/logs/memd.log"
    if [ -f "$memd_log" ]; then
        local last_stats
        last_stats=$(grep -o 'chroma=[0-9]*' "$memd_log" 2>/dev/null | tail -1 | cut -d= -f2)
        [ -n "$last_stats" ] && chroma_items="$last_stats"
        last_stats=$(grep -o 'fts=[0-9]*' "$memd_log" 2>/dev/null | tail -1 | cut -d= -f2)
        [ -n "$last_stats" ] && fts_rows="$last_stats"
    fi

    echo "$pinned_lines|$history_lines|$chroma_items|$fts_rows"
}

# =================== OUTPUT ===================

echo ""
echo -e "${BOLD}ClawOS${NC} ${DIM}v$VERSION${NC}"
echo ""

echo -e "${BOLD}Services${NC}"
check_service "policyd"    "policyd"
check_service "memd"       "memd"
check_service "modeld"     "modeld"
check_service "toolbridge" "toolbridge"
check_service "agentd"     "agentd"
check_service "voiced"     "voiced"
check_service "clawd"      "clawd"
check_service "dashd"      "dashd"
check_service "gatewayd"   "gatewayd"
echo ""

IFS='|' read -r model vram <<< "$(get_model_info)"
echo -e "${BOLD}Model${NC}"
echo -e "  ${CYAN}$model${NC}"
[ "$vram" != "—" ] && echo -e "  ${DIM}VRAM: $vram${NC}"
echo ""

IFS='|' read -r pinned_lines history_lines chroma_items fts_rows <<< "$(get_memory_stats)"
echo -e "${BOLD}Memory${NC}"
echo -e "  ${DIM}PINNED.md${NC}     $pinned_lines lines"
echo -e "  ${DIM}HISTORY.md${NC}    $history_lines entries"
echo -e "  ${DIM}ChromaDB${NC}      $chroma_items items"
echo -e "  ${DIM}SQLite FTS5${NC}   $fts_rows rows"
echo ""

echo -e "${BOLD}System${NC}"
echo -e "  RAM:    $(free -h | awk '/^Mem:/ {printf "%s used / %s total", $3, $2}')"
echo -e "  Audit:  $([ -f "$CLAWOS_HOME/logs/audit.jsonl" ] && wc -l < "$CLAWOS_HOME/logs/audit.jsonl" || echo 0) entries"
echo -e "  Logs:   $CLAWOS_HOME/logs/"
echo ""

echo -e "${DIM}  start: systemctl --user start clawos"
echo -e "  stop:  systemctl --user stop clawos"
echo -e "  chat:  clawos${NC}"
echo ""
