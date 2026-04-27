# ClawOS Troubleshooting Guide

Based on real-world installation experience and community feedback.

---

## Installation Issues

### "sudo: a terminal is required to read the password"

**Problem:** Running installer via pipe doesn't allow password input.  
**Solution:** Use the `-S` flag with sudo:

```bash
# Instead of:
curl -fsSL ... | bash

# Use:
curl -fsSL ... -o /tmp/clawos.sh
{ echo "YOUR_PASSWORD"; } | sudo -S bash /tmp/clawos.sh
```

### "E: Unable to correct problems, you have held broken packages"

**Problem:** Package conflicts during apt install.  
**Solution:**

```bash
# Fix broken packages first
sudo apt-get install -f -y
sudo dpkg --configure -a
sudo apt-get autoremove -y

# Then retry installation
```

### Installation interrupted/timed out

**Problem:** Install script killed during Python package installation.  
**Solution:** Use the resume script:

```bash
cd ~/.clawos-runtime
bash scripts/install-resume.sh
```

---

## Service Issues

### Dashboard not starting (port 7070 in use)

**Problem:** Another service is using port 7070.  
**Solution:**

```bash
# Find what's using the port
sudo lsof -i :7070

# Kill it or use alternative port
export CLAWOS_PORT=7071
bash scripts/dev_boot.sh
```

### clawd service showing as "down"

**Problem:** Clawd (command execution service) not starting.  
**Solution:**

```bash
cd ~/.clawos-runtime
source venv/bin/activate
python3 -m services.clawd.main
```

### voiced service "degraded"

**Problem:** Voice pipeline issues - missing wake word model or audio.  
**Solution:**

```bash
# Check audio devices
arecord -l

# Install wake word model if missing
bash scripts/install_wake_word.sh

# Or disable voice in config
export CLAWOS_VOICE_ENABLED=false
```

### ChromaDB unavailable

**Problem:** Missing chromadb module.  
**Solution:**

```bash
cd ~/.clawos-runtime
source venv/bin/activate
pip install chromadb
```

---

## Model Issues

### "Ollama not running"

**Problem:** Ollama service not started.  
**Solution:**

```bash
# Start Ollama
ollama serve

# Or run in background
ollama serve &
```

### Model download fails

**Problem:** Network issues or model name incorrect.  
**Solution:**

```bash
# Check available models
ollama list

# Pull manually
ollama pull qwen2.5:7b

# Verify
ollama run qwen2.5:7b "Hello"
```

---

## Common User Pain Points (from Reddit/GitHub)

### 1. Typing TTL Bug (GitHub #43204)
**Issue:** Long-running agent runs (>2min) stop showing typing indicator.  
**Status:** Fixed in recent PR - update to latest version.

### 2. Agent tasks not executing (GitHub #40082)
**Issue:** Tasks accepted but agents don't execute them.  
**Workaround:** Restart agentd service:
```bash
pkill -f agentd
python3 -m services.agentd.main
```

### 3. Local conversation agent ignored (Home Assistant #162768)
**Issue:** Voice assistant sometimes ignores local agent.  **Workaround:** Disable cloud voice in settings, ensure local pipeline is default.

---

## Quick Diagnostic Commands

```bash
# Full health check
curl http://localhost:7070/api/health | jq

# Check all services
bash scripts/clawos-status.sh

# View logs
tail -f ~/.clawos-runtime/logs/clawosd.log

# Restart all services
pkill -f "python3 -m services"
bash scripts/dev_boot.sh
```

---

## Getting Help

- **Discord:** https://discord.com/invite/clawd
- **GitHub Issues:** https://github.com/xbrxr03/clawos/issues
- **Documentation:** https://docs.clawos.ai

---

*Last updated: 2026-04-26*
