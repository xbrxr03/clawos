# SPDX-License-Identifier: AGPL-3.0-or-later
"""ClawOS Core - foundational modules for the AI operating system."""

from clawos_core.exceptions import (
    ClawOSError,
    AuthenticationError,
    ValidationError,
    ResourceNotFoundError,
    ServiceUnavailableError,
    CircuitBreakerError,
    DatabaseError,
    ErrorCode,
    ErrorSeverity,
    ErrorContext,
    handle_exception,
    register_exception_handlers,
)

from clawos_core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitState,
    get_registry,
    register,
    get,
    health,
)

__all__ = [
    # Exceptions
    "ClawOSError",
    "AuthenticationError",
    "ValidationError",
    "ResourceNotFoundError",
    "ServiceUnavailableError",
    "CircuitBreakerError",
    "DatabaseError",
    "ErrorCode",
    "ErrorSeverity",
    "ErrorContext",
    "handle_exception",
    "register_exception_handlers",
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerRegistry",
    "CircuitState",
    "get_registry",
    "register",
    "get",
    "health",
]
