# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for Secure Sandbox service (sandboxd)."""

import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil

from services.sandboxd.v2.main import (
    SecureSandbox,
    SandboxConfig,
    NodeType as SandboxNodeType
)


@pytest.fixture
def temp_dir():
    """Create temporary directory."""
    temp = tempfile.mkdtemp()
    yield Path(temp)
    shutil.rmtree(temp)


@pytest.fixture
def sandbox_config():
    """Create default sandbox config."""
    return SandboxConfig(
        language="python",
        timeout_seconds=5,
        memory_limit_mb=128,
        network_enabled=False
    )


class TestSecureSandbox:
    """Test secure sandbox functionality."""
    
    def test_sandbox_creation(self, temp_dir, sandbox_config):
        """Test sandbox initialization."""
        sandbox = SecureSandbox(
            sandbox_id="test-1",
            config=sandbox_config
        )
        
        assert sandbox.sandbox_id == "test-1"
        assert sandbox.config.language == "python"
        assert sandbox.sandbox_path.exists()
    
    @pytest.mark.asyncio
    async def test_execute_python_code(self, temp_dir, sandbox_config):
        """Test Python code execution."""
        sandbox = SecureSandbox(
            sandbox_id="test-py",
            config=sandbox_config
        )
        
        result = await sandbox.execute("print('Hello from sandbox')")
        
        assert result["success"] is True
        assert "Hello from sandbox" in result["stdout"]
        assert result["exit_code"] == 0
    
    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, temp_dir, sandbox_config):
        """Test execution timeout."""
        config = SandboxConfig(
            language="python",
            timeout_seconds=1,
            memory_limit_mb=128
        )
        
        sandbox = SecureSandbox(
            sandbox_id="test-timeout",
            config=config
        )
        
        # Code that sleeps longer than timeout
        result = await sandbox.execute("import time; time.sleep(10)")
        
        assert result["success"] is False
        assert "timeout" in result["stderr"].lower() or result["exit_code"] != 0
    
    @pytest.mark.asyncio
    async def test_security_check_code_injection(self, temp_dir, sandbox_config):
        """Test security check blocks dangerous code."""
        sandbox = SecureSandbox(
            sandbox_id="test-security",
            config=sandbox_config
        )
        
        # Try to execute dangerous code
        result = await sandbox.execute("import os; os.system('rm -rf /')")
        
        # Should be blocked by security check
        assert result["success"] is False
        assert "security" in result["stderr"].lower()
    
    @pytest.mark.asyncio
    async def test_execute_bash(self, temp_dir):
        """Test bash execution."""
        config = SandboxConfig(language="bash", timeout_seconds=5)
        sandbox = SecureSandbox(
            sandbox_id="test-bash",
            config=config
        )
        
        result = await sandbox.execute("echo 'Hello from bash'")
        
        assert result["success"] is True
        assert "Hello from bash" in result["stdout"]
    
    def test_file_operations(self, temp_dir, sandbox_config):
        """Test file read/write in sandbox."""
        sandbox = SecureSandbox(
            sandbox_id="test-files",
            config=sandbox_config
        )
        
        # Write file
        sandbox.write_file("test.txt", "Hello World")
        
        # Read file
        content = sandbox.read_file("test.txt")
        assert content == "Hello World"
    
    def test_file_security(self, temp_dir, sandbox_config):
        """Test file path security."""
        sandbox = SecureSandbox(
            sandbox_id="test-file-security",
            config=sandbox_config
        )
        
        # Try path traversal
        with pytest.raises(ValueError):
            sandbox.write_file("../../../etc/passwd", "malicious")


class TestSandboxConfig:
    """Test sandbox configuration."""
    
    def test_default_values(self):
        """Test default config values."""
        config = SandboxConfig()
        
        assert config.language == "python"
        assert config.timeout_seconds == 30
        assert config.memory_limit_mb == 512
        assert config.network_enabled is False
    
    def test_custom_values(self):
        """Test custom config values."""
        config = SandboxConfig(
            language="node",
            timeout_seconds=60,
            memory_limit_mb=1024,
            network_enabled=True
        )
        
        assert config.language == "node"
        assert config.timeout_seconds == 60
        assert config.memory_limit_mb == 1024
        assert config.network_enabled is True
