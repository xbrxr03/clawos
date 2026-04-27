# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unit tests for clawos_core.service_registry module."""

import pytest
import time
from unittest.mock import Mock

from clawos_core.service_registry import (
    ServiceRegistry,
    ServiceRegistryConfig,
    ServiceInstance,
    ServiceStatus,
)
from clawos_core.exceptions import ServiceUnavailableError


class TestServiceRegistryConfig:
    """Test ServiceRegistryConfig."""
    
    def test_default_values(self):
        config = ServiceRegistryConfig()
        assert config.heartbeat_ttl == 60.0
        assert config.cleanup_interval == 30.0
        assert config.enable_circuit_breaker is True


class TestServiceRegistryRegistration:
    """Test service registration."""
    
    @pytest.fixture
    def registry(self):
        return ServiceRegistry(ServiceRegistryConfig(heartbeat_ttl=0.1))
    
    def test_register_service(self, registry):
        instance = registry.register(
            name="test-service",
            host="127.0.0.1",
            port=8080,
        )
        
        assert instance.name == "test-service"
        assert instance.host == "127.0.0.1"
        assert instance.port == 8080
        assert instance.status == ServiceStatus.HEALTHY
    
    def test_register_with_capabilities(self, registry):
        instance = registry.register(
            name="test-service",
            host="127.0.0.1",
            port=8080,
            capabilities={"api", "webhook"},
        )
        
        assert "api" in instance.capabilities
        assert "webhook" in instance.capabilities
    
    def test_deregister_service(self, registry):
        registry.register(name="test", host="127.0.0.1", port=8080)
        assert registry.deregister("test") is True
        assert registry.deregister("test") is False


class TestServiceDiscovery:
    """Test service discovery."""
    
    @pytest.fixture
    def registry(self):
        return ServiceRegistry()
    
    def test_discover_existing_service(self, registry):
        registry.register(name="test", host="127.0.0.1", port=8080)
        
        instance = registry.discover("test")
        assert instance is not None
        assert instance.name == "test"
    
    def test_discover_missing_service(self, registry):
        instance = registry.discover("nonexistent")
        assert instance is None
    
    def test_discover_unhealthy_service(self, registry):
        registry.register(name="test", host="127.0.0.1", port=8080)
        registry.heartbeat("test", ServiceStatus.UNHEALTHY)
        
        instance = registry.discover("test")
        assert instance is None
    
    def test_discover_by_capability(self, registry):
        registry.register(
            name="service1",
            host="127.0.0.1",
            port=8080,
            capabilities={"api"},
        )
        registry.register(
            name="service2",
            host="127.0.0.1",
            port=8081,
            capabilities={"api", "webhook"},
        )
        registry.register(
            name="service3",
            host="127.0.0.1",
            port=8082,
            capabilities={"worker"},
        )
        
        results = registry.discover_by_capability("api")
        assert len(results) == 2
        assert all("api" in r.capabilities for r in results)


class TestHeartbeat:
    """Test heartbeat mechanism."""
    
    @pytest.fixture
    def registry(self):
        return ServiceRegistry()
    
    def test_heartbeat_updates_timestamp(self, registry):
        registry.register(name="test", host="127.0.0.1", port=8080)
        before = registry._services["test"].last_heartbeat
        
        time.sleep(0.01)
        registry.heartbeat("test")
        
        after = registry._services["test"].last_heartbeat
        assert after > before
    
    def test_heartbeat_updates_status(self, registry):
        registry.register(name="test", host="127.0.0.1", port=8080)
        
        registry.heartbeat("test", ServiceStatus.DEGRADED)
        assert registry._services["test"].status == ServiceStatus.DEGRADED


class TestServiceRegistryHealth:
    """Test registry health reporting."""
    
    @pytest.fixture
    def registry(self):
        return ServiceRegistry()
    
    def test_empty_registry_health(self, registry):
        health = registry.health()
        assert health["total_services"] == 0
        assert health["healthy"] == 0
        assert health["overall"] == "healthy"
    
    def test_mixed_health(self, registry):
        registry.register(name="healthy1", host="127.0.0.1", port=8080)
        registry.register(name="healthy2", host="127.0.0.1", port=8081)
        registry.register(name="degraded", host="127.0.0.1", port=8082)
        
        registry.heartbeat("degraded", ServiceStatus.DEGRADED)
        
        health = registry.health()
        assert health["total_services"] == 3
        assert health["healthy"] == 2
        assert health["degraded"] == 1


class TestServiceRegistryWatchers:
    """Test service registry watchers."""
    
    @pytest.fixture
    def registry(self):
        return ServiceRegistry()
    
    def test_watcher_called_on_status_change(self, registry):
        watcher = Mock()
        registry.watch(watcher)
        
        registry.register(name="test", host="127.0.0.1", port=8080)
        registry.heartbeat("test", ServiceStatus.DEGRADED)
        
        watcher.assert_called_once_with("test", ServiceStatus.DEGRADED)
