# ClawOS - AI Operating System

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Status](https://img.shields.io/badge/status-beta-orange.svg)](https://github.com/openclaw/clawos)

**ClawOS** is an open-source AI operating system that brings local-first AI agents to your machine. Think of it as an operating system where AI agents are first-class citizens.

## ✨ Key Features

- **🤖 Local-First AI**: Run models locally with Ollama - no cloud required
- **🔧 MCP Protocol**: Model Context Protocol for universal tool integration
- **👥 Multi-Agent System**: Coordinate multiple specialized AI agents
- **🧠 Second Brain**: Knowledge management with graph storage
- **🔒 Secure Sandbox**: E2B-inspired code execution
- **📝 DevOps Notebooks**: Executable markdown documentation
- **🎨 Visual Workflows**: ComfyUI-style node editor
- **🗣️ Voice Pipeline**: TTS/STT for voice interaction
- **🌐 Browser Automation**: Playwright-based web automation
- **📊 Observability**: Built-in metrics and tracing

## 🚀 Quick Start

```bash
# Clone repository
git clone https://github.com/openclaw/clawos.git
cd clawos

# Install dependencies
./install.sh

# Start all services
./scripts/dev_boot.sh --full

# Check status
clawctl status

# Try the CLI
clawctl chat  # Start Nexus interactive chat
```

## 📋 Requirements

- **OS**: Linux, macOS, or Windows (WSL2)
- **Python**: 3.10 or higher
- **Memory**: 8GB RAM minimum (16GB recommended)
- **Storage**: 10GB free space
- **Ollama**: For local LLM inference

## 🏗️ Architecture

ClawOS uses a microservices architecture with 16+ services:

```
┌─────────────────────────────────────────────────────┐
│                   User Interfaces                     │
│  clawctl (CLI) │ Web UI │ VS Code │ API              │
└──────────────────┬──────────────────────────────────┘
                   │
    ┌──────────────┼──────────────┬──────────────┐
    │              │              │              │
┌───▼───┐   ┌─────▼────┐   ┌────▼───┐    ┌─────▼────┐
│ Core  │   │   AI     │   │ Agents │    │  Tools   │
│7070-74│   │7075-7079 │   │7080-83 │    │7084-7086 │
└───┬───┘   └────┬─────┘   └───┬────┘    └────┬─────┘
    │            │             │              │
    └────────────┴─────────────┴──────────────┘
                   │
            ┌──────▼──────┐
            │   Skills    │
            │  & Models   │
            └─────────────┘
```

**Core Services**: Dashboard, API, Memory, Policy  
**AI Services**: Models, MCP Protocol, Voice, Metrics  
**Agents**: Single agents, Multi-agent, A2A Protocol  
**Tools**: Desktop, Second Brain, Sandbox, Visual Workflows

## 🎯 Use Cases

### Personal AI Assistant
```bash
clawctl chat                    # Interactive chat
clawctl voice enable            # Voice activation
clawctl brain search "meeting notes"  # Knowledge search
```

### Software Development
```bash
clawctl code review file.py     # Code review
clawctl sandbox create --lang python  # Test code
clawctl notebook run setup.md   # Executable docs
```

### Automation
```bash
clawctl wf run daily_backup    # Run workflow
clawctl agentd run researcher  # Deploy agent
```

## 📚 Documentation

- [Installation Guide](docs/DEPLOYMENT_GUIDE.md)
- [Architecture Overview](docs/ARCHITECTURE.md)
- [Feature Reference](docs/FEATURES.md)
- [API Reference](docs/API_REFERENCE.md)
- [Testing Guide](docs/TESTING_GUIDE.md)

## 🔌 Service Ports

| Service | Port | Description |
|---------|------|-------------|
| dashd | 7070 | Dashboard |
| clawd | 7071 | Core API |
| agentd | 7072 | Agents |
| memd | 7073 | Memory |
| policyd | 7074 | Policy Engine |
| modeld | 7075 | Model Management |
| metricd | 7076 | Metrics |
| mcpd | 7077 | MCP Protocol |
| observd | 7078 | Observability |
| voiced | 7079 | Voice Pipeline |
| desktopd | 7080 | Desktop Automation |
| agentd_v2 | 7081 | Multi-Agent Framework |
| braind | 7082 | Second Brain |
| a2ad | 7083 | A2A Protocol |
| sandboxd | 7085 | Secure Sandbox |
| visuald | 7086 | Visual Workflows |

## 🛠️ Development

```bash
# Clone repo
git clone https://github.com/openclaw/clawos.git
cd clawos

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest tests/

# Start dev services
./scripts/dev_boot.sh --core
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_modeld.py

# Run with coverage
pytest --cov=clawos_core --cov=services

# Run diagnostics
clawctl doctor
```

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📜 License

ClawOS is licensed under the [AGPL-3.0](LICENSE) license.

## 🙏 Acknowledgments

- **Ollama** - Local LLM inference
- **Playwright** - Browser automation
- **FastAPI** - API framework
- **ComfyUI** - Inspiration for visual workflows
- **E2B** - Inspiration for secure sandboxing

## 🔗 Links

- **Website**: https://clawos.ai
- **Documentation**: https://docs.clawos.ai
- **Discord**: https://discord.gg/clawd
- **GitHub**: https://github.com/openclaw/clawos

## ⚡ Status

ClawOS is currently in **beta**. APIs may change. Use in production with caution.

## 📊 Stats

- **Services**: 16 microservices
- **Lines of Code**: 50,000+
- **Test Coverage**: 85%+
- **Contributors**: Growing

---

<p align="center">
  <strong>Built with ❤️ by the OpenClaw community</strong>
</p>
