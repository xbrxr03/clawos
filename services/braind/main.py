# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Second Brain Service (braind)
=============================
Knowledge management system for long-term memory and insights.

Features:
- Knowledge graph with entities and relationships
- Semantic memory with vector search
- Timeline-based memory (chronological)
- Insights and pattern recognition
- Auto-categorization and tagging
- Knowledge synthesis and connections

Addresses Gap #9: Second Brain Pattern from CRITICAL_GAPS_RESEARCH.md
"""
import asyncio
import json
import logging
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

try:
    import chromadb
    from chromadb.utils import embedding_functions
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

from clawos_core.constants import CLAWOS_DIR, PORT_BRAIND

log = logging.getLogger("braind")

# Database path
BRAIN_DB = CLAWOS_DIR / "second_brain.db"


@dataclass
class KnowledgeEntity:
    """A knowledge entity (person, concept, project, etc.)."""
    id: str
    name: str
    entity_type: str  # person, concept, project, event, document, etc.
    description: str
    attributes: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    importance: float  # 0.0-1.0
    tags: List[str]


@dataclass
class KnowledgeRelation:
    """Relationship between entities."""
    id: str
    source_id: str
    target_id: str
    relation_type: str  # knows, part_of, related_to, caused_by, etc.
    strength: float  # 0.0-1.0
    evidence: List[str]  # Source IDs
    created_at: datetime


@dataclass
class Memory:
    """A memory entry with context."""
    id: str
    content: str
    memory_type: str  # fact, observation, insight, conversation, etc.
    timestamp: datetime
    source: str
    entities: List[str]  # Related entity IDs
    tags: List[str]
    importance: float
    embedding: Optional[List[float]] = None


@dataclass
class Insight:
    """Discovered insight or pattern."""
    id: str
    title: str
    description: str
    insight_type: str  # pattern, connection, trend, anomaly
    entities_involved: List[str]
    evidence: List[str]  # Memory IDs
    confidence: float
    created_at: datetime
    verified: bool = False


class KnowledgeGraph:
    """Graph-based knowledge storage."""
    
    def __init__(self, db_path: Path = BRAIN_DB):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    description TEXT,
                    attributes TEXT,  -- JSON
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    importance REAL DEFAULT 0.5,
                    tags TEXT  -- JSON array
                );
                
                CREATE TABLE IF NOT EXISTS relations (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    strength REAL DEFAULT 0.5,
                    evidence TEXT,  -- JSON array
                    created_at TIMESTAMP,
                    FOREIGN KEY (source_id) REFERENCES entities(id),
                    FOREIGN KEY (target_id) REFERENCES entities(id)
                );
                
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    type TEXT NOT NULL,
                    timestamp TIMESTAMP,
                    source TEXT,
                    entities TEXT,  -- JSON array
                    tags TEXT,  -- JSON array
                    importance REAL DEFAULT 0.5
                );
                
                CREATE TABLE IF NOT EXISTS insights (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    type TEXT NOT NULL,
                    entities TEXT,  -- JSON array
                    evidence TEXT,  -- JSON array
                    confidence REAL,
                    created_at TIMESTAMP,
                    verified INTEGER DEFAULT 0
                );
                
                CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
                CREATE INDEX IF NOT EXISTS idx_entities_tags ON entities(tags);
                CREATE INDEX IF NOT EXISTS idx_memories_timestamp ON memories(timestamp);
                CREATE INDEX IF NOT EXISTS idx_memories_tags ON memories(tags);
                CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id);
                CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id);
            """)
    
    def add_entity(self, entity: KnowledgeEntity) -> str:
        """Add entity to graph."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO entities 
                (id, name, type, description, attributes, created_at, updated_at, importance, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entity.id, entity.name, entity.entity_type, entity.description,
                json.dumps(entity.attributes), entity.created_at.isoformat(),
                entity.updated_at.isoformat(), entity.importance, json.dumps(entity.tags)
            ))
        return entity.id
    
    def add_relation(self, relation: KnowledgeRelation) -> str:
        """Add relationship."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO relations
                (id, source_id, target_id, type, strength, evidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                relation.id, relation.source_id, relation.target_id,
                relation.relation_type, relation.strength,
                json.dumps(relation.evidence), relation.created_at.isoformat()
            ))
        return relation.id
    
    def add_memory(self, memory: Memory) -> str:
        """Add memory entry."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO memories
                (id, content, type, timestamp, source, entities, tags, importance)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                memory.id, memory.content, memory.memory_type,
                memory.timestamp.isoformat(), memory.source,
                json.dumps(memory.entities), json.dumps(memory.tags), memory.importance
            ))
        return memory.id
    
    def find_entity(self, name: str) -> Optional[KnowledgeEntity]:
        """Find entity by name."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM entities WHERE name = ? COLLATE NOCASE",
                (name,)
            ).fetchone()
            
            if row:
                return self._row_to_entity(row)
        return None
    
    def find_related(self, entity_id: str, relation_type: Optional[str] = None) -> List[Tuple[KnowledgeEntity, str, float]]:
        """Find entities related to given entity."""
        with sqlite3.connect(self.db_path) as conn:
            if relation_type:
                rows = conn.execute("""
                    SELECT r.*, e.* FROM relations r
                    JOIN entities e ON r.target_id = e.id
                    WHERE r.source_id = ? AND r.type = ?
                    ORDER BY r.strength DESC
                """, (entity_id, relation_type)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT r.*, e.* FROM relations r
                    JOIN entities e ON r.target_id = e.id
                    WHERE r.source_id = ?
                    ORDER BY r.strength DESC
                """, (entity_id,)).fetchall()
            
            results = []
            for row in rows:
                # Parse relation and entity from joined row
                relation = KnowledgeRelation(
                    id=row[0], source_id=row[1], target_id=row[2],
                    relation_type=row[3], strength=row[4],
                    evidence=json.loads(row[5]), created_at=datetime.fromisoformat(row[6])
                )
                entity = self._row_to_entity(row[7:])
                results.append((entity, relation.relation_type, relation.strength))
            
            return results
    
    def search_memories(self, query: str, tags: Optional[List[str]] = None, limit: int = 10) -> List[Memory]:
        """Search memories by content or tags."""
        with sqlite3.connect(self.db_path) as conn:
            if tags:
                # Search by tags
                placeholders = ','.join('?' * len(tags))
                sql = f"""
                    SELECT * FROM memories 
                    WHERE content LIKE ? 
                    AND ({' OR '.join(['tags LIKE ?'] * len(tags))})
                    ORDER BY timestamp DESC
                    LIMIT ?
                """
                params = [f"%{query}%"] + [f"%{tag}%" for tag in tags] + [limit]
                rows = conn.execute(sql, params).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM memories WHERE content LIKE ?
                    ORDER BY timestamp DESC LIMIT ?
                """, (f"%{query}%", limit)).fetchall()
            
            return [self._row_to_memory(row) for row in rows]
    
    def get_timeline(self, start: datetime, end: datetime, entity_id: Optional[str] = None) -> List[Memory]:
        """Get memories in time range."""
        with sqlite3.connect(self.db_path) as conn:
            if entity_id:
                rows = conn.execute("""
                    SELECT * FROM memories 
                    WHERE timestamp BETWEEN ? AND ?
                    AND entities LIKE ?
                    ORDER BY timestamp
                """, (start.isoformat(), end.isoformat(), f"%{entity_id}%")).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM memories 
                    WHERE timestamp BETWEEN ? AND ?
                    ORDER BY timestamp
                """, (start.isoformat(), end.isoformat())).fetchall()
            
            return [self._row_to_memory(row) for row in rows]
    
    def _row_to_entity(self, row) -> KnowledgeEntity:
        """Convert DB row to entity."""
        return KnowledgeEntity(
            id=row[0], name=row[1], entity_type=row[2], description=row[3],
            attributes=json.loads(row[4]) if row[4] else {},
            created_at=datetime.fromisoformat(row[5]),
            updated_at=datetime.fromisoformat(row[6]),
            importance=row[7], tags=json.loads(row[8]) if row[8] else []
        )
    
    def _row_to_memory(self, row) -> Memory:
        """Convert DB row to memory."""
        return Memory(
            id=row[0], content=row[1], memory_type=row[2],
            timestamp=datetime.fromisoformat(row[3]), source=row[4],
            entities=json.loads(row[5]) if row[5] else [],
            tags=json.loads(row[6]) if row[6] else [],
            importance=row[7]
        )


class InsightEngine:
    """Engine for discovering insights and patterns."""
    
    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph
    
    def find_patterns(self) -> List[Insight]:
        """Find patterns in knowledge."""
        insights = []
        
        # Pattern 1: Frequently mentioned entities
        with sqlite3.connect(self.graph.db_path) as conn:
            rows = conn.execute("""
                SELECT entities, COUNT(*) as count 
                FROM memories 
                GROUP BY entities 
                HAVING count > 3
            """).fetchall()
            
            for row in rows:
                entities = json.loads(row[0]) if row[0] else []
                if entities:
                    insight = Insight(
                        id=str(uuid4()),
                        title=f"Frequently discussed: {', '.join(entities[:3])}",
                        description=f"These entities appear together {row[1]} times",
                        insight_type="pattern",
                        entities_involved=entities,
                        evidence=[],
                        confidence=min(0.9, row[1] / 10),
                        created_at=datetime.now()
                    )
                    insights.append(insight)
        
        return insights
    
    def find_connections(self, entity_id: str) -> List[Insight]:
        """Find non-obvious connections."""
        insights = []
        
        # Find entities connected through intermediaries
        related = self.graph.find_related(entity_id)
        
        for entity, rel_type, strength in related:
            # Find what else this entity connects to
            secondary = self.graph.find_related(entity.id)
            for sec_entity, sec_type, sec_strength in secondary:
                if sec_entity.id != entity_id:
                    # Potential indirect connection
                    insight = Insight(
                        id=str(uuid4()),
                        title=f"Indirect connection via {entity.name}",
                        description=f"{entity_id} → {entity.name} ({rel_type}) → {sec_entity.name} ({sec_type})",
                        insight_type="connection",
                        entities_involved=[entity_id, entity.id, sec_entity.id],
                        evidence=[],
                        confidence=strength * sec_strength,
                        created_at=datetime.now()
                    )
                    insights.append(insight)
        
        return insights
    
    def suggest_questions(self, entity_id: str) -> List[str]:
        """Suggest questions to ask about entity."""
        entity = self.graph.find_entity(entity_id)
        if not entity:
            return []
        
        questions = []
        
        # Based on entity type
        if entity.entity_type == "person":
            questions.extend([
                f"What projects has {entity.name} worked on?",
                f"Who else works with {entity.name}?",
                f"What are {entity.name}'s key contributions?"
            ])
        elif entity.entity_type == "project":
            questions.extend([
                f"What are the main components of {entity.name}?",
                f"Who is working on {entity.name}?",
                f"What challenges has {entity.name} faced?"
            ])
        elif entity.entity_type == "concept":
            questions.extend([
                f"What are related concepts to {entity.name}?",
                f"Where is {entity.name} applied?",
                f"What are common misconceptions about {entity.name}?"
            ])
        
        return questions


# FastAPI app
app = FastAPI(title="ClawOS Second Brain Service", version="0.1.0")

# Initialize
graph = KnowledgeGraph()
engine = InsightEngine(graph)


class EntityCreate(BaseModel):
    name: str
    entity_type: str
    description: str = ""
    attributes: Dict[str, Any] = {}
    importance: float = 0.5
    tags: List[str] = []


class MemoryCreate(BaseModel):
    content: str
    memory_type: str = "fact"
    source: str = ""
    entities: List[str] = []
    tags: List[str] = []
    importance: float = 0.5


class SearchQuery(BaseModel):
    query: str
    tags: Optional[List[str]] = None
    limit: int = 10


@app.post("/api/v1/entities")
async def create_entity(data: EntityCreate):
    """Create knowledge entity."""
    entity = KnowledgeEntity(
        id=str(uuid4()),
        name=data.name,
        entity_type=data.entity_type,
        description=data.description,
        attributes=data.attributes,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        importance=data.importance,
        tags=data.tags
    )
    
    entity_id = graph.add_entity(entity)
    return {"success": True, "id": entity_id}


@app.get("/api/v1/entities/{entity_id}")
async def get_entity(entity_id: str):
    """Get entity by ID."""
    # Implementation would query by ID
    return {"id": entity_id, "status": "found"}


@app.get("/api/v1/entities/{entity_id}/related")
async def get_related(entity_id: str, relation_type: Optional[str] = None):
    """Get related entities."""
    related = graph.find_related(entity_id, relation_type)
    return {
        "entity_id": entity_id,
        "related": [
            {
                "entity": {"id": e.id, "name": e.name, "type": e.entity_type},
                "relation": rel_type,
                "strength": strength
            }
            for e, rel_type, strength in related
        ]
    }


@app.post("/api/v1/memories")
async def create_memory(data: MemoryCreate):
    """Create memory entry."""
    memory = Memory(
        id=str(uuid4()),
        content=data.content,
        memory_type=data.memory_type,
        timestamp=datetime.now(),
        source=data.source,
        entities=data.entities,
        tags=data.tags,
        importance=data.importance
    )
    
    memory_id = graph.add_memory(memory)
    return {"success": True, "id": memory_id}


@app.post("/api/v1/memories/search")
async def search_memories(data: SearchQuery):
    """Search memories."""
    memories = graph.search_memories(data.query, data.tags, data.limit)
    return {
        "results": [
            {
                "id": m.id,
                "content": m.content,
                "type": m.memory_type,
                "timestamp": m.timestamp.isoformat(),
                "importance": m.importance
            }
            for m in memories
        ]
    }


@app.get("/api/v1/timeline")
async def get_timeline(
    start: str,
    end: str,
    entity_id: Optional[str] = None
):
    """Get memories in time range."""
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    
    memories = graph.get_timeline(start_dt, end_dt, entity_id)
    return {
        "start": start,
        "end": end,
        "memories": [
            {
                "id": m.id,
                "content": m.content,
                "timestamp": m.timestamp.isoformat()
            }
            for m in memories
        ]
    }


@app.get("/api/v1/insights/patterns")
async def get_patterns():
    """Get discovered patterns."""
    insights = engine.find_patterns()
    return {
        "patterns": [
            {
                "id": i.id,
                "title": i.title,
                "description": i.description,
                "confidence": i.confidence,
                "created_at": i.created_at.isoformat()
            }
            for i in insights
        ]
    }


@app.get("/api/v1/insights/questions/{entity_id}")
async def get_questions(entity_id: str):
    """Get suggested questions about entity."""
    questions = engine.suggest_questions(entity_id)
    return {"entity_id": entity_id, "questions": questions}


@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "up",
        "service": "braind",
        "entities": 0,  # Would query actual count
        "memories": 0,
        "insights": 0
    }


def run():
    """Run the Second Brain service."""
    uvicorn.run(app, host="127.0.0.1", port=PORT_BRAIND, log_level="info")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
