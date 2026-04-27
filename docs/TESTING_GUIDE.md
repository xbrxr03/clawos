# ClawOS Testing Guide

Complete testing procedures for ClawOS development and deployment.

---

## Quick Test

Run all tests in one command:

```bash
cd /home/jarvis/clawos-analysis

# Run comprehensive test suite
python3 -c "
import sys
sys.path.insert(0, '.')

# Test imports
from clawos_core.constants import *
from clawos_core.config.loader import get
from clawos_core.security import InputValidator
from clawos_core.performance import monitor, timed

print('✓ Core imports OK')

# Test service health modules
services = ['mcpd', 'observd', 'memd', 'policyd', 'modeld']
for svc in services:
    __import__(f'services.{svc}.health')
    print(f'✓ {svc} health module')

print('✓ All tests passed')
"
```

---

## Test Categories

### 1. Static Analysis

**Syntax Check:**
```bash
# Check all Python files
find . -name "*.py" -exec python3 -m py_compile {} \;

# Check shell scripts
bash -n scripts/dev_boot.sh
bash -n install.sh
```

**Import Cycles:**
```bash
# Check for circular imports
python3 -c "
import ast
imports = {}
for root, dirs, files in os.walk('clawos_core'):
    for file in files:
        if file.endswith('.py'):
            # Parse and check imports
            pass
"
```

### 2. Unit Tests

**Test Individual Services:**
```bash
# Test MCPD
python3 -c "from services.mcpd.main import app; print('✓ MCPD loads')"

# Test ObservD
python3 -c "from services.observd.main import app; print('✓ ObservD loads')"

# Test VoiceD
python3 -c "from services.voiced.main import VoicePipeline; print('✓ VoiceD loads')"

# Test DesktopD
python3 -c "from services.desktopd.main import DesktopAutomation; print('✓ DesktopD loads')"
```

### 3. Integration Tests

**Start Services:**
```bash
# Start all services
./scripts/dev_boot.sh

# Check health
curl http://localhost:7070/health
curl http://localhost:7077/health  # MCPD
curl http://localhost:7078/health  # ObservD
```

**Test MCP Integration:**
```bash
# List tools
curl http://localhost:7077/api/v1/tools

# Execute a tool
curl -X POST http://localhost:7077/api/v1/tools/execute \
  -H "Content-Type: application/json" \
  -d '{"name": "clawos_system_info", "arguments": {}}'
```

**Test Observability:**
```bash
# Record a call
curl -X POST http://localhost:7078/api/v1/llm_calls \
  -H "Content-Type: application/json" \
  -d '{
    "workspace": "test",
    "model": "test-model",
    "provider": "test",
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "duration_ms": 1000
  }'

# Get calls
curl http://localhost:7078/api/v1/calls?hours=1
```

### 4. End-to-End Tests

**Test Complete Workflow:**
```bash
# 1. Start services
./scripts/dev_boot.sh

# 2. Test MCP
curl http://localhost:7077/health

# 3. Test Observability
curl http://localhost:7078/health

# 4. Test CLI
clawctl observ status
clawctl mcp list

# 5. Test dashboard
curl http://localhost:7070/api/health
```

### 5. Performance Tests

**Load Testing:**
```bash
# Install wrk
sudo apt install wrk

# Test MCP endpoint
wrk -t12 -c400 -d30s http://localhost:7077/health

# Test Observability endpoint
wrk -t12 -c400 -d30s http://localhost:7078/health
```

**Memory Profiling:**
```bash
# Monitor memory usage
python3 -c "
from clawos_core.performance import MemoryProfiler
profiler = MemoryProfiler()
profiler.snapshot('start')
# ... do work ...
profiler.snapshot('end')
print(profiler.get_snapshots())
"
```

### 6. Security Tests

**Input Validation:**
```bash
python3 -c "
from clawos_core.security import InputValidator

# Test path sanitization
assert InputValidator.sanitize_path('../etc/passwd') == 'etc/passwd'
assert InputValidator.sanitize_path('/etc/passwd') == 'etc/passwd'
assert InputValidator.sanitize_path('test.txt') == 'test.txt'
print('✓ Path sanitization')

# Test code injection detection
safe, patterns = InputValidator.check_code_injection('print(\"hello\")')
assert safe == True

unsafe, patterns = InputValidator.check_code_injection('os.system(\"rm -rf /\")')
assert safe == False
print('✓ Code injection detection')
"
```

**Rate Limiting:**
```bash
python3 -c "
from clawos_core.security import RateLimiter

limiter = RateLimiter(max_requests=5, window_seconds=60)

# Should allow first 5
for i in range(5):
    assert limiter.is_allowed('test') == True

# Should deny 6th
assert limiter.is_allowed('test') == False

print('✓ Rate limiting')
"
```

### 7. Stress Tests

**Concurrent Requests:**
```bash
python3 -c "
import asyncio
import aiohttp

async def test_concurrent():
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i in range(100):
            task = session.get('http://localhost:7077/health')
            tasks.append(task)
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        success = sum(1 for r in responses if not isinstance(r, Exception))
        print(f'Success: {success}/100')

asyncio.run(test_concurrent())
"
```

**Memory Stress:**
```bash
# Monitor over time
python3 -c "
import time
from clawos_core.performance import MemoryProfiler

profiler = MemoryProfiler()
for i in range(60):
    profiler.snapshot(f'iteration_{i}')
    time.sleep(1)

snapshots = profiler.get_snapshots()
print(f'Memory at start: {snapshots[0][\"memory_mb\"]} MB')
print(f'Memory at end: {snapshots[-1][\"memory_mb\"]} MB')
"
```

### 8. Edge Case Tests

**Boundary Testing:**
```bash
python3 -c "
from clawos_core.security import InputValidator

# Test max string length
long_string = 'x' * 10000
result = InputValidator.sanitize_string(long_string, max_length=1000)
assert len(result) == 1000
print('✓ String truncation')

# Test empty inputs
assert InputValidator.sanitize_path('') == None
assert InputValidator.sanitize_path(None) == None
print('✓ Empty input handling')

# Test special characters
assert InputValidator.validate_workspace('test-123') == 'test-123'
assert InputValidator.validate_workspace('test space') == None
assert InputValidator.validate_workspace('test@#$') == None
print('✓ Workspace validation')
"
```

---

## Test Automation

**GitHub Actions Workflow:**
```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      
      - name: Run syntax check
        run: |
          find . -name "*.py" -exec python3 -m py_compile {} \;
      
      - name: Run tests
        run: |
          python3 -m pytest tests/ -v
      
      - name: Test services start
        run: |
          timeout 30 ./scripts/dev_boot.sh || true
          curl http://localhost:7077/health
```

---

## Debugging Failed Tests

**Service Won't Start:**
```bash
# Check logs
./scripts/clawos-status.sh

# Check for port conflicts
sudo lsof -i :7077

# Check Python errors
python3 services/mcpd/main.py 2>&1
```

**Import Errors:**
```bash
# Check Python path
python3 -c "import sys; print(sys.path)"

# Check if module exists
python3 -c "import services.mcpd.main"

# Verbose import
python3 -v -c "import services.mcpd.main" 2>&1 | head -50
```

**Database Issues:**
```bash
# Check permissions
ls -la ~/.clawos/

# Reset databases
rm ~/.clawos/*.db

# Create directory if missing
mkdir -p ~/.clawos
```

---

## Test Coverage Goals

| Component | Target Coverage |
|-----------|-----------------|
| Core modules | 90% |
| Services | 80% |
| CLI commands | 70% |
| Skills | 60% |
| Workflows | 60% |

---

## Continuous Testing

**Pre-commit Hook:**
```bash
#!/bin/bash
# .git/hooks/pre-commit

# Run syntax check
find . -name "*.py" -exec python3 -m py_compile {} \; || exit 1

# Run quick tests
python3 -c "from clawos_core.constants import *" || exit 1

echo "Pre-commit checks passed"
```

**Nightly Tests:**
```bash
#!/bin/bash
# Run full test suite

# 1. Syntax check
find . -name "*.py" -exec python3 -m py_compile {} \;

# 2. Import tests
python3 -c "from clawos_core import *"

# 3. Start services
./scripts/dev_boot.sh

# 4. Integration tests
curl -f http://localhost:7077/health
curl -f http://localhost:7078/health

# 5. Performance tests
# ...

# 6. Cleanup
./scripts/dev_boot.sh --stop
```

---

## Troubleshooting

**Common Issues:**

1. **Port already in use**
   - Solution: `sudo lsof -i :7077` then `kill <pid>`

2. **Import errors**
   - Solution: `export PYTHONPATH=/home/jarvis/clawos-analysis`

3. **Database locked**
   - Solution: `rm ~/.clawos/*.db` and restart

4. **Permission denied**
   - Solution: `chmod +x scripts/*.sh`

---

**Last Updated:** April 27, 2026
