#!/usr/bin/env bash
# clawos status — ClawOS service health and runtime info

CLAWOS_HOME="${CLAWOS_HOME:-$HOME/clawos}"
BOLD='\033[1m'; DIM='\033[2m'; GREEN='\033[0;32m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'

VERSION="0.3.0"
[ -f "$CLAWOS_HOME/VERSION" ] && VERSION=$(cat "$CLAWOS_HOME/VERSION")

echo ""
echo -e "${BOLD}ClawOS${NC} ${DIM}v$VERSION${NC}"
echo ""

# --- Main service ---
echo -e "${BOLD}Service${NC}"
if systemctl --user is-active --quiet clawos.service 2>/dev/null; then
    UPTIME=$(systemctl --user show clawos.service --property=ActiveEnterTimestamp \
        | cut -d= -f2)
    echo -e "  ${GREEN}●${NC} clawos       ${DIM}running${NC}"
    echo -e "    ${DIM}since $UPTIME${NC}"
else
    echo -e "  ${RED}●${NC} clawos       ${RED}stopped${NC}"
fi

# Dashboard
if curl -sf http://localhost:7070 > /dev/null 2>&1; then
    echo -e "  ${GREEN}●${NC} dashboard    ${DIM}http://localhost:7070${NC}"
else
    echo -e "  ${RED}●${NC} dashboard    ${RED}not responding${NC}"
fi
echo ""

# --- Model ---
echo -e "${BOLD}Model${NC}"
MODEL=$(curl -sf http://localhost:11434/api/ps 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)
m=d.get('models',[])
print(m[0]['name'] if m else 'idle')
" 2>/dev/null || echo "unknown")
echo -e "  ${CYAN}$MODEL${NC}"
if command -v nvidia-smi &>/dev/null; then
    VRAM=$(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null \
        | awk -F', ' '{printf "%dMB / %dMB", $1, $2}')
    echo -e "  ${DIM}VRAM: $VRAM${NC}"
fi
echo ""

# --- Memory ---
echo -e "${BOLD}Memory${NC}"
PINNED="$CLAWOS_HOME/workspace/jarvis_default/PINNED.md"
HISTORY="$CLAWOS_HOME/workspace/jarvis_default/HISTORY.md"
echo -e "  ${DIM}PINNED.md${NC}    $([ -f "$PINNED" ] && wc -l < "$PINNED" || echo 0) lines"
echo -e "  ${DIM}HISTORY.md${NC}   $([ -f "$HISTORY" ] && wc -l < "$HISTORY" || echo 0) entries"
echo ""

# --- System ---
echo -e "${BOLD}System${NC}"
echo -e "  RAM:    $(free -h | awk '/^Mem:/ {printf "%s used / %s total", $3, $2}')"
echo -e "  Audit:  $([ -f "$CLAWOS_HOME/logs/audit.jsonl" ] && wc -l < "$CLAWOS_HOME/logs/audit.jsonl" || echo 0) entries"
echo -e "  Log:    $CLAWOS_HOME/logs/clawosd.log"
echo ""
echo -e "${DIM}  start: systemctl --user start clawos"
echo -e "  stop:  systemctl --user stop clawos"
echo -e "  chat:  clawos${NC}"
echo ""
