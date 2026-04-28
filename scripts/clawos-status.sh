#!/bin/bash
# ClawOS Service Status Checker
# Usage: bash scripts/clawos-status.sh

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║        ClawOS Service Status         ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# Check dashboard health
HEALTH=$(curl -sf http://localhost:7070/api/health 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "  Dashboard: ✅ Running on http://localhost:7070"
    echo ""
    
    # Parse service statuses
    echo "  Services:"
    for service in dashd agentd memd modeld policyd setupd clawd voiced; do
        STATUS=$(echo "$HEALTH" | grep -o "\"$service\":{[^}]*}" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
        LATENCY=$(echo "$HEALTH" | grep -o "\"$service\":{[^}]*}" | grep -o '"latency_ms":[0-9]*' | cut -d':' -f2)
        
        if [ "$STATUS" = "up" ]; then
            echo "    ✅ $service (${LATENCY}ms)"
        elif [ "$STATUS" = "down" ]; then
            echo "    ❌ $service (down)"
        else
            echo "    ⚠️  $service ($STATUS)"
        fi
    done
    
    echo ""
    MODEL=$(echo "$HEALTH" | grep -o '"name":"[^"]*"' | head -1 | cut -d'"' -f4)
    echo "  Model: $MODEL"
else
    echo "  Dashboard: ❌ Not responding"
    echo "  Run: bash scripts/dev_boot.sh"
fi

echo ""
echo "  ═══════════════════════════════════════"
echo "  Quick commands:"
echo "    nexus              - Start chat"
echo "    clawctl status     - Full status"
echo "  ═══════════════════════════════════════"
echo ""
