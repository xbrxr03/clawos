#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# start_visual.sh — start ComfyUI and the visual agent
# Run this AFTER writing, voice, and assembling are complete
# so ComfyUI gets maximum available RAM

set -a && source ~/factory/.env && set +a
export FACTORY_ROOT=/home/abrar/factory
export PYTHONPATH=/home/abrar/factory

echo "Checking available RAM..."
FREE_MB=$(free -m | awk '/^Mem:/{print $7}')
echo "Available: ${FREE_MB}MB"

if [ "$FREE_MB" -lt 3000 ]; then
    echo ""
    echo "⚠ WARNING: Less than 3GB available."
    echo "  ComfyUI needs ~4GB to run safely."
    echo "  Consider stopping other processes first."
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Kill any leftover ComfyUI
pkill -f "ComfyUI/main.py" 2>/dev/null
sleep 2

echo "Starting ComfyUI..."
cd ~/ComfyUI && python main.py --listen 0.0.0.0 --cpu >> ~/factory/logs/comfyui.log 2>&1 &
COMFY_PID=$!

echo "Waiting for ComfyUI to load (this takes ~30 seconds)..."
for i in $(seq 1 30); do
    sleep 2
    if curl -sf http://localhost:8188/system_stats > /dev/null 2>&1; then
        echo "✓ ComfyUI is ready"
        break
    fi
    echo -n "."
done

echo ""
echo "Starting visual agent..."
cd ~/factory
python agents/visual_agent.py >> ~/factory/logs/visual_agent.log 2>&1 &

echo "✓ Visual agent started"
echo ""
echo "Images will generate one by one. Watch progress:"
echo "  cd ~/factory && ./factoryctl events --tail 20"
echo ""
echo "Dashboard: http://192.168.0.17:7000"
