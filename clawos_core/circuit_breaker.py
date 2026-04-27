# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS Circuit Breaker Module

Implements the Circuit Breaker pattern for resilient microservices communication.
Prevents cascade failures by temporarily disabling calls to failing services.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Service is failing, requests are blocked
- HALF_OPEN: Testing if service has recovered

Features:
- Configurable failure thresholds and timeouts
- Automatic state transitions
- Exponential backoff for retries
- Thread-safe operations
- Metrics and health reporting
"""

import time
import threading
from enum import Enum
from typing import Callable, Optional, TypeVar, Generic, Dict, Any
from dataclasses import dataclass, field
from functools import wraps
import logging

from .exceptions import CircuitBreakerError, ErrorCode, ErrorContext

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    name: str
    failure_threshold: int = 5          # Failures before opening
    success_threshold: int = 3            # Successes to close
    timeout_seconds: float = 60.0         # Time before half-open
    half_open_max_calls: int = 3          # Max calls in half-open
    exception_types: tuple = (Exception,) # Exceptions that count as failures
    
    def __post_init__(self):
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if self.success_threshold < 1:
            raise ValueError("success_threshold must be >= 1")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")


@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker monitoring."""
    state_changes: int = 0
    failures: int = 0
    successes: int = 0
    rejected_calls: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    consecutive_successes: int = 0
    consecutive_failures: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "state_changes": self.state_changes,
            "failures": self.failures,
            "successes": self.successes,
            "rejected_calls": self.rejected_calls,
            "consecutive_successes": self.consecutive_successes,
            "consecutive_failures": self.consecutive_failures,
        }


class CircuitBreaker:
    """
    Circuit Breaker implementation for resilient service calls.
    
    Thread-safe circuit breaker that monitors calls and automatically
    transitions between states based on failure/success patterns.
    
    Example:
        breaker = CircuitBreaker(CircuitBreakerConfig(
            name="braind-api",
            failure_threshold=5,
            timeout_seconds=30.0
        ))
        
        @breaker.protect
        def call_braind_api(data: dict) -> dict:
            # This will raise CircuitBreakerError if circuit is open
            return requests.post("http://braind:7082/process", json=data).json()
    """
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self._state = CircuitState.CLOSED
        self._state_lock = threading.RLock()
        self._half_open_calls = 0
        self._last_state_change = time.time()
        self._metrics = CircuitBreakerMetrics()
        
        logger.info(f"Circuit breaker '{config.name}' initialized (CLOSED)")
    
    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        with self._state_lock:
            return self._state
    
    @property
    def metrics(self) -> CircuitBreakerMetrics:
        """Current metrics (read-only)."""
        with self._state_lock:
            # Return a copy to prevent external modification
            return CircuitBreakerMetrics(**self._metrics.__dict__)
    
    def can_execute(self) -> bool:
        """
        Check if a call can be executed.
        
        Returns:
            True if call should proceed, False if it should be rejected
        """
        with self._state_lock:
            if self._state == CircuitState.CLOSED:
                return True
            
            if self._state == CircuitState.OPEN:
                # Check if timeout has passed
                if time.time() - self._last_state_change >= self.config.timeout_seconds:
                    logger.info(f"Circuit '{self.config.name}' transitioning to HALF_OPEN")
                    self._transition_to(CircuitState.HALF_OPEN)
                    return True
                else:
                    self._metrics.rejected_calls += 1
                    return False
            
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self.config.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                else:
                    self._metrics.rejected_calls += 1
                    return False
            
            return False
    
    def record_success(self):
        """Record a successful call."""
        with self._state_lock:
            self._metrics.successes += 1
            self._metrics.consecutive_successes += 1
            self._metrics.consecutive_failures = 0
            self._metrics.last_success_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                if self._metrics.consecutive_successes >= self.config.success_threshold:
                    logger.info(f"Circuit '{self.config.name}' closing (sufficient successes)")
                    self._transition_to(CircuitState.CLOSED)
            elif self._state == CircuitState.CLOSED:
                # Reset consecutive failures on success
                pass
    
    def record_failure(self, exception: Exception):
        """Record a failed call."""
        with self._state_lock:
            self._metrics.failures += 1
            self._metrics.consecutive_failures += 1
            self._metrics.consecutive_successes = 0
            self._metrics.last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                logger.warning(f"Circuit '{self.config.name}' opening (failure in HALF_OPEN)")
                self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.CLOSED:
                if self._metrics.consecutive_failures >= self.config.failure_threshold:
                    logger.warning(
                        f"Circuit '{self.config.name}' opening ({self._metrics.consecutive_failures} failures)"
                    )
                    self._transition_to(CircuitState.OPEN)
    
    def _transition_to(self, new_state: CircuitState):
        """Transition to a new state."""
        old_state = self._state
        self._state = new_state
        self._last_state_change = time.time()
        self._metrics.state_changes += 1
        
        if new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._metrics.consecutive_successes = 0
        elif new_state == CircuitState.CLOSED:
            self._half_open_calls = 0
            self._metrics.consecutive_failures = 0
    
    def protect(self, func: Callable[..., T]) -> Callable[..., T]:
        """
        Decorator to protect a function with this circuit breaker.
        
        Args:
            func: The function to protect
            
        Returns:
            Wrapped function that checks circuit before executing
        """
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            if not self.can_execute():
                context = ErrorContext(
                    service=self.config.name,
                    operation=func.__name__,
                )
                raise CircuitBreakerError(
                    f"Circuit breaker '{self.config.name}' is OPEN",
                    code=ErrorCode.CIRCUIT_BREAKER_OPEN,
                    context=context,
                )
            
            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except self.config.exception_types as e:
                self.record_failure(e)
                raise
        
        return wrapper
    
    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Call a function with circuit breaker protection.
        
        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerError: If circuit is open
            Exception: Original exception from func
        """
        if not self.can_execute():
            context = ErrorContext(
                service=self.config.name,
                operation=func.__name__,
            )
            raise CircuitBreakerError(
                f"Circuit breaker '{self.config.name}' is OPEN",
                code=ErrorCode.CIRCUIT_BREAKER_OPEN,
                context=context,
            )
        
        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except self.config.exception_types as e:
            self.record_failure(e)
            raise
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize circuit breaker state to dictionary."""
        with self._state_lock:
            return {
                "name": self.config.name,
                "state": self._state.value,
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "success_threshold": self.config.success_threshold,
                    "timeout_seconds": self.config.timeout_seconds,
                },
                "metrics": self._metrics.to_dict(),
                "half_open_calls": self._half_open_calls,
                "time_in_state": time.time() - self._last_state_change,
            }


# Registry for managing multiple circuit breakers

class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.
    
    Provides centralized access to circuit breakers by name
    and health monitoring across all circuits.
    """
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.RLock()
    
    def register(self, config: CircuitBreakerConfig) -> CircuitBreaker:
        """
        Register a new circuit breaker.
        
        Args:
            config: Circuit breaker configuration
            
        Returns:
            The registered circuit breaker
        """
        with self._lock:
            if config.name in self._breakers:
                raise ValueError(f"Circuit breaker '{config.name}' already registered")
            
            breaker = CircuitBreaker(config)
            self._breakers[config.name] = breaker
            logger.info(f"Registered circuit breaker: {config.name}")
            return breaker
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get a circuit breaker by name."""
        with self._lock:
            return self._breakers.get(name)
    
    def remove(self, name: str) -> bool:
        """Remove a circuit breaker. Returns True if removed."""
        with self._lock:
            if name in self._breakers:
                del self._breakers[name]
                logger.info(f"Removed circuit breaker: {name}")
                return True
            return False
    
    def health(self) -> Dict[str, Any]:
        """
        Get health status of all circuit breakers.
        
        Returns:
            Dictionary with overall health and individual breaker states
        """
        with self._lock:
            states = {name: breaker.state.value for name, breaker in self._breakers.items()}
            open_circuits = sum(1 for s in states.values() if s == "open")
            
            return {
                "healthy": open_circuits == 0,
                "total_circuits": len(self._breakers),
                "open_circuits": open_circuits,
                "states": states,
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize all circuit breakers."""
        with self._lock:
            return {
                name: breaker.to_dict()
                for name, breaker in self._breakers.items()
            }


# Global registry instance
_global_registry = CircuitBreakerRegistry()


def get_registry() -> CircuitBreakerRegistry:
    """Get the global circuit breaker registry."""
    return _global_registry


def register(name: str, **kwargs) -> CircuitBreaker:
    """Convenience function to register a circuit breaker globally."""
    config = CircuitBreakerConfig(name=name, **kwargs)
    return _global_registry.register(config)


def get(name: str) -> Optional[CircuitBreaker]:
    """Convenience function to get a circuit breaker by name."""
    return _global_registry.get(name)


def health() -> Dict[str, Any]:
    """Get health status of all registered circuit breakers."""
    return _global_registry.health()


# FastAPI integration

def get_circuit_breaker_health():
    """
    Get circuit breaker health for FastAPI health endpoint.
    
    Returns:
        Dictionary suitable for health check responses
    """
    health_data = health()
    
    return {
        "status": "up" if health_data["healthy"] else "degraded",
        "service": "circuit-breaker",
        "details": health_data,
    }
