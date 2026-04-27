# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for Second Brain service (braind)."""

import pytest
from datetime import datetime
from pathlib import Path
import tempfile
import shutil

from services.braind.main import (
    KnowledgeGraph,
    KnowledgeEntity,
    KnowledgeRelation,
    Memory,
    InsightEngine,
    NodeType as BrainNodeType,
    PortType as BrainPortType
)


@pytest.fixture
def temp_db():
    """Create temporary database."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_brain.db"
    yield db_path
    shutil.rmtree(temp_dir)


@pytest.fixture
def graph(temp_db):
    """Create knowledge graph."""
    return KnowledgeGraph(db_path=temp_db)


class TestKnowledgeGraph:
    """Test knowledge graph operations."""
    
    def test_add_entity(self, graph):
        """Test adding entity to graph."""
        entity = KnowledgeEntity(
            id="test-1",
            name="Python",
            entity_type="concept",
            description="Programming language",
            attributes={"paradigm": "multi-paradigm"},
            created_at=datetime.now(),
            updated_at=datetime.now(),
            importance=0.9,
            tags=["programming", "language"]
        )
        
        entity_id = graph.add_entity(entity)
        assert entity_id == "test-1"
        
        # Verify retrieval
        found = graph.find_entity("Python")
        assert found is not None
        assert found.name == "Python"
        assert found.entity_type == "concept"
    
    def test_add_relation(self, graph):
        """Test adding relation between entities."""
        # Create entities
        python = KnowledgeEntity(
            id="python", name="Python", entity_type="concept",
            description="", attributes={}, created_at=datetime.now(),
            updated_at=datetime.now(), importance=0.9, tags=[]
        )
        django = KnowledgeEntity(
            id="django", name="Django", entity_type="framework",
            description="", attributes={}, created_at=datetime.now(),
            updated_at=datetime.now(), importance=0.8, tags=[]
        )
        
        graph.add_entity(python)
        graph.add_entity(django)
        
        # Create relation
        relation = KnowledgeRelation(
            id="rel-1",
            source_id="django",
            target_id="python",
            relation_type="built_on",
            strength=1.0,
            evidence=["docs"],
            created_at=datetime.now()
        )
        
        graph.add_relation(relation)
        
        # Verify
        related = graph.find_related("django")
        assert len(related) == 1
        assert related[0][0].name == "Python"
    
    def test_add_memory(self, graph):
        """Test adding memory entry."""
        memory = Memory(
            id="mem-1",
            content="Learned about decorators",
            memory_type="insight",
            timestamp=datetime.now(),
            source="conversation",
            entities=["python"],
            tags=["learning", "python"],
            importance=0.7
        )
        
        mem_id = graph.add_memory(memory)
        assert mem_id == "mem-1"
        
        # Search
        results = graph.search_memories("decorators")
        assert len(results) == 1
        assert results[0].content == "Learned about decorators"
    
    def test_get_timeline(self, graph):
        """Test timeline retrieval."""
        # Add memories at different times
        now = datetime.now()
        
        for i in range(3):
            memory = Memory(
                id=f"mem-{i}",
                content=f"Memory {i}",
                memory_type="observation",
                timestamp=now,
                source="test",
                entities=[],
                tags=[],
                importance=0.5
            )
            graph.add_memory(memory)
        
        # Get timeline
        timeline = graph.get_timeline(
            start=now.replace(hour=0, minute=0, second=0),
            end=now
        )
        
        assert len(timeline) == 3


class TestInsightEngine:
    """Test insight generation."""
    
    def test_find_patterns(self, graph):
        """Test pattern discovery."""
        engine = InsightEngine(graph)
        
        # Add multiple related memories
        for i in range(5):
            memory = Memory(
                id=f"mem-{i}",
                content=f"Discussion about Python",
                memory_type="conversation",
                timestamp=datetime.now(),
                source="chat",
                entities=["python"],
                tags=["coding"],
                importance=0.6
            )
            graph.add_memory(memory)
        
        patterns = engine.find_patterns()
        assert len(patterns) > 0


class TestAPI:
    """Test FastAPI endpoints."""
    
    def test_health_endpoint(self):
        """Test health check."""
        from fastapi.testclient import TestClient
        from services.braind.main import app
        
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "up"
        assert data["service"] == "braind"
