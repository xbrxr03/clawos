#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# ClawOS ISO hook 05 — Install first-boot wizard systemd unit
# This runs DURING ISO BUILD. The service it installs runs on FIRST BOOT.
set -uo pipefail

echo "[ClawOS hook 05] Installing first-boot wizard service..."

# Create the clawos system user if not exists
if ! id clawos &>/dev/null; then
    useradd -m -s /bin/bash -G sudo clawos 2>/dev/null || true
    echo "clawos:clawos" | chpasswd 2>/dev/null || true
    echo "[hook 05] Created 'clawos' user"
fi

# ── First-boot wizard systemd service ────────────────────────────────────────
cat > /etc/systemd/system/clawos-firstboot.service <<'EOF'
[Unit]
Description=ClawOS First-Boot Setup Wizard
After=network-online.target graphical.target
Wants=network-online.target
ConditionPathExists=!/var/lib/clawos/.setup_complete

[Service]
Type=oneshot
User=clawos
Environment=HOME=/home/clawos
Environment=DISPLAY=:0
ExecStart=/opt/clawos/packaging/iso/firstboot_wizard.sh
RemainAfterExit=yes

[Install]
WantedBy=graphical.target
EOF

systemctl enable clawos-firstboot.service 2>/dev/null || true

# ── First-boot wizard launcher script ────────────────────────────────────────
cat > /opt/clawos/packaging/iso/firstboot_wizard.sh <<'WIZARD'
#!/usr/bin/env bash
# Runs on first boot — opens ClawOS setup wizard in browser
SETUP_FLAG="/var/lib/clawos/.setup_complete"
CLAWOS_DIR="/opt/clawos"
LOG="/var/log/clawos-firstboot.log"

mkdir -p /var/lib/clawos/
exec >> "$LOG" 2>&1

echo "[firstboot] $(date) — Starting ClawOS first boot..."

# Start ClawOS services
cd "$CLAWOS_DIR"
python3 daemon.py &
sleep 8

# Wait for dashd to be ready
for i in $(seq 1 30); do
    if curl -sf http://127.0.0.1:7070/api/health &>/dev/null; then
        break
    fi
    sleep 2
done

# Open setup wizard in browser
if command -v chromium-browser &>/dev/null; then
    su -c "DISPLAY=:0 chromium-browser --new-window --app=http://localhost:7070/setup 2>/dev/null &" clawos
elif command -v xdg-open &>/dev/null; then
    su -c "DISPLAY=:0 xdg-open http://localhost:7070/setup 2>/dev/null &" clawos
fi

echo "[firstboot] Setup wizard launched."

# Mark complete after wizard runs
# (The wizard itself writes this file on Step 8 completion)
# We wait up to 30 minutes for wizard to complete
for i in $(seq 1 180); do
    if [ -f "$SETUP_FLAG" ]; then
        echo "[firstboot] Setup complete. Disabling first-boot service."
        systemctl disable clawos-firstboot.service
        exit 0
    fi
    sleep 10
done

# Timeout — mark as complete anyway so service doesn't loop
touch "$SETUP_FLAG"
echo "[firstboot] Wizard timeout — marked complete."
WIZARD

chmod +x /opt/clawos/packaging/iso/firstboot_wizard.sh
echo "[hook 05] First-boot wizard service installed."

# ── MOTD ─────────────────────────────────────────────────────────────────────
cat > /etc/motd <<'EOF'

  ██████╗██╗      █████╗ ██╗    ██╗ ██████╗ ███████╗
 ██╔════╝██║     ██╔══██╗██║    ██║██╔═══██╗██╔════╝
 ██║     ██║     ███████║██║ █╗ ██║██║   ██║███████╗
 ██║     ██║     ██╔══██║██║███╗██║██║   ██║╚════██║
 ╚██████╗███████╗██║  ██║╚███╔███╔╝╚██████╔╝███████║
  ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝  ╚═════╝ ╚══════╝

  Your personal JARVIS — open source, offline-first.
  Dashboard: http://localhost:7070
  CLI: clawctl status

EOF

echo "[hook 05] Done."
