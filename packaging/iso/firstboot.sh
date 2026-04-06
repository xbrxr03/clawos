#!/bin/bash
# ClawOS first-boot compatibility handoff.
# The branded setup experience now lives in the browser-based /setup route.
set -euo pipefail

DONE_FLAG="/var/lib/clawos/.firstboot_done"
LOG="/var/log/clawos/firstboot.log"
mkdir -p /var/lib/clawos /var/log/clawos
exec >>"$LOG" 2>&1

echo "[$(date '+%F %T')] Starting first-boot handoff"

if [ -f "$DONE_FLAG" ]; then
  echo "[$(date '+%F %T')] First boot already completed"
  exit 0
fi

systemctl --user start clawos.service 2>/dev/null || true
systemctl --user start ollama.service 2>/dev/null || systemctl start ollama 2>/dev/null || true

if [ -x /usr/bin/python3 ] && [ -f /opt/clawos/clients/desktop/launch_command_center.py ]; then
  /usr/bin/python3 /opt/clawos/clients/desktop/launch_command_center.py --route /setup --timeout 180 \
    || echo "[$(date '+%F %T')] Browser handoff skipped; desktop autostart will retry"
fi

touch "$DONE_FLAG"
echo "[$(date '+%F %T')] First-boot handoff complete"
