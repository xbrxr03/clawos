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
    get_registry as get_circuit_registry,
    register as register_circuit,
    get as get_circuit,
    health as circuit_health,
)

from clawos_core.service_registry import (
    ServiceRegistry,
    ServiceRegistryConfig,
    ServiceInstance,
    ServiceStatus,
    get_registry,
    register,
    discover,
    heartbeat,
    health,
)

from clawos_core.database import (
    ConnectionPool,
    get_pool,
    db_connection,
    execute_query,
)

from clawos_core.bootstrap import (
    Bootstrap,
    ServiceConfig,
    get_bootstrap,
    create_default_bootstrap,
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
    "get_circuit_registry",
    "register_circuit",
    "get_circuit",
    "circuit_health",
    # Service Registry
    "ServiceRegistry",
    "ServiceRegistryConfig",
    "ServiceInstance",
    "ServiceStatus",
    "get_registry",
    "register",
    "discover",
    "heartbeat",
    "health",
    # Database
    "ConnectionPool",
    "get_pool",
    "db_connection",
    "execute_query",
    # Bootstrap
    "Bootstrap",
    "ServiceConfig",
    "get_bootstrap",
    "create_default_bootstrap",
]
