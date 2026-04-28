.PHONY: help install dev test lint format clean docs docker start stop restart status doctor

# Default target
help:
	@echo "ClawOS Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  install       - Install dependencies"
	@echo "  dev           - Setup development environment"
	@echo "  test          - Run all tests"
	@echo "  test-quick    - Run quick tests only"
	@echo "  lint          - Run linters"
	@echo "  format        - Format code"
	@echo "  clean         - Clean build artifacts"
	@echo "  docs          - Build documentation"
	@echo "  start         - Start all services"
	@echo "  stop          - Stop all services"
	@echo "  restart       - Restart all services"
	@echo "  status        - Show service status"
	@echo "  doctor        - Run diagnostics"
	@echo "  docker-build  - Build Docker images"
	@echo "  docker-run    - Run with Docker Compose"
	@echo "  release       - Create release"

# Installation
install:
	@echo "Installing ClawOS dependencies..."
	pip install -e "."
	@echo "Installation complete!"

dev: install
	@echo "Setting up development environment..."
	pip install -e ".[dev]"
	pre-commit install
	@echo "Development environment ready!"

# Testing
test:
	@echo "Running all tests..."
	pytest tests/ -v --tb=short

test-quick:
	@echo "Running quick tests..."
	pytest tests/ -v --tb=short -m "not slow"

test-coverage:
	@echo "Running tests with coverage..."
	pytest tests/ --cov=clawos_core --cov=services --cov=skills --cov-report=html
	@echo "Coverage report generated in htmlcov/"

test-specific:
	@echo "Usage: make test-specific TEST=test_file.py"
	pytest tests/$(TEST) -v

# Code quality
lint:
	@echo "Running linters..."
	flake8 clawos_core services skills clawctl --max-line-length=120
	pylint clawos_core services skills clawctl --disable=all --enable=E,F
	@echo "Linting complete!"

format:
	@echo "Formatting code..."
	black clawos_core services skills clawctl --line-length=100
	isort clawos_core services skills clawctl
	@echo "Formatting complete!"

format-check:
	@echo "Checking code formatting..."
	black --check clawos_core services skills clawctl --line-length=100
	isort --check-only clawos_core services skills clawctl

# Cleaning
clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/ dist/ *.egg-info
	rm -rf .pytest_cache .coverage htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	@echo "Clean complete!"

clean-all: clean
	@echo "Cleaning everything including data..."
	rm -rf ~/.clawos/run/*
	rm -rf ~/.clawos/logs/*
	@echo "All cleaned!"

# Documentation
docs:
	@echo "Building documentation..."
	@echo "Docs are in markdown format in docs/"
	@echo "API docs can be generated with:"
	@echo "  pdoc --html -o docs/api clawos_core"

docs-serve:
	@echo "Serving documentation..."
	python -m http.server 8080 --directory docs/

# Service management
start:
	@echo "Starting ClawOS services..."
	./scripts/dev_boot.sh --full

start-core:
	@echo "Starting core services..."
	./scripts/dev_boot.sh --core

start-ai:
	@echo "Starting AI services..."
	./scripts/dev_boot.sh --ai

stop:
	@echo "Stopping ClawOS services..."
	./scripts/dev_boot.sh --stop

restart:
	@echo "Restarting ClawOS services..."
	./scripts/dev_boot.sh --restart

status:
	@echo "Checking service status..."
	./scripts/dev_boot.sh --status

logs:
	@echo "Showing logs..."
	@echo "Usage: make logs SERVICE=clawd"
	@./scripts/dev_boot.sh --logs $(SERVICE)

# Diagnostics
doctor:
	@echo "Running diagnostics..."
	./scripts/dev_boot.sh --doctor

# Security
security-audit:
	@echo "Running security audit..."
	bandit -r clawos_core services skills

dependency-check:
	@echo "Checking dependencies..."
	safety check

# Docker
docker-build:
	@echo "Building Docker images..."
	docker-compose build

docker-run:
	@echo "Running with Docker Compose..."
	docker-compose up -d

docker-stop:
	@echo "Stopping Docker containers..."
	docker-compose down

docker-logs:
	@echo "Showing Docker logs..."
	docker-compose logs -f

# Release
release:
	@echo "Creating release..."
	@echo "1. Update version in setup.py"
	@echo "2. Update CHANGELOG.md"
	@echo "3. Run tests: make test"
	@echo "4. Create git tag: git tag vX.Y.Z"
	@echo "5. Push tag: git push origin vX.Y.Z"
	@echo "6. Build package: python -m build"
	@echo "7. Upload to PyPI: twine upload dist/*"

# Utilities
install-hooks:
	@echo "Installing git hooks..."
	pre-commit install

update:
	@echo "Updating dependencies..."
	pip install -e "." --upgrade
	pip install -e ".[dev]" --upgrade

check-ports:
	@echo "Checking ClawOS ports..."
	@for port in 7070 7071 7072 7073 7074 7075 7076 7077 7078 7079 7080 7081 7082 7083 7085 7086; do \
		if lsof -Pi :$$port -sTCP:LISTEN -t >/dev/null 2>&1; then \
			echo "Port $$port: IN USE"; \
		else \
			echo "Port $$port: available"; \
		fi \
	done

# Database operations
migrate:
	@echo "Running database migrations..."
	@echo "No migrations needed for current version"

backup:
	@echo "Creating backup..."
	tar -czf clawos-backup-$(shell date +%Y%m%d).tar.gz ~/.clawos/
	@echo "Backup created: clawos-backup-$(shell date +%Y%m%d).tar.gz"

restore:
	@echo "Usage: make restore BACKUP=backup-file.tar.gz"
	@echo "Restoring from backup..."
	tar -xzf $(BACKUP) -C ~/
	@echo "Restore complete!"

# Performance
profile:
	@echo "Running performance profiling..."
	python -m cProfile -o profile.stats -m clawctl status
	python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative'); p.print_stats(20)"

# CI/CD
ci-test:
	@echo "Running CI tests..."
	pytest tests/ -v --tb=short --cov=clawos_core --cov=services --cov=skills --cov-report=xml

ci-lint:
	@echo "Running CI linting..."
	flake8 clawos_core services skills clawctl --max-line-length=120
	black --check clawos_core services skills clawctl --line-length=100

# Development shortcuts
dev-install: install
	@echo "Installing development tools..."
	pip install pytest pytest-asyncio pytest-cov black flake8 isort mypy bandit safety pre-commit

dev-test: test-quick

dev-lint: format lint

# Quick commands
q: test-quick
s: status
st: stop
ss: start
sr: restart
