#!/bin/bash
# start.sh — start all factory agents in parallel
FACTORY_DIR="${FACTORY_ROOT:-$HOME/factory}"
ENV_FILE="$FACTORY_DIR/.env"

if [[ -f "$ENV_FILE" ]]; then
    while IFS='=' read -r key value; do
        [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
        export "${key// /}=${value// /}"
    done < <(grep -v '^\s*#' "$ENV_FILE" | grep -v '^\s*$')
fi

export FACTORY_ROOT="$FACTORY_DIR"
export PYTHONPATH="$FACTORY_DIR"
cd "$FACTORY_DIR"
mkdir -p logs

# Kill any stale agents
for agent in foreman_agent monitor_agent writer_agent voice_agent \
             assembler_agent visual_agent render_agent upload_agent; do
    pkill -f "${agent}.py" 2>/dev/null || true
done
sleep 1

# Start ALL agents in parallel — no agent killing, 32GB RAM
python3 agents/foreman_agent.py   >> logs/foreman_agent.log   2>&1 &
python3 agents/monitor_agent.py   >> logs/monitor_agent.log   2>&1 &
python3 agents/writer_agent.py    >> logs/writer_agent.log    2>&1 &
python3 agents/voice_agent.py     >> logs/voice_agent.log     2>&1 &
python3 agents/assembler_agent.py >> logs/assembler_agent.log 2>&1 &
python3 agents/visual_agent.py    >> logs/visual_agent.log    2>&1 &
python3 agents/render_agent.py    >> logs/render_agent.log    2>&1 &
python3 agents/upload_agent.py    >> logs/upload_agent.log    2>&1 &

sleep 2
IP=$(hostname -I | awk '{print $1}' 2>/dev/null || echo localhost)
echo "Content Factory started — all agents running in parallel"
echo "Dashboard: http://$IP:7000"
echo "Submit:    cd ~/factory && python3 factoryctl.py new-job \"Your topic\" --template documentary_video"
