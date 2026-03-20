#!/bin/bash
echo "Stopping all factory agents and ComfyUI..."
pkill -f foreman_agent.py   2>/dev/null
pkill -f monitor_agent.py   2>/dev/null
pkill -f writer_agent.py    2>/dev/null
pkill -f visual_agent.py    2>/dev/null
pkill -f voice_agent.py     2>/dev/null
pkill -f assembler_agent.py 2>/dev/null
pkill -f "ComfyUI/main.py"  2>/dev/null
sleep 2
echo "All stopped."
