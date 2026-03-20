#!/bin/bash
# start.sh — start all factory agents
# Pipeline: writing → voice → assembling → visualizing → rendering → uploading

set -a && source ~/factory/.env 2>/dev/null || true && set +a

export FACTORY_ROOT="${FACTORY_ROOT:-$HOME/factory}"
export PYTHONPATH="$FACTORY_ROOT"

cd "$FACTORY_ROOT"

pkill -f "foreman_agent.py"   2>/dev/null || true
pkill -f "monitor_agent.py"   2>/dev/null || true
pkill -f "writer_agent.py"    2>/dev/null || true
pkill -f "voice_agent.py"     2>/dev/null || true
pkill -f "assembler_agent.py" 2>/dev/null || true
pkill -f "visual_agent.py"    2>/dev/null || true
pkill -f "render_agent.py"    2>/dev/null || true
pkill -f "upload_agent.py"    2>/dev/null || true
sleep 1

mkdir -p logs

echo "Starting factory agents..."

python3 agents/foreman_agent.py   >> logs/foreman_agent.log   2>&1 &
python3 agents/monitor_agent.py   >> logs/monitor_agent.log   2>&1 &
python3 agents/writer_agent.py    >> logs/writer_agent.log    2>&1 &
python3 agents/voice_agent.py     >> logs/voice_agent.log     2>&1 &
python3 agents/assembler_agent.py >> logs/assembler_agent.log 2>&1 &
python3 agents/render_agent.py    >> logs/render_agent.log    2>&1 &
python3 agents/upload_agent.py    >> logs/upload_agent.log    2>&1 &

sleep 2

echo ""
echo "✓ Agents started: foreman, monitor, writer, voice, assembler, render, upload"
echo ""
echo "Pipeline: writing → voice → assembling → visualizing → rendering → uploading"
echo ""
echo "NOTE: Visual agent (ComfyUI) not started — run: bash ~/factory/start_visual.sh"
echo ""
echo "Dashboard: http://localhost:7000"
echo "Submit: python3 factoryctl.py new-job \"Your topic\" --template documentary_video"
