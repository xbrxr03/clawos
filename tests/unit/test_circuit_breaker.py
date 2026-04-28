# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unit tests for clawos_core.circuit_breaker module."""

import pytest
import threading
import time
from unittest.mock import Mock

from clawos_core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitBreakerRegistry,
)
from clawos_core.exceptions import CircuitBreakerError


class TestCircuitBreakerConfig:
    """Test CircuitBreakerConfig dataclass."""
    
    def test_default_values(self):
        config = CircuitBreakerConfig(name="test")
        assert config.failure_threshold == 5
        assert config.success_threshold == 3
        assert config.timeout_seconds == 60.0
    
    def test_custom_values(self):
        config = CircuitBreakerConfig(
            name="test",
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=30.0
        )
        assert config.failure_threshold == 3
        assert config.success_threshold == 2
        assert config.timeout_seconds == 30.0
    
    def test_invalid_threshold_raises(self):
        with pytest.raises(ValueError):
            CircuitBreakerConfig(name="test", failure_threshold=0)
        with pytest.raises(ValueError):
            CircuitBreakerConfig(name="test", success_threshold=0)
    
    def test_invalid_timeout_raises(self):
        with pytest.raises(ValueError):
            CircuitBreakerConfig(name="test", timeout_seconds=0)


class TestCircuitBreakerStateTransitions:
    """Test circuit breaker state machine."""
    
    def test_starts_closed(self):
        cb = CircuitBreaker(CircuitBreakerConfig(name="test"))
        assert cb.state == CircuitState.CLOSED
    
    def test_opens_after_failures(self):
        config = CircuitBreakerConfig(name="test", failure_threshold=3)
        cb = CircuitBreaker(config)
        
        # Record 3 failures
        cb.record_failure(Exception("fail 1"))
        assert cb.state == CircuitState.CLOSED  # Still closed
        cb.record_failure(Exception("fail 2"))
        assert cb.state == CircuitState.CLOSED  # Still closed
        cb.record_failure(Exception("fail 3"))
        assert cb.state == CircuitState.OPEN   # Now open
    
    def test_half_open_after_timeout(self):
        config = CircuitBreakerConfig(name="test", timeout_seconds=0.1)
        cb = CircuitBreaker(config)
        
        # Open the circuit
        for _ in range(config.failure_threshold):
            cb.record_failure(Exception("fail"))
        assert cb.state == CircuitState.OPEN
        
        # Wait for timeout
        time.sleep(0.2)
        assert cb.can_execute()  # Should transition to half-open
        assert cb.state == CircuitState.HALF_OPEN
    
    def test_closes_after_successes(self):
        config = CircuitBreakerConfig(name="test", success_threshold=2)
        cb = CircuitBreaker(config)
        
        # Open first
        for _ in range(config.failure_threshold):
            cb.record_failure(Exception("fail"))
        
        # Force to half-open
        cb._transition_to(CircuitState.HALF_OPEN)
        
        # Record successes
        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerCanExecute:
    """Test can_execute logic."""
    
    def test_closed_allows_execution(self):
        cb = CircuitBreaker(CircuitBreakerConfig(name="test"))
        assert cb.can_execute() is True
    
    def test_open_blocks_execution(self):
        config = CircuitBreakerConfig(name="test")
        cb = CircuitBreaker(config)
        for _ in range(config.failure_threshold):
            cb.record_failure(Exception("fail"))
        assert cb.can_execute() is False
    
    def test_half_open_allows_limited_execution(self):
        config = CircuitBreakerConfig(name="test", half_open_max_calls=2)
        cb = CircuitBreaker(config)
        
        # Open then transition to half-open
        for _ in range(config.failure_threshold):
            cb.record_failure(Exception("fail"))
        cb._transition_to(CircuitState.HALF_OPEN)
        
        # Should allow up to 2 calls
        assert cb.can_execute() is True
        assert cb.can_execute() is True
        # Third call should be blocked
        assert cb.can_execute() is False


class TestCircuitBreakerMetrics:
    """Test metrics tracking."""
    
    def test_tracks_successes(self):
        cb = CircuitBreaker(CircuitBreakerConfig(name="test"))
        cb.record_success()
        cb.record_success()
        assert cb.metrics.successes == 2
    
    def test_tracks_failures(self):
        cb = CircuitBreaker(CircuitBreakerConfig(name="test"))
        cb.record_failure(Exception("fail"))
        assert cb.metrics.failures == 1
    
    def test_tracks_state_changes(self):
        config = CircuitBreakerConfig(name="test")
        cb = CircuitBreaker(config)
        initial_changes = cb.metrics.state_changes
        
        # Trigger state change
        for _ in range(config.failure_threshold):
            cb.record_failure(Exception("fail"))
        
        assert cb.metrics.state_changes == initial_changes + 1


class TestCircuitBreakerRegistry:
    """Test CircuitBreakerRegistry."""
    
    def test_register_and_get(self):
        registry = CircuitBreakerRegistry()
        config = CircuitBreakerConfig(name="test")
        
        cb = registry.register(config)
        assert cb is not None
        assert registry.get("test") is cb
    
    def test_register_duplicate_raises(self):
        registry = CircuitBreakerRegistry()
        config = CircuitBreakerConfig(name="test")
        
        registry.register(config)
        with pytest.raises(ValueError):
            registry.register(config)
    
    def test_remove(self):
        registry = CircuitBreakerRegistry()
        config = CircuitBreakerConfig(name="test")
        
        registry.register(config)
        assert registry.remove("test") is True
        assert registry.get("test") is None
    
    def test_health_empty(self):
        registry = CircuitBreakerRegistry()
        health = registry.health()
        assert health["healthy"] is True
        assert health["total_circuits"] == 0
