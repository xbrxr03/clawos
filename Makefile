# ClawOS Makefile
# Usage: make <target>

PYTHON     := python3
PYTHONPATH := $(shell pwd)
export PYTHONPATH

.PHONY: help run chat test test-e2e wizard doctor bootstrap install-deps clean

help:
	@echo ""
	@echo "  ClawOS dev commands:"
	@echo ""
	@echo "  make run          start all services (dev mode)"
	@echo "  make chat         start interactive chat"
	@echo "  make wizard       run first-run wizard"
	@echo "  make test         run unit tests"
	@echo "  make test-e2e     run all tests (needs Ollama)"
	@echo "  make doctor       diagnose issues"
	@echo "  make bootstrap    initialise machine (run once)"
	@echo "  make install-deps install Python dependencies"
	@echo "  make clean        remove __pycache__ files"
	@echo ""

run:
	bash scripts/dev_boot.sh

chat:
	$(PYTHON) -m clients.cli.repl

wizard:
	$(PYTHON) -m setup.first_run.wizard

test:
	$(PYTHON) tests/system/test_phase1.py
	$(PYTHON) tests/system/test_phase2.py

test-e2e:
	$(PYTHON) tests/system/test_phase1.py --e2e
	$(PYTHON) tests/system/test_phase2.py --e2e

doctor:
	$(PYTHON) -m clawctl.main doctor

bootstrap:
	$(PYTHON) -m bootstrap.bootstrap

install-deps:
	pip install pyyaml aiohttp fastapi uvicorn ollama click \
	            openai-whisper piper-tts \
	            --break-system-packages

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

seed:
	bash scripts/seed_workspace.sh

status:
	$(PYTHON) -m clawctl.main status
