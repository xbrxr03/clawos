# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS Bootstrap Module

Initialization and startup sequence for ClawOS services.
Provides ordered initialization, dependency injection, and
graceful shutdown handling.
"""

import logging
import signal
import sys
from typing import List, Optional, Callable, Dict, Any
from dataclasses import dataclass
from pathlib import Path

from clawos_core.constants import PORT_BRAIND, PORT_SANDBOXD, PORT_VISUALD
from clawos_core.service_registry import get_registry, ServiceStatus
from clawos_core.exceptions import ServiceUnavailableError

logger = logging.getLogger(__name__)


@dataclass
class ServiceConfig:
    """Configuration for a ClawOS service."""
    name: str
    host: str = "127.0.0.1"
    port: int = 0
    dependencies: List[str] = None
    init_func: Optional[Callable[[], Any]] = None
    health_func: Optional[Callable[[], Dict[str, Any]]] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class Bootstrap:
    """
    ClawOS bootstrap manager.
    
    Handles ordered initialization of services with dependency resolution
    and graceful shutdown.
    
    Example:
        bootstrap = Bootstrap()
        
        bootstrap.register(ServiceConfig(
            name="braind",
            port=PORT_BRAIND,
            init_func=init_braind,
        ))
        
        bootstrap.initialize_all()
    """
    
    def __init__(self):
        self._services: Dict[str, ServiceConfig] = {}
        self._initialized: List[str] = []
        self._shutdown_handlers: List[Callable[[], None]] = []
        self._registry = get_registry()
        
        # Setup signal handlers
        self._setup_signals()
    
    def _setup_signals(self):
        """Setup graceful shutdown signal handlers."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            self.shutdown()
            sys.exit(0)
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
    
    def register(self, config: ServiceConfig):
        """Register a service configuration."""
        self._services[config.name] = config
        logger.debug(f"Registered service: {config.name}")
    
    def initialize_all(self) -> bool:
        """
        Initialize all services in dependency order.
        
        Returns:
            True if all services initialized successfully
        """
        # Topological sort by dependencies
        order = self._resolve_dependencies()
        
        logger.info(f"Initializing {len(order)} services: {order}")
        
        for name in order:
            config = self._services[name]
            
            try:
                # Check dependencies
                for dep in config.dependencies:
                    if dep not in self._initialized:
                        raise ServiceUnavailableError(
                            f"Dependency '{dep}' not initialized for '{name}'"
                        )
                
                # Initialize service
                if config.init_func:
                    logger.info(f"Initializing {name}...")
                    config.init_func()
                
                # Register with service registry
                self._registry.register(
                    name=name,
                    host=config.host,
                    port=config.port,
                    metadata={"version": "1.0.0"},
                )
                
                self._initialized.append(name)
                logger.info(f"✓ {name} initialized")
                
            except Exception as e:
                logger.error(f"✗ Failed to initialize {name}: {e}")
                self._registry.register(
                    name=name,
                    host=config.host,
                    port=config.port,
                    status=ServiceStatus.UNHEALTHY,
                )
                return False
        
        logger.info(f"Successfully initialized {len(self._initialized)} services")
        return True
    
    def _resolve_dependencies(self) -> List[str]:
        """
        Resolve service dependencies using topological sort.
        
        Returns:
            Ordered list of service names
        """
        # Simple dependency resolution
        resolved = []
        unresolved = set(self._services.keys())
        
        while unresolved:
            # Find services with all dependencies resolved
            ready = {
                name for name in unresolved
                if all(dep in resolved for dep in self._services[name].dependencies)
            }
            
            if not ready:
                # Circular dependency detected
                raise RuntimeError(f"Circular dependency detected: {unresolved}")
            
            resolved.extend(sorted(ready))
            unresolved -= ready
        
        return resolved
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all initialized services.
        
        Returns:
            Health status dictionary
        """
        results = {}
        healthy = 0
        
        for name in self._initialized:
            config = self._services[name]
            
            try:
                if config.health_func:
                    health = config.health_func()
                    results[name] = health
                    if health.get("status") == "ok":
                        healthy += 1
                else:
                    # Try to get from registry
                    instance = self._registry.discover(name)
                    if instance:
                        results[name] = {"status": instance.status.value}
                        if instance.status == ServiceStatus.HEALTHY:
                            healthy += 1
                    else:
                        results[name] = {"status": "unknown"}
                        
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                results[name] = {"status": "error", "error": str(e)}
        
        return {
            "overall": "healthy" if healthy == len(self._initialized) else "degraded",
            "healthy_count": healthy,
            "total_count": len(self._initialized),
            "services": results,
        }
    
    def on_shutdown(self, handler: Callable[[], None]):
        """Register a shutdown handler."""
        self._shutdown_handlers.append(handler)
    
    def shutdown(self):
        """Graceful shutdown of all services."""
        logger.info("Shutting down ClawOS...")
        
        # Run shutdown handlers in reverse order
        for handler in reversed(self._shutdown_handlers):
            try:
                handler()
            except Exception as e:
                logger.error(f"Shutdown handler failed: {e}")
        
        # Shutdown registry
        self._registry.shutdown()
        
        logger.info("ClawOS shutdown complete")


# Convenience functions

def create_default_bootstrap() -> Bootstrap:
    """Create bootstrap with default ClawOS services."""
    bootstrap = Bootstrap()
    
    # Core services
    bootstrap.register(ServiceConfig(
        name="braind",
        port=PORT_BRAIND,
    ))
    
    bootstrap.register(ServiceConfig(
        name="sandboxd",
        port=PORT_SANDBOXD,
    ))
    
    bootstrap.register(ServiceConfig(
        name="visuald",
        port=PORT_VISUALD,
    ))
    
    return bootstrap


# Global bootstrap instance
_global_bootstrap: Optional[Bootstrap] = None


def get_bootstrap() -> Bootstrap:
    """Get or create global bootstrap instance."""
    global _global_bootstrap
    if _global_bootstrap is None:
        _global_bootstrap = create_default_bootstrap()
    return _global_bootstrap
