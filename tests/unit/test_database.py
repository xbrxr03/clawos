# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unit tests for clawos_core.database module."""

import pytest
import sqlite3
import tempfile
from pathlib import Path
import threading
import time

from clawos_core.database import (
    ConnectionPool,
    get_pool,
    db_connection,
    execute_query,
)
from clawos_core.exceptions import DatabaseError


class TestConnectionPool:
    """Test ConnectionPool class."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database file."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = Path(f.name)
        yield path
        path.unlink(missing_ok=True)
    
    def test_pool_initialization(self, temp_db):
        pool = ConnectionPool(db_path=temp_db, pool_size=3)
        assert not pool._initialized
        
        pool.initialize()
        assert pool._initialized
        assert pool._connection_count == 3
    
    def test_acquire_connection(self, temp_db):
        pool = ConnectionPool(db_path=temp_db, pool_size=2)
        pool.initialize()
        
        with pool.acquire() as conn:
            assert conn is not None
            # Verify connection works
            result = conn.execute("SELECT 1").fetchone()
            assert result[0] == 1
    
    def test_pool_exhaustion(self, temp_db):
        pool = ConnectionPool(db_path=temp_db, pool_size=1, timeout=0.1)
        pool.initialize()
        
        # Use the only connection
        with pool.acquire() as conn:
            pass
        
        # Try to get connection immediately (should work since we returned it)
        with pool.acquire() as conn2:
            assert conn2 is not None
    
    def test_connection_health_check(self, temp_db):
        pool = ConnectionPool(db_path=temp_db, pool_size=1)
        pool.initialize()
        
        # Connection should pass health check
        with pool.acquire() as conn:
            conn.execute("SELECT 1")
    
    def test_execute_method(self, temp_db):
        pool = ConnectionPool(db_path=temp_db, pool_size=2)
        
        # Create table
        pool.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        
        # Insert data
        pool.execute("INSERT INTO test (name) VALUES (?)", ("test_name",))
        
        # Query data
        results = pool.execute("SELECT * FROM test WHERE name = ?", ("test_name",), fetch=True)
        assert len(results) == 1
        assert results[0]["name"] == "test_name"


class TestDatabaseErrorHandling:
    """Test database error handling."""
    
    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = Path(f.name)
        yield path
        path.unlink(missing_ok=True)
    
    def test_invalid_query_raises_error(self, temp_db):
        pool = ConnectionPool(db_path=temp_db, pool_size=1)
        pool.initialize()
        
        with pytest.raises(DatabaseError):
            pool.execute("INVALID SYNTAX")


class TestGlobalPoolRegistry:
    """Test global pool registry functions."""
    
    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = Path(f.name)
        yield path
        # Cleanup
        from clawos_core.database import _pool_registry
        _pool_registry.clear()
        path.unlink(missing_ok=True)
    
    def test_get_pool_creates_new(self, temp_db):
        pool = get_pool(temp_db, pool_size=2)
        assert pool is not None
        assert pool._initialized
    
    def test_get_pool_returns_existing(self, temp_db):
        pool1 = get_pool(temp_db)
        pool2 = get_pool(temp_db)
        assert pool1 is pool2
    
    def test_db_connection_context_manager(self, temp_db):
        with db_connection(temp_db) as conn:
            result = conn.execute("SELECT 1").fetchone()
            assert result[0] == 1
    
    def test_execute_query(self, temp_db):
        # Create table and insert
        execute_query(temp_db, "CREATE TABLE test (id INTEGER PRIMARY KEY)")
        
        # Query
        results = execute_query(temp_db, "SELECT * FROM test", fetch=True)
        assert results == []
