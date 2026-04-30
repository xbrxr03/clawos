#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Morning Briefing CLI Helper
# Usage: ./demos/morning_briefing.sh

set -e

CLAWOS_HOST="${CLAWOS_HOST:-http://localhost:7088}"

echo "🏠 ClawOS Morning Briefing"
echo "=========================="
echo ""

# Check if waketrd is running
if ! curl -s "$CLAWOS_HOST/health" > /dev/null 2>&1; then
    echo "❌ waketrd not running on port 7088"
    echo "   Start it with: bash scripts/dev_boot.sh --full"
    exit 1
fi

# Trigger the briefing
echo "🎤 Triggering morning briefing..."
echo ""

RESPONSE=$(curl -s -X POST "$CLAWOS_HOST/trigger" 2>&1)

# Parse response
if echo "$RESPONSE" | grep -q '"triggered":true'; then
    ACTION=$(echo "$RESPONSE" | grep -o '"action":"[^"]*"' | cut -d'"' -f4)
    TEXT=$(echo "$RESPONSE" | grep -o '"text":"[^"]*"' | cut -d'"' -f4 | sed 's/\\n/\n/g')
    
    echo "✅ Briefing delivered!"
    echo ""
    echo "Action: $ACTION"
    echo ""
    echo "---"
    echo "$TEXT"
    echo "---"
else
    echo "❌ Briefing failed"
    echo "Response: $RESPONSE"
    exit 1
fi
