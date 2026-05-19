# Contributing to ClawOS

Thanks for your interest in contributing! ClawOS is a local-first AI agent OS — every contribution makes local AI better for everyone.

## Quick Links

- [Good First Issues](https://github.com/xbrxr03/clawos/labels/good%20first%20issue) — beginner-friendly tasks
- [Discussions](https://github.com/xbrxr03/clawos/discussions) — questions, ideas, RFCs
- [Roadmap](docs/ROADMAP.md) — where the project is headed
- [CLI Reference](docs/CLI_REFERENCE.md) — all `clawctl` commands and flags

---

## Development Setup

### Prerequisites

- **Python 3.10+** (specified in `pyproject.toml`)
- **[Ollama](https://ollama.com)** with at least `qwen2.5:3b` pulled (for running the agent)
- **Git**

### Install

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/clawos.git
cd clawos

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"
```

### Optional Dependencies

Install extras based on what you're working on:

```bash
pip install -e ".[voice]"     # STT/TTS (Whisper, Piper)
pip install -e ".[memory]"    # ChromaDB, json-repair
pip install -e ".[browser]"   # Playwright
pip install -e ".[brain]"     # LangChain experimental
pip install -e ".[full]"      # Everything
```

### Verify Installation

```bash
clawctl health    # Check that all services are running
```

---

## Running Tests

```bash
# Run all unit tests (no live LLM required)
pytest tests/ -v --tb=short

# Run a specific test file
pytest tests/unit/test_agent_loop.py -v

# Run with coverage
pytest tests/ --cov=clawos_core --cov=services --cov=skills --cov-report=html

# Quick tests only (skip slow marks)
pytest tests/ -v -m "not slow"
```

Tests live in `tests/unit/`, `tests/integration/`, `tests/system/`, and `tests/services/`. Unit tests don't require a running Ollama instance.

---

## Code Style

We use **[Ruff](https://docs.astral.sh/ruff/)** for linting and formatting, configured in `pyproject.toml`:

- **Line length:** 100 characters
- **Target Python:** 3.10+
- **Formatter:** Ruff (replaces Black + isort)

Run checks before committing:

```bash
# Lint
ruff check .

# Format
ruff format .
```

Or use the Makefile:

```bash
make lint      # flake8 + pylint
make format    # black + isort (line-length=100)
make format-check
```

### Conventions

- Follow existing patterns in the codebase
- Keep functions small and focused
- Use type hints for public APIs
- Add docstrings to modules and public functions
- **Document *why*, not *what*** — code shows what, comments show why

---

## Pull Request Process

1. **Fork** the repository
2. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/my-feature
   # or
   git checkout -b fix/issue-42
   ```
3. **Make your changes** — keep commits focused and atomic
4. **Write/update tests** — especially for bug fixes and new features
5. **Run the test suite** — make sure everything passes:
   ```bash
   pytest tests/ -v --tb=short
   ```
6. **Commit with conventional messages:**
   ```
   feat: add voice command for setting timers
   fix: prevent list mutation in agent tool parsing
   docs: update API reference for memd endpoints
   refactor: extract approval popup into reusable component
   test: add unit tests for memory layer
   chore: update dependencies
   ```
7. **Push** to your fork and open a PR against `main`
8. **Respond to review feedback** — we'll work with you to get it merged

### PR Checklist

- [ ] Tests pass locally (`pytest tests/`)
- [ ] New code has tests
- [ ] Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
- [ ] No unrelated changes in the PR
- [ ] Documentation updated if needed

---

## Reporting Bugs

Use the [Bug Report](https://github.com/xbrxr03/clawos/issues/new?template=bug_report.md) template. Include:

- ClawOS version (`clawctl --version`)
- OS and hardware (especially RAM and GPU)
- Steps to reproduce
- Expected vs. actual behavior
- Logs if available (`clawctl logs <service>`)

---

## Suggesting Features

Use the [Feature Request](https://github.com/xbrxr03/clawos/issues/new?template=feature_request.md) template. Describe the use case, not just the solution.

---

## Project Structure

```
clawos/
├── clawos_core/          # Core library
├── runtimes/agent/       # Nexus agent loop (4-tier pipeline)
│   ├── runtime.py        #   Priority pipeline: memory → confirm → intent → LLM
│   ├── intents.py        #   Deterministic regex classifier
│   ├── router.py         #   3b/7b/coder dynamic model router
│   ├── tool_schemas.py   #   31 tool JSON schemas for Ollama function calling
│   └── tools/            #   Tool modules (Linux + macOS)
├── services/             # 29 daemons (FastAPI + SQLite)
├── workflows/            # 28 built-in workflows
├── desktop/command-center/ # Tauri shell + approval overlay
├── dashboard/frontend/   # React SPA
├── clawctl/              # CLI
├── tests/                # Unit + integration + system tests
├── docs/                 # Documentation
└── packaging/            # AppImage, .deb, AUR, ISO
```

---

## Getting Help

- **Questions?** [GitHub Discussions](https://github.com/xbrxr03/clawos/discussions)
- **Bugs?** [Open an issue](https://github.com/xbrxr03/clawos/issues)
- **Security?** See [SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md)

---

## License

By contributing, you agree that your contributions will be licensed under [AGPL-3.0](LICENSE).