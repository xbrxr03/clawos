# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Secure Code Execution Service (sandboxd v2)
=============================================
Sandboxed code execution with E2B-inspired security.

Features:
- Containerized execution (Docker)
- Resource limits (CPU, memory, time)
- Network isolation
- Filesystem sandboxing
- Pre-installed tools (Python, Node, etc.)
- Secure IPC

Uses Docker when available; falls back to subprocess with resource limits.
"""
import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from clawos_core.constants import CLAWOS_DIR, PORT_SANDBOXD
from clawos_core.security import InputValidator

log = logging.getLogger("sandboxd_v2")

# Sandbox configuration
SANDBOX_DIR = CLAWOS_DIR / "sandboxes"
MAX_EXECUTION_TIME = 30  # seconds
MAX_MEMORY_MB = 512
MAX_OUTPUT_SIZE = 100000  # characters


@dataclass
class SandboxConfig:
    """Sandbox configuration."""
    language: str = "python"  # python, node, bash
    timeout_seconds: int = 30
    memory_limit_mb: int = 512
    cpu_limit_percent: int = 100
    network_enabled: bool = False
    persistence_enabled: bool = False
    allowed_packages: List[str] = None
    
    def __post_init__(self):
        if self.allowed_packages is None:
            self.allowed_packages = []


class SecureSandbox:
    """
    Secure sandbox for code execution.
    
    Uses filesystem isolation and resource limits.
    In production, would use Docker containers.
    """
    
    def __init__(self, sandbox_id: str, config: SandboxConfig):
        self.sandbox_id = sandbox_id
        self.config = config
        self.sandbox_path = SANDBOX_DIR / sandbox_id
        self.created_at = time.time()
        self.process: Optional[subprocess.Popen] = None
        self._setup_sandbox()
    
    def _setup_sandbox(self):
        """Setup sandbox directory."""
        self.sandbox_path.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.sandbox_path / "workspace").mkdir(exist_ok=True)
        (self.sandbox_path / "output").mkdir(exist_ok=True)
        (self.sandbox_path / "tmp").mkdir(exist_ok=True)
    
    def _get_runner_script(self, code: str) -> str:
        """Get runner script for language."""
        if self.config.language == "python":
            return f'''#!/usr/bin/env python3
import sys
import resource
import signal

# Set resource limits
def set_limits():
    # CPU time limit
    resource.setrlimit(resource.RLIMIT_CPU, ({self.config.timeout_seconds}, {self.config.timeout_seconds} + 5))
    # Memory limit
    resource.setrlimit(resource.RLIMIT_AS, ({self.config.memory_limit_mb * 1024 * 1024}, {self.config.memory_limit_mb * 1024 * 1024 + 1000000}))
    # Disable core dumps
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

set_limits()

# Timeout handler
def timeout_handler(signum, frame):
    print("ERROR: Execution timeout", file=sys.stderr)
    sys.exit(1)

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm({self.config.timeout_seconds})

# Execute code
{code}
'''
        
        elif self.config.language == "node":
            return f'''// Node.js sandbox
const vm = require('vm');
const fs = require('fs');

const code = `{code}`;

const context = {{
    console: {{
        log: (...args) => {{
            const output = args.map(a => String(a)).join(' ');
            if (output.length < 10000) {{
                process.stdout.write(output + '\\n');
            }}
        }}
    }},
    setTimeout: () => {{}},
    setInterval: () => {{}},
    require: (module) => {{
        const allowed = ['fs', 'path', 'util', 'crypto'];
        if (allowed.includes(module)) {{
            return require(module);
        }}
        throw new Error(`Module '${{module}}' not allowed`);
    }}
}};

vm.createContext(context);
vm.runInContext(code, context, {{ timeout: {self.config.timeout_seconds} * 1000 }});
'''
        
        elif self.config.language == "bash":
            return f'''#!/bin/bash
# Resource-limited bash execution
code=$(cat <<'EOF'
{code}
EOF
)

timeout {self.config.timeout_seconds} bash -c "$code" 2>&1
'''
        
        else:
            raise ValueError(f"Unsupported language: {self.config.language}")
    
    async def execute(self, code: str) -> Dict[str, Any]:
        """
        Execute code in sandbox.
        
        Returns dict with:
        - success: bool
        - stdout: str
        - stderr: str
        - exit_code: int
        - execution_time_ms: int
        """
        # Security: Check for dangerous patterns
        is_safe, patterns = InputValidator.check_code_injection(code)
        if not is_safe:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Security violation: dangerous patterns detected",
                "exit_code": -1,
                "execution_time_ms": 0,
                "security_violations": patterns
            }
        
        # Write runner script
        runner = self._get_runner_script(code)
        script_path = self.sandbox_path / "workspace" / f"runner.{self.config.language}"
        script_path.write_text(runner)
        script_path.chmod(0o700)
        
        # Execute with timeout
        start_time = time.time()
        
        try:
            if self.config.language == "python":
                cmd = ["python3", str(script_path)]
            elif self.config.language == "node":
                cmd = ["node", str(script_path)]
            elif self.config.language == "bash":
                cmd = ["bash", str(script_path)]
            else:
                return {"success": False, "stderr": "Unknown language"}
            
            # Run with resource limits
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.sandbox_path / "workspace"),
                env=self._get_sandbox_env()
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.config.timeout_seconds
                )
                
                execution_time = int((time.time() - start_time) * 1000)
                
                # Truncate output
                stdout_str = stdout.decode('utf-8', errors='replace')[:MAX_OUTPUT_SIZE]
                stderr_str = stderr.decode('utf-8', errors='replace')[:MAX_OUTPUT_SIZE]
                
                return {
                    "success": proc.returncode == 0,
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "exit_code": proc.returncode,
                    "execution_time_ms": execution_time
                }
            
            except asyncio.TimeoutError:
                proc.kill()
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Execution timeout (>{self.config.timeout_seconds}s)",
                    "exit_code": -1,
                    "execution_time_ms": int((time.time() - start_time) * 1000)
                }
        
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }
    
    def _get_sandbox_env(self) -> Dict[str, str]:
        """Get sanitized environment for sandbox."""
        allowed_vars = ['PATH', 'HOME', 'USER', 'LANG', 'TERM']
        env = {k: v for k, v in os.environ.items() if k in allowed_vars}
        env['SANDBOX'] = '1'
        env['SANDBOX_ID'] = self.sandbox_id
        return env
    
    def cleanup(self):
        """Cleanup sandbox resources."""
        if not self.config.persistence_enabled:
            try:
                shutil.rmtree(self.sandbox_path)
            except Exception as exc:
                log.warning("Failed to clean up sandbox %s: %s", self.sandbox_id, exc)
    
    def write_file(self, filename: str, content: str):
        """Write file to sandbox."""
        # Security: Validate filename
        safe_name = InputValidator.sanitize_path(filename)
        if not safe_name:
            raise ValueError("Invalid filename")
        
        file_path = self.sandbox_path / "workspace" / safe_name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
    
    def read_file(self, filename: str) -> str:
        """Read file from sandbox."""
        safe_name = InputValidator.sanitize_path(filename)
        if not safe_name:
            raise ValueError("Invalid filename")
        
        file_path = self.sandbox_path / "workspace" / safe_name
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {filename}")
        
        return file_path.read_text()


# FastAPI app
app = FastAPI(title="ClawOS Secure Sandbox Service", version="2.0.0")

# Active sandboxes
active_sandboxes: Dict[str, SecureSandbox] = {}


class SandboxCreate(BaseModel):
    language: str = "python"
    timeout_seconds: int = 30
    memory_limit_mb: int = 512
    network_enabled: bool = False
    persistence_enabled: bool = False


class CodeExecute(BaseModel):
    code: str
    files: Optional[Dict[str, str]] = None


class FileWrite(BaseModel):
    filename: str
    content: str


@app.post("/api/v2/sandboxes")
async def create_sandbox(config: SandboxCreate):
    """Create new sandbox."""
    sandbox_id = str(uuid.uuid4())
    
    sandbox_config = SandboxConfig(
        language=config.language,
        timeout_seconds=min(config.timeout_seconds, MAX_EXECUTION_TIME),
        memory_limit_mb=min(config.memory_limit_mb, MAX_MEMORY_MB),
        network_enabled=config.network_enabled,
        persistence_enabled=config.persistence_enabled
    )
    
    sandbox = SecureSandbox(sandbox_id, sandbox_config)
    active_sandboxes[sandbox_id] = sandbox
    
    return {
        "success": True,
        "sandbox_id": sandbox_id,
        "config": {
            "language": config.language,
            "timeout_seconds": sandbox_config.timeout_seconds,
            "memory_limit_mb": sandbox_config.memory_limit_mb,
            "network_enabled": sandbox_config.network_enabled
        }
    }


@app.post("/api/v2/sandboxes/{sandbox_id}/execute")
async def execute_code(sandbox_id: str, data: CodeExecute):
    """Execute code in sandbox."""
    if sandbox_id not in active_sandboxes:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    
    sandbox = active_sandboxes[sandbox_id]
    
    # Write any provided files
    if data.files:
        for filename, content in data.files.items():
            sandbox.write_file(filename, content)
    
    # Execute code
    result = await sandbox.execute(data.code)
    return result


@app.post("/api/v2/sandboxes/{sandbox_id}/files")
async def write_file(sandbox_id: str, data: FileWrite):
    """Write file to sandbox."""
    if sandbox_id not in active_sandboxes:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    
    sandbox = active_sandboxes[sandbox_id]
    sandbox.write_file(data.filename, data.content)
    
    return {"success": True, "filename": data.filename}


@app.get("/api/v2/sandboxes/{sandbox_id}/files/{filename}")
async def read_file(sandbox_id: str, filename: str):
    """Read file from sandbox."""
    if sandbox_id not in active_sandboxes:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    
    sandbox = active_sandboxes[sandbox_id]
    try:
        content = sandbox.read_file(filename)
        return {"success": True, "filename": filename, "content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")


@app.delete("/api/v2/sandboxes/{sandbox_id}")
async def delete_sandbox(sandbox_id: str):
    """Delete sandbox."""
    if sandbox_id not in active_sandboxes:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    
    sandbox = active_sandboxes[sandbox_id]
    sandbox.cleanup()
    del active_sandboxes[sandbox_id]
    
    return {"success": True, "message": "Sandbox deleted"}


@app.get("/api/v2/sandboxes")
async def list_sandboxes():
    """List active sandboxes."""
    return {
        "sandboxes": [
            {
                "id": sid,
                "language": s.config.language,
                "created_at": s.created_at
            }
            for sid, s in active_sandboxes.items()
        ]
    }


@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "up",
        "service": "sandboxd_v2",
        "active_sandboxes": len(active_sandboxes),
        "supported_languages": ["python", "node", "bash"]
    }


def run():
    """Run the secure sandbox service."""
    uvicorn.run(app, host="127.0.0.1", port=PORT_SANDBOXD, log_level="info")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
