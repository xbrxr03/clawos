#!/bin/bash
# ClawOS First Boot — runs once via systemd, shows progress screen
set -e
DONE_FLAG="/var/lib/clawos/.firstboot_done"
LOG="/var/log/clawos/firstboot.log"
mkdir -p /var/lib/clawos /var/log/clawos
exec 2>>"$LOG"

PURPLE="\033[38;5;141m" GREEN="\033[38;5;84m"
AMBER="\033[38;5;220m"  DIM="\033[2m"
BOLD="\033[1m"           RESET="\033[0m"
GREY="\033[38;5;245m"

TOTAL=5
CURRENT=0

draw() {
  clear
  echo -e ""
  echo -e "${PURPLE}${BOLD}  ██████╗██╗      █████╗ ██╗    ██╗ ██████╗ ███████╗"
  echo -e " ██╔════╝██║     ██╔══██╗██║    ██║██╔═══██╗██╔════╝"
  echo -e " ██║     ██║     ███████║██║ █╗ ██║██║   ██║███████╗"
  echo -e " ██║     ██║     ██╔══██║██║███╗██║██║   ██║╚════██║"
  echo -e " ╚██████╗███████╗██║  ██║╚███╔███╔╝╚██████╔╝███████║"
  echo -e "  ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝  ╚═════╝ ╚══════╝${RESET}"
  echo -e ""
  echo -e "  ${DIM}${GREY}First-time setup — runs once, takes about 5 minutes${RESET}"
  echo -e ""
  echo -e "  ${DIM}${GREY}$(date '+%H:%M:%S')${RESET}"
  echo -e ""

  # Progress bar
  local pct=$(( CURRENT * 100 / TOTAL ))
  local filled=$(( pct * 44 / 100 ))
  local empty=$(( 44 - filled ))
  local bar=""
  for ((i=0; i<filled; i++)); do bar+="█"; done
  for ((i=0; i<empty;  i++)); do bar+="░"; done
  echo -e "  ${PURPLE}${bar}${RESET} ${BOLD}${pct}%${RESET}"
  echo -e ""
}

step() {
  CURRENT=$(( CURRENT + 1 ))
  draw
  echo -e "  ${AMBER}◆${RESET}  $1"
  echo -e ""
  echo "[$(date '+%H:%M:%S')] $1" >> "$LOG"
}

done_step() {
  echo -e "  ${GREEN}✓${RESET}  $1"
  echo ""
}

# ── Step 1: Ollama ────────────────────────────────────────────────────────────
step "Starting Ollama... (1/${TOTAL})"
systemctl start ollama 2>/dev/null || true
for i in $(seq 1 30); do
  curl -sf http://localhost:11434/api/tags >/dev/null 2>&1 && break
  sleep 1
done
done_step "Ollama ready"

# ── Step 2: Model download ────────────────────────────────────────────────────
step "Downloading AI model — gemma3:4b (~2GB) (2/${TOTAL})"
echo -e "  ${DIM}${GREY}Needs internet. This is a one-time download.${RESET}"
echo -e ""
ollama pull gemma3:4b 2>&1 | grep -E "pulling|verifying|success|MB|GB" | \
  while IFS= read -r line; do
    echo -e "  ${DIM}${GREY}${line}${RESET}"
  done
done_step "gemma3:4b ready"

# ── Step 3: Bootstrap ─────────────────────────────────────────────────────────
step "Initialising workspace... (3/${TOTAL})"
cd /opt/clawos
PYTHONPATH=/opt/clawos python3 -m bootstrap.bootstrap \
  --profile lowram --yes >> "$LOG" 2>&1
done_step "Workspace ready"

# ── Step 4: Services ──────────────────────────────────────────────────────────
step "Starting services... (4/${TOTAL})"
PYTHONPATH=/opt/clawos bash scripts/dev_boot.sh --no-dashboard >> "$LOG" 2>&1 &
sleep 3
done_step "Services running"

# ── Step 5: Done ──────────────────────────────────────────────────────────────
CURRENT=$TOTAL
draw
echo -e "  ${GREEN}${BOLD}✓  ClawOS is ready.${RESET}"
echo -e ""
echo -e "  ${DIM}${GREY}────────────────────────────────────────────────${RESET}"
echo -e ""
echo -e "  ${AMBER}clawctl chat${RESET}           start chatting with Jarvis"
echo -e "  ${AMBER}clawctl openclaw start${RESET} start OpenClaw"
echo -e "  ${AMBER}openclaw onboard${RESET}       connect WhatsApp"
echo -e "  ${AMBER}http://localhost:7070${RESET}  dashboard"
echo -e ""
echo -e "  ${DIM}${GREY}────────────────────────────────────────────────${RESET}"
echo -e ""

touch "$DONE_FLAG"
echo "[$(date '+%H:%M:%S')] First boot complete." >> "$LOG"
