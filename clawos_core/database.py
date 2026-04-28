# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS Database Connection Pool

SQLite connection pooling and management for ClawOS services.
Provides thread-safe connection pooling, automatic retries,
and circuit breaker integration for database operations.
"""

import sqlite3
import threading
import queue
import logging
from contextlib import contextmanager
from typing import Optional, Dict, Any, Generator
from pathlib import Path

from clawos_core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from clawos_core.exceptions import DatabaseError, ErrorContext

logger = logging.getLogger(__name__)


class ConnectionPool:
    """
    Thread-safe SQLite connection pool.
    
    Manages a pool of database connections with:
    - Automatic connection creation/recycling
    - Thread-local connection assignment
    - Connection health checks
    - Circuit breaker integration
    """
    
    def __init__(
        self,
        db_path: Path,
        pool_size: int = 5,
        timeout: float = 30.0,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        self.db_path = db_path
        self.pool_size = pool_size
        self.timeout = timeout
        self._circuit_breaker = circuit_breaker
        self._pool: queue.Queue[sqlite3.Connection] = queue.Queue(maxsize=pool_size)
        self._local = threading.local()
        self._lock = threading.Lock()
        self._initialized = False
        self._connection_count = 0
        
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection."""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=self.timeout,
            check_same_thread=False,  # We manage thread safety
        )
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    
    def initialize(self):
        """Initialize the connection pool."""
        if self._initialized:
            return
            
        with self._lock:
            if self._initialized:
                return
                
            # Ensure directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Pre-populate pool
            for _ in range(self.pool_size):
                conn = self._create_connection()
                self._pool.put(conn)
                self._connection_count += 1
                
            self._initialized = True
            logger.info(f"Connection pool initialized for {self.db_path}")
    
    @contextmanager
    def acquire(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Acquire a connection from the pool.
        
        Yields:
            Database connection
            
        Raises:
            DatabaseError: If circuit breaker is open or connection fails
        """
        if self._circuit_breaker and not self._circuit_breaker.can_execute():
            raise DatabaseError(
                "Database circuit breaker is OPEN",
                context=ErrorContext(service="database", operation="acquire"),
            )
        
        if not self._initialized:
            self.initialize()
        
        conn = None
        try:
            # Try to get from pool with timeout
            conn = self._pool.get(timeout=self.timeout)
            
            # Health check - test connection
            try:
                conn.execute("SELECT 1")
            except sqlite3.Error:
                # Connection is bad, create new one
                conn = self._create_connection()
            
            yield conn
            
            # Return to pool
            self._pool.put(conn)
            
            # Record success
            if self._circuit_breaker:
                self._circuit_breaker.record_success()
                
        except queue.Empty:
            raise DatabaseError(
                "Connection pool exhausted",
                context=ErrorContext(service="database", operation="acquire"),
            )
        except sqlite3.Error as e:
            if self._circuit_breaker:
                self._circuit_breaker.record_failure(e)
            raise DatabaseError(
                f"Database error: {e}",
                context=ErrorContext(service="database", operation="acquire"),
            ) from e
        except Exception as e:
            if self._circuit_breaker:
                self._circuit_breaker.record_failure(e)
            raise
    
    def execute(
        self,
        query: str,
        params: tuple = (),
        fetch: bool = False,
    ) -> Optional[list]:
        """
        Execute a query with automatic connection management.
        
        Args:
            query: SQL query
            params: Query parameters
            fetch: Whether to fetch results
            
        Returns:
            List of rows if fetch=True, None otherwise
        """
        with self.acquire() as conn:
            cursor = conn.execute(query, params)
            if fetch:
                return cursor.fetchall()
            conn.commit()
            return None
    
    def close(self):
        """Close all connections in the pool."""
        with self._lock:
            while not self._pool.empty():
                try:
                    conn = self._pool.get_nowait()
                    conn.close()
                except queue.Empty:
                    break
            self._initialized = False
            logger.info(f"Connection pool closed for {self.db_path}")


# Global pool registry
_pool_registry: Dict[Path, ConnectionPool] = {}
_registry_lock = threading.Lock()


def get_pool(
    db_path: Path,
    pool_size: int = 5,
    timeout: float = 30.0,
) -> ConnectionPool:
    """
    Get or create a connection pool for a database.
    
    Args:
        db_path: Path to SQLite database
        pool_size: Number of connections in pool
        timeout: Connection acquisition timeout
        
    Returns:
        ConnectionPool instance
    """
    with _registry_lock:
        if db_path not in _pool_registry:
            _pool_registry[db_path] = ConnectionPool(
                db_path=db_path,
                pool_size=pool_size,
                timeout=timeout,
            )
        return _pool_registry[db_path]


def close_all_pools():
    """Close all connection pools."""
    with _registry_lock:
        for pool in _pool_registry.values():
            pool.close()
        _pool_registry.clear()


# Convenience functions

@contextmanager
def db_connection(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for database connections.
    
    Example:
        with db_connection(Path("/path/to/db.sqlite")) as conn:
            cursor = conn.execute("SELECT * FROM table")
            rows = cursor.fetchall()
    """
    pool = get_pool(db_path)
    with pool.acquire() as conn:
        yield conn


def execute_query(
    db_path: Path,
    query: str,
    params: tuple = (),
    fetch: bool = False,
) -> Optional[list]:
    """
    Execute a query on a database.
    
    Args:
        db_path: Path to database
        query: SQL query
        params: Query parameters
        fetch: Whether to fetch results
        
    Returns:
        List of rows if fetch=True, None otherwise
    """
    pool = get_pool(db_path)
    return pool.execute(query, params, fetch)
