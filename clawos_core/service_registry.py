# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS Service Registry

Central service discovery and registration for ClawOS microservices.
Provides health-aware routing, load balancing hints, and automatic
service discovery.

Features:
- Service registration/deregistration
- Health-aware service discovery
- Metadata and capability tags
- Circuit breaker integration
- TTL-based heartbeat management
"""

import json
import time
import threading
from typing import Dict, List, Optional, Set, Callable, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging

from clawos_core.exceptions import ServiceUnavailableError, ErrorContext
from clawos_core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceInstance:
    """Represents a registered service instance."""
    name: str
    host: str
    port: int
    version: str = "1.0.0"
    status: ServiceStatus = ServiceStatus.UNKNOWN
    last_heartbeat: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    capabilities: Set[str] = field(default_factory=set)
    health_endpoint: str = "/health"
    circuit_breaker: Optional[CircuitBreaker] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "version": self.version,
            "status": self.status.value,
            "last_heartbeat": self.last_heartbeat,
            "metadata": self.metadata,
            "capabilities": list(self.capabilities),
            "health_endpoint": self.health_endpoint,
            "address": f"{self.host}:{self.port}",
        }


@dataclass
class ServiceRegistryConfig:
    """Configuration for service registry."""
    heartbeat_ttl: float = 60.0  # Seconds before considering service unhealthy
    cleanup_interval: float = 30.0  # Cleanup interval for dead services
    enable_circuit_breaker: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: float = 30.0


class ServiceRegistry:
    """
    Central service registry for ClawOS.
    
    Thread-safe service registration and discovery with health tracking
    and circuit breaker integration.
    
    Example:
        registry = ServiceRegistry()
        
        # Register a service
        registry.register(
            name="braind",
            host="localhost",
            port=7082,
            capabilities={"knowledge_graph", "semantic_search"},
        )
        
        # Discover services
        braind = registry.discover("braind")
        if braind:
            address = braind.address
    """
    
    def __init__(self, config: Optional[ServiceRegistryConfig] = None):
        self.config = config or ServiceRegistryConfig()
        self._services: Dict[str, ServiceInstance] = {}
        self._lock = threading.RLock()
        self._shutdown = False
        self._cleanup_thread: Optional[threading.Thread] = None
        self._watchers: List[Callable[[str, ServiceStatus], None]] = []
        
        # Start cleanup thread
        self._start_cleanup()
        
    def _start_cleanup(self):
        """Start the cleanup thread for expired services."""
        def cleanup_loop():
            while not self._shutdown:
                time.sleep(self.config.cleanup_interval)
                if not self._shutdown:
                    self._cleanup_expired()
        
        self._cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        self._cleanup_thread.start()
        
    def _cleanup_expired(self):
        """Remove expired services based on TTL."""
        now = time.time()
        expired = []
        
        with self._lock:
            for name, instance in list(self._services.items()):
                if now - instance.last_heartbeat > self.config.heartbeat_ttl:
                    if instance.status != ServiceStatus.UNHEALTHY:
                        logger.warning(f"Service '{name}' expired (TTL)")
                        instance.status = ServiceStatus.UNHEALTHY
                        self._notify_watchers(name, ServiceStatus.UNHEALTHY)
                    
                    # Remove if expired for 2x TTL
                    if now - instance.last_heartbeat > self.config.heartbeat_ttl * 2:
                        expired.append(name)
            
            for name in expired:
                del self._services[name]
                logger.info(f"Removed expired service: {name}")
    
    def register(
        self,
        name: str,
        host: str,
        port: int,
        version: str = "1.0.0",
        capabilities: Optional[Set[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        health_endpoint: str = "/health",
    ) -> ServiceInstance:
        """
        Register a new service instance.
        
        Args:
            name: Service name (e.g., "braind")
            host: Service host
            port: Service port
            version: Service version
            capabilities: Set of capability strings
            metadata: Additional metadata
            health_endpoint: Health check endpoint path
            
        Returns:
            Registered service instance
        """
        with self._lock:
            # Create circuit breaker if enabled
            cb = None
            if self.config.enable_circuit_breaker:
                cb = CircuitBreaker(
                    CircuitBreakerConfig(
                        name=f"registry-{name}",
                        failure_threshold=self.config.circuit_breaker_threshold,
                        timeout_seconds=self.config.circuit_breaker_timeout,
                    )
                )
            
            instance = ServiceInstance(
                name=name,
                host=host,
                port=port,
                version=version,
                status=ServiceStatus.HEALTHY,
                last_heartbeat=time.time(),
                metadata=metadata or {},
                capabilities=capabilities or set(),
                health_endpoint=health_endpoint,
                circuit_breaker=cb,
            )
            
            self._services[name] = instance
            logger.info(f"Registered service: {name} at {host}:{port}")
            return instance
    
    def deregister(self, name: str) -> bool:
        """
        Deregister a service.
        
        Args:
            name: Service name
            
        Returns:
            True if service was removed
        """
        with self._lock:
            if name in self._services:
                del self._services[name]
                logger.info(f"Deregistered service: {name}")
                return True
            return False
    
    def heartbeat(self, name: str, status: Optional[ServiceStatus] = None) -> bool:
        """
        Update service heartbeat.
        
        Args:
            name: Service name
            status: Optional status update
            
        Returns:
            True if service exists and was updated
        """
        with self._lock:
            if name not in self._services:
                return False
            
            instance = self._services[name]
            instance.last_heartbeat = time.time()
            
            if status and status != instance.status:
                old_status = instance.status
                instance.status = status
                logger.debug(f"Service '{name}' status: {old_status.value} -> {status.value}")
                self._notify_watchers(name, status)
            
            return True
    
    def discover(self, name: str) -> Optional[ServiceInstance]:
        """
        Discover a service by name.
        
        Args:
            name: Service name
            
        Returns:
            Service instance if found and healthy, None otherwise
        """
        with self._lock:
            instance = self._services.get(name)
            
            if not instance:
                return None
            
            if instance.status == ServiceStatus.UNHEALTHY:
                return None
            
            # Check circuit breaker
            if instance.circuit_breaker and not instance.circuit_breaker.can_execute():
                raise ServiceUnavailableError(
                    f"Service '{name}' circuit breaker is OPEN",
                    context=ErrorContext(service="registry", operation="discover"),
                )
            
            return instance
    
    def discover_by_capability(self, capability: str) -> List[ServiceInstance]:
        """
        Discover services by capability.
        
        Args:
            capability: Capability string
            
        Returns:
            List of matching healthy services
        """
        with self._lock:
            return [
                instance for instance in self._services.values()
                if capability in instance.capabilities
                and instance.status != ServiceStatus.UNHEALTHY
            ]
    
    def list_services(self) -> List[ServiceInstance]:
        """List all registered services."""
        with self._lock:
            return list(self._services.values())
    
    def get_healthy_services(self) -> List[ServiceInstance]:
        """List all healthy services."""
        with self._lock:
            return [
                instance for instance in self._services.values()
                if instance.status == ServiceStatus.HEALTHY
            ]
    
    def health(self) -> Dict[str, Any]:
        """
        Get registry health status.
        
        Returns:
            Dictionary with service counts and statuses
        """
        with self._lock:
            statuses = {s.name: s.status.value for s in self._services.values()}
            healthy = sum(1 for s in self._services.values() if s.status == ServiceStatus.HEALTHY)
            
            return {
                "total_services": len(self._services),
                "healthy": healthy,
                "degraded": sum(1 for s in self._services.values() if s.status == ServiceStatus.DEGRADED),
                "unhealthy": sum(1 for s in self._services.values() if s.status == ServiceStatus.UNHEALTHY),
                "unknown": sum(1 for s in self._services.values() if s.status == ServiceStatus.UNKNOWN),
                "services": statuses,
            }
    
    def watch(self, callback: Callable[[str, ServiceStatus], None]):
        """Register a callback for service status changes."""
        self._watchers.append(callback)
    
    def _notify_watchers(self, name: str, status: ServiceStatus):
        """Notify all watchers of status change."""
        for watcher in self._watchers:
            try:
                watcher(name, status)
            except (OSError, ValueError) as e:
                logger.error(f"Watcher failed: {e}")
    
    def shutdown(self):
        """Shutdown the registry and cleanup resources."""
        self._shutdown = True
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5.0)
        logger.info("Service registry shutdown")
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize registry to dictionary."""
        return {
            "config": {
                "heartbeat_ttl": self.config.heartbeat_ttl,
                "cleanup_interval": self.config.cleanup_interval,
            },
            "health": self.health(),
            "services": {name: instance.to_dict() for name, instance in self._services.items()},
        }


# Global registry instance
_global_registry: Optional[ServiceRegistry] = None
_registry_lock = threading.Lock()


def get_registry() -> ServiceRegistry:
    """Get or create the global service registry."""
    global _global_registry
    with _registry_lock:
        if _global_registry is None:
            _global_registry = ServiceRegistry()
        return _global_registry


def register(
    name: str,
    host: str,
    port: int,
    **kwargs,
) -> ServiceInstance:
    """Convenience function to register with global registry."""
    return get_registry().register(name, host, port, **kwargs)


def discover(name: str) -> Optional[ServiceInstance]:
    """Convenience function to discover from global registry."""
    return get_registry().discover(name)


def heartbeat(name: str, status: Optional[ServiceStatus] = None) -> bool:
    """Convenience function to send heartbeat to global registry."""
    return get_registry().heartbeat(name, status)


def health() -> Dict[str, Any]:
    """Get global registry health."""
    return get_registry().health()


def shutdown():
    """Shutdown global registry."""
    global _global_registry
    with _registry_lock:
        if _global_registry:
            _global_registry.shutdown()
            _global_registry = None
