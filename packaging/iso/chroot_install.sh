#!/bin/bash
# Runs inside chroot during ISO build.
# Installs all ClawOS deps, bakes OpenClaw offline config.
set -e
export DEBIAN_FRONTEND=noninteractive
export HOME=/root

echo "[ClawOS] System packages ..."
apt-get update -qq
apt-get install -y -qq \
  python3 python3-pip \
  curl wget git sqlite3 \
  alsa-utils pulseaudio pipewire pipewire-alsa \
  ffmpeg build-essential

echo "[ClawOS] Node.js 22+ ..."
curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - >/dev/null 2>&1
apt-get install -y -qq nodejs

echo "[ClawOS] Python packages ..."
pip3 install --break-system-packages -q \
  pyyaml aiohttp fastapi uvicorn ollama click \
  openai-whisper piper-tts 2>/dev/null || true

echo "[ClawOS] Ollama ..."
curl -fsSL https://ollama.com/install.sh | sh >/dev/null 2>&1 || true

echo "[ClawOS] OpenClaw ..."
npm install -g openclaw@latest --quiet

echo "[ClawOS] OpenClaw offline config ..."
mkdir -p /root/.openclaw/agents/main/agent
cat > /root/.openclaw/agents/main/agent/auth-profiles.json << 'JSON'
{"ollama:local":{"type":"token","provider":"ollama","token":"ollama-local"},"lastGood":{"ollama":"ollama:local"}}
JSON
cat > /root/.openclaw/openclaw.json << 'JSON'
{"models":{"providers":{"ollama":{"baseUrl":"http://127.0.0.1:11434/v1","apiKey":"ollama-local","api":"openai-completions","models":[{"id":"gemma3:4b","name":"gemma3:4b","contextWindow":4096,"maxOutput":2048,"inputCostPer1M":0,"outputCostPer1M":0}]}}},"agents":{"defaults":{"model":{"primary":"ollama/gemma3:4b"}}},"cloud":{"enabled":false,"fallback":false},"network":{"mode":"offline","allow_local_network":true}}
JSON

echo "[ClawOS] ClawOS setup ..."
cd /opt/clawos

# clawctl in PATH
cat > /usr/local/bin/clawctl << 'CMD'
#!/bin/bash
PYTHONPATH=/opt/clawos python3 /opt/clawos/clawctl/main.py "$@"
CMD
chmod +x /usr/local/bin/clawctl

# First boot service
cat > /etc/systemd/system/clawos-firstboot.service << 'UNIT'
[Unit]
Description=ClawOS First Boot
After=network.target ollama.service
ConditionPathExists=!/var/lib/clawos/.firstboot_done

[Service]
Type=oneshot
ExecStart=/opt/clawos/packaging/iso/firstboot.sh
RemainAfterExit=yes
StandardOutput=journal

[Install]
WantedBy=multi-user.target
UNIT
systemctl enable clawos-firstboot.service 2>/dev/null || true

# Ollama systemd
cat > /etc/systemd/system/ollama.service << 'UNIT'
[Unit]
Description=Ollama AI
After=network-online.target

[Service]
ExecStart=/usr/local/bin/ollama serve
Restart=always
RestartSec=3
Environment=HOME=/root

[Install]
WantedBy=multi-user.target
UNIT
systemctl enable ollama.service 2>/dev/null || true

# MOTD
cat > /etc/motd << 'MOTD'

  ██████╗██╗      █████╗ ██╗    ██╗ ██████╗ ███████╗
 ██╔════╝██║     ██╔══██╗██║    ██║██╔═══██╗██╔════╝
 ██║     ██║     ███████║██║ █╗ ██║██║   ██║███████╗
 ██║     ██║     ██╔══██║██║███╗██║██║   ██║╚════██║
 ╚██████╗███████╗██║  ██║╚███╔███╔╝╚██████╔╝███████║
  ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝  ╚═════╝ ╚══════╝

  Flash it. Boot it. Your AI is ready.
  No API keys. No monthly bill. No setup.

  clawctl status         check services
  clawctl chat           start chatting
  clawctl openclaw start start OpenClaw
  openclaw onboard       connect WhatsApp
  http://localhost:7070  dashboard

MOTD

echo "[ClawOS] Chroot install complete."
