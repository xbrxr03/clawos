# ClawOS Deployment Guide

Complete guide for deploying ClawOS in various environments.

## Quick Start

```bash
# 1. Clone repository
git clone https://github.com/xbrxr03/clawos.git
cd clawos

# 2. Install dependencies
./install.sh

# 3. Start services
./scripts/dev_boot.sh --full

# 4. Verify
clawctl status
```

## Installation Methods

### Method 1: Automated Install (Recommended)

```bash
./install.sh --full
```

This installs:
- Python dependencies
- Ollama (if not present)
- System services
- Configuration files

### Method 2: Manual Install

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install optional dependencies for all services
pip install -r requirements-optional.txt
```

### Method 3: Docker (Coming Soon)

```bash
docker-compose up -d
```

## Service Configuration

### Core Services (Required)

| Service | Port | Purpose | Config File |
|---------|------|---------|-------------|
| dashd | 7070 | Dashboard | `services/dashd/config.yaml` |
| clawd | 7071 | Core API | `services/clawd/config.yaml` |
| memd | 7073 | Memory | `services/memd/config.yaml` |
| policyd | 7074 | Policy Engine | `services/policyd/config.yaml` |

### AI Services (Recommended)

| Service | Port | Purpose | Requires |
|---------|------|---------|----------|
| modeld | 7075 | Model Management | Ollama |
| mcpd | 7077 | MCP Protocol | - |
| voiced | 7079 | Voice Pipeline | sox, portaudio |

### Agent Services (Optional)

| Service | Port | Purpose |
|---------|------|---------|
| agentd | 7072 | Basic Agents |
| agentd_v2 | 7081 | Multi-Agent Framework |
| a2ad | 7083 | A2A Protocol |

### Tool Services (Optional)

| Service | Port | Purpose | Requires |
|---------|------|---------|----------|
| desktopd | 7080 | Desktop Automation | X11/wayland |
| braind | 7082 | Second Brain | - |
| sandboxd | 7085 | Secure Sandbox | Docker (opt) |
| visuald | 7086 | Visual Workflows | - |

## Deployment Scenarios

### Scenario 1: Personal Desktop

Minimal setup for personal use:

```bash
# Start core + AI only
./scripts/dev_boot.sh --core --ai

# Or individually
./scripts/dev_boot.sh --core    # dashd, clawd, memd, policyd
./scripts/dev_boot.sh --ai      # modeld, mcpd, voiced
```

### Scenario 2: Development Server

Full stack for development:

```bash
# Everything
./scripts/dev_boot.sh --full

# Or start specific groups
./scripts/dev_boot.sh --agents  # agent services
./scripts/dev_boot.sh --tools   # tool services
```

### Scenario 3: Production Server

Secure production deployment:

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with production values

# 2. Run security hardening
clawctl doctor --fix

# 3. Start with systemd
sudo systemctl enable clawos
cdawos start --production
```

### Scenario 4: Headless/Server

No desktop automation:

```bash
# Skip desktop services
./scripts/dev_boot.sh --core --ai --agents --api
```

## Configuration Files

### Global Config

`~/.clawos/config.yaml`:

```yaml
clawos:
  version: "0.1.0"
  environment: production
  
  logging:
    level: info
    file: ~/.clawos/logs/clawos.log
    
  security:
    api_key_required: true
    allowed_hosts:
      - "localhost"
      - "127.0.0.1"
      
  ollama:
    host: http://localhost:11434
    default_model: llama3.2
```

### Service-Specific Config

Each service can have its own config in `~/.clawos/services/<service>.yaml`.

Example for modeld:

```yaml
modeld:
  default_model: "llama3.2"
  temperature: 0.7
  max_tokens: 4096
  
  models:
    llama3.2:
      context_window: 128000
    qwen2.5-coder:
      context_window: 32000
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CLAWOS_ENV` | Environment mode | `development` |
| `CLAWOS_DIR` | Data directory | `~/.clawos` |
| `CLAWOS_LOG_LEVEL` | Logging level | `info` |
| `OLLAMA_HOST` | Ollama server | `http://localhost:11434` |
| `OPENAI_API_KEY` | OpenAI key (optional) | - |
| `ANTHROPIC_API_KEY` | Claude key (optional) | - |

## Security Considerations

### Network Security

1. **Firewall Rules**:
   ```bash
   # Allow only localhost for most services
   sudo ufw deny 7070:7090/tcp
   sudo ufw allow from 127.0.0.1 to any port 7070:7090
   ```

2. **API Keys**: Set `api_key_required: true` in production

3. **CORS**: Configure `allowed_origins` for web access

### Service Isolation

- Each service runs in separate process
- Sandboxed code execution (sandboxd)
- Policy-based permissions (policyd)

### Data Protection

- All data stored in `~/.clawos/`
- Encrypted at rest (optional)
- Audit logging enabled

## Troubleshooting

### Services Won't Start

```bash
# Check port conflicts
clawctl doctor

# Check logs
tail -f ~/.clawos/logs/*.log

# Restart specific service
./scripts/dev_boot.sh --stop
./scripts/dev_boot.sh --core
```

### Ollama Connection Issues

```bash
# Verify Ollama is running
curl http://localhost:11434/api/tags

# Check model availability
ollama list

# Pull default model
ollama pull llama3.2
```

### Permission Errors

```bash
# Fix permissions
chmod +x scripts/*.sh
chmod +x install.sh

# Ensure data directory is writable
mkdir -p ~/.clawos
chmod 755 ~/.clawos
```

## Monitoring

### Health Checks

```bash
# All services
clawctl status

# Specific service
curl http://localhost:7071/health  # clawd
curl http://localhost:7070/health  # dashd
```

### Metrics

Enable metricd for Prometheus-compatible metrics:

```bash
# Access metrics
curl http://localhost:7076/metrics
```

### Logs

```bash
# View all logs
cdawos logs

# Service-specific
clawctl logs clawd -f

# Search logs
grep ERROR ~/.clawos/logs/*.log
```

## Backup and Restore

### Backup

```bash
# Backup all data
tar -czf clawos-backup-$(date +%Y%m%d).tar.gz ~/.clawos/

# Backup specific service
tar -czf braind-backup.tar.gz ~/.clawos/brain/
```

### Restore

```bash
# Restore from backup
tar -xzf clawos-backup-20260127.tar.gz -C ~/

# Restart services
./scripts/dev_boot.sh --restart
```

## Updating

```bash
# Pull latest changes
git pull origin main

# Update dependencies
./install.sh --update

# Restart services
./scripts/dev_boot.sh --restart
```

## Uninstallation

```bash
# Stop all services
./scripts/dev_boot.sh --stop

# Remove data (optional)
rm -rf ~/.clawos

# Remove code (if desired)
rm -rf /path/to/clawos
```

## Support

- Documentation: https://docs.clawos.ai
- Issues: https://github.com/openclaw/clawos/issues
- Discord: https://discord.gg/clawd

---

**Note**: This is beta software. Back up your data regularly.
