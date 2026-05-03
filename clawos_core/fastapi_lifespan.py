# SPDX-License-Identifier: AGPL-3.0-or-later
"""FastAPI lifespan helpers for clean startup/shutdown.

Replaces deprecated @app.on_event("startup") / @app.on_event("shutdown")
with modern lifespan context managers.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Callable, Any


@asynccontextmanager
async def single_service_lifespan(
    service_name: str,
    start_func: Callable[[], Any],
    stop_func: Callable[[], Any],
) -> AsyncGenerator[None, None]:
    """Lifespan for a single service with start/stop functions.
    
    Usage:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with single_service_lifespan("myapp", daemon.start, daemon.stop):
                yield
        
        app = FastAPI(lifespan=lifespan)
    """
    import logging
    log = logging.getLogger(service_name)
    
    try:
        await start_func() if callable(start_func) else start_func()
        log.info(f"{service_name} started")
        yield
    finally:
        await stop_func() if callable(stop_func) else stop_func()
        log.info(f"{service_name} stopped")


@asynccontextmanager
async def composite_lifespan(
    **services: dict[str, tuple[Callable, Callable]]
) -> AsyncGenerator[None, None]:
    """Lifespan for multiple services.
    
    Usage:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with composite_lifespan(
                db=(db.connect, db.close),
                cache=(cache.connect, cache.close),
            ):
                yield
    """
    import logging
    log = logging.getLogger("lifespan")
    
    # Start all services
    for name, (start, stop) in services.items():
        try:
            await start() if callable(start) else start
            log.info(f"{name} started")
        except (OSError, RuntimeError, AttributeError) as e:
            log.error(f"Failed to start {name}: {e}")
            raise
    
    try:
        yield
    finally:
        # Stop in reverse order
        for name, (start, stop) in reversed(list(services.items())):
            try:
                await stop() if callable(stop) else stop
                log.info(f"{name} stopped")
            except (OSError, RuntimeError, AttributeError) as e:
                log.error(f"Failed to stop {name}: {e}")


def create_simple_lifespan(
    service_name: str,
    startup_tasks: list[Callable] = None,
    shutdown_tasks: list[Callable] = None,
):
    """Create a simple lifespan with just startup/shutdown tasks.
    
    Usage:
        app = FastAPI(lifespan=create_simple_lifespan("myapp"))
    """
    @asynccontextmanager
    async def lifespan(app):
        import logging
        log = logging.getLogger(service_name)
        
        if startup_tasks:
            for task in startup_tasks:
                try:
                    result = task()
                    if hasattr(result, '__await__'):
                        await result
                except (AttributeError, TypeError) as e:
                    log.error(f"Startup task failed: {e}")
        
        log.info(f"{service_name} ready")
        yield
        
        if shutdown_tasks:
            for task in shutdown_tasks:
                try:
                    result = task()
                    if hasattr(result, '__await__'):
                        await result
                except (AttributeError, TypeError) as e:
                    log.error(f"Shutdown task failed: {e}")
        
        log.info(f"{service_name} shut down")
    
    return lifespan
