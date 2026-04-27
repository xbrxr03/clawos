# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Observability Service (observd)
================================
Trace, monitor, and analyze LLM calls across ClawOS.

Features:
- Request/response tracing
- Token usage tracking
- Latency monitoring
- Cost estimation
- Performance analytics
- Dashboard integration

This addresses the observability gap identified in CRITICAL_GAPS_RESEARCH.md
"""
import asyncio
import json
import logging
import sqlite3
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
import uvicorn

from clawos_core.constants import CLAWOS_DIR, PORT_OBSERVD
from clawos_core.config.loader import get as get_config

log = logging.getLogger("observd")

# Database path
OBSERVDB_PATH = CLAWOS_DIR / "observability.db"


@dataclass
class LLMCall:
    """Record of a single LLM API call."""
    id: str
    timestamp: float
    workspace: str
    service: str  # Which service made the call (nexus, agentd, etc.)
    provider: str  # ollama, openai, anthropic, etc.
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    cost_usd: float
    status: str  # success, error, cached
    error_message: Optional[str] = None
    prompt_preview: Optional[str] = None  # First 200 chars
    response_preview: Optional[str] = None  # First 200 chars


class ObservabilityStore:
    """SQLite-backed store for observability data."""
    
    def __init__(self, db_path: Path = OBSERVDB_PATH):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables."""
        OBSERVDB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS llm_calls (
                    id TEXT PRIMARY KEY,
                    timestamp REAL NOT NULL,
                    workspace TEXT NOT NULL,
                    service TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    latency_ms REAL NOT NULL,
                    cost_usd REAL NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    prompt_preview TEXT,
                    response_preview TEXT
                )
            """)
            
            # Indexes for common queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON llm_calls(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_workspace ON llm_calls(workspace)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_service ON llm_calls(service)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_model ON llm_calls(model)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON llm_calls(status)")
            
            conn.commit()
    
    def record_call(self, call: LLMCall):
        """Record a new LLM call."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO llm_calls VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                call.id, call.timestamp, call.workspace, call.service,
                call.provider, call.model, call.prompt_tokens,
                call.completion_tokens, call.total_tokens, call.latency_ms,
                call.cost_usd, call.status, call.error_message,
                call.prompt_preview, call.response_preview
            ))
            conn.commit()
    
    def get_calls(
        self,
        workspace: Optional[str] = None,
        service: Optional[str] = None,
        model: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[LLMCall]:
        """Query LLM calls with filters."""
        query = "SELECT * FROM llm_calls WHERE 1=1"
        params = []
        
        if workspace:
            query += " AND workspace = ?"
            params.append(workspace)
        if service:
            query += " AND service = ?"
            params.append(service)
        if model:
            query += " AND model = ?"
            params.append(model)
        if status:
            query += " AND status = ?"
            params.append(status)
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
        
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            
            return [LLMCall(**dict(row)) for row in rows]
    
    def get_stats(
        self,
        workspace: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> dict:
        """Get aggregate statistics."""
        where_clause = "WHERE 1=1"
        params = []
        
        if workspace:
            where_clause += " AND workspace = ?"
            params.append(workspace)
        if start_time:
            where_clause += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            where_clause += " AND timestamp <= ?"
            params.append(end_time)
        
        with sqlite3.connect(self.db_path) as conn:
            # Total calls
            total = conn.execute(
                f"SELECT COUNT(*) FROM llm_calls {where_clause}",
                params
            ).fetchone()[0]
            
            # Success/error breakdown
            success = conn.execute(
                f"SELECT COUNT(*) FROM llm_calls {where_clause} AND status = 'success'",
                params
            ).fetchone()[0]
            
            error = conn.execute(
                f"SELECT COUNT(*) FROM llm_calls {where_clause} AND status = 'error'",
                params
            ).fetchone()[0]
            
            # Token usage
            tokens_result = conn.execute(
                f"""SELECT 
                    SUM(prompt_tokens) as prompt_tokens,
                    SUM(completion_tokens) as completion_tokens,
                    SUM(total_tokens) as total_tokens
                FROM llm_calls {where_clause}""",
                params
            ).fetchone()
            
            # Cost
            cost_result = conn.execute(
                f"SELECT SUM(cost_usd) FROM llm_calls {where_clause}",
                params
            ).fetchone()
            
            # Latency
            latency_result = conn.execute(
                f"""SELECT 
                    AVG(latency_ms) as avg_latency,
                    MIN(latency_ms) as min_latency,
                    MAX(latency_ms) as max_latency
                FROM llm_calls {where_clause} AND status = 'success'""",
                params
            ).fetchone()
            
            # Top models
            top_models = conn.execute(
                f"""SELECT model, COUNT(*) as count
                FROM llm_calls {where_clause}
                GROUP BY model
                ORDER BY count DESC
                LIMIT 5""",
                params
            ).fetchall()
            
            # Top services
            top_services = conn.execute(
                f"""SELECT service, COUNT(*) as count
                FROM llm_calls {where_clause}
                GROUP BY service
                ORDER BY count DESC
                LIMIT 5""",
                params
            ).fetchall()
            
            return {
                "total_calls": total,
                "success_count": success,
                "error_count": error,
                "success_rate": round(success / total * 100, 1) if total > 0 else 0,
                "prompt_tokens": tokens_result[0] or 0,
                "completion_tokens": tokens_result[1] or 0,
                "total_tokens": tokens_result[2] or 0,
                "estimated_cost_usd": round(cost_result[0] or 0, 4),
                "avg_latency_ms": round(latency_result[0] or 0, 1),
                "min_latency_ms": round(latency_result[1] or 0, 1) if latency_result[1] else 0,
                "max_latency_ms": round(latency_result[2] or 0, 1) if latency_result[2] else 0,
                "top_models": [{"model": m[0], "count": m[1]} for m in top_models],
                "top_services": [{"service": s[0], "count": s[1]} for s in top_services]
            }
    
    def get_time_series(
        self,
        interval: str = "hour",  # hour, day
        workspace: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> list[dict]:
        """Get time-series data for charts."""
        if interval == "hour":
            time_format = "%Y-%m-%d %H:00"
        else:
            time_format = "%Y-%m-%d"
        
        where_clause = "WHERE 1=1"
        params = []
        
        if workspace:
            where_clause += " AND workspace = ?"
            params.append(workspace)
        if start_time:
            where_clause += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            where_clause += " AND timestamp <= ?"
            params.append(end_time)
        
        with sqlite3.connect(self.db_path) as conn:
            query = f"""
                SELECT 
                    datetime(timestamp, 'unixepoch', 'localtime') as time_bucket,
                    COUNT(*) as calls,
                    SUM(total_tokens) as tokens,
                    SUM(cost_usd) as cost,
                    AVG(latency_ms) as avg_latency
                FROM llm_calls
                {where_clause}
                GROUP BY strftime('{time_format}', timestamp, 'unixepoch')
                ORDER BY time_bucket
            """
            
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            
            return [
                {
                    "time": row[0],
                    "calls": row[1],
                    "tokens": row[2] or 0,
                    "cost_usd": round(row[3] or 0, 4),
                    "avg_latency_ms": round(row[4] or 0, 1)
                }
                for row in rows
            ]


class ObservabilityClient:
    """Client for recording observability data from other services."""
    
    def __init__(self, store: Optional[ObservabilityStore] = None):
        self.store = store or ObservabilityStore()
    
    def record_llm_call(
        self,
        workspace: str,
        service: str,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        status: str = "success",
        error_message: Optional[str] = None,
        prompt_preview: Optional[str] = None,
        response_preview: Optional[str] = None
    ) -> str:
        """Record an LLM call. Returns the call ID."""
        # Calculate cost (rough estimates)
        cost_usd = self._estimate_cost(provider, model, prompt_tokens, completion_tokens)
        
        call = LLMCall(
            id=str(uuid4()),
            timestamp=time.time(),
            workspace=workspace,
            service=service,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            status=status,
            error_message=error_message,
            prompt_preview=prompt_preview[:200] if prompt_preview else None,
            response_preview=response_preview[:200] if response_preview else None
        )
        
        self.store.record_call(call)
        return call.id
    
    def _estimate_cost(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> float:
        """Estimate cost in USD based on provider pricing."""
        # Pricing per 1M tokens (as of 2024-2025)
        pricing = {
            "openai": {
                "gpt-4o": {"prompt": 2.50, "completion": 10.00},
                "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
                "gpt-4-turbo": {"prompt": 10.00, "completion": 30.00},
            },
            "anthropic": {
                "claude-3-opus": {"prompt": 15.00, "completion": 75.00},
                "claude-3-sonnet": {"prompt": 3.00, "completion": 15.00},
                "claude-3-haiku": {"prompt": 0.25, "completion": 1.25},
            },
            "ollama": {
                # Local models - effectively free (electricity cost negligible)
                "default": {"prompt": 0, "completion": 0},
            },
            "google": {
                "gemini-pro": {"prompt": 0.50, "completion": 1.50},
                "gemini-ultra": {"prompt": 1.00, "completion": 2.00},
            }
        }
        
        provider_pricing = pricing.get(provider, pricing["ollama"])
        model_pricing = provider_pricing.get(model, provider_pricing.get("default", {"prompt": 0, "completion": 0}))
        
        prompt_cost = (prompt_tokens / 1_000_000) * model_pricing["prompt"]
        completion_cost = (completion_tokens / 1_000_000) * model_pricing["completion"]
        
        return prompt_cost + completion_cost


# FastAPI app
app = FastAPI(title="ClawOS Observability Service", version="0.1.0")
store = ObservabilityStore()


@app.post("/api/v1/record")
async def record_call(request: dict):
    """Record a new LLM call."""
    try:
        call_id = store.record_call(LLMCall(**request))
        return {"status": "ok", "id": call_id}
    except Exception as e:
        log.error(f"Failed to record call: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/calls")
async def get_calls(
    workspace: Optional[str] = None,
    service: Optional[str] = None,
    model: Optional[str] = None,
    status: Optional[str] = None,
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0)
):
    """Get LLM calls with filtering."""
    end_time = time.time()
    start_time = end_time - (hours * 3600)
    
    calls = store.get_calls(
        workspace=workspace,
        service=service,
        model=model,
        status=status,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset
    )
    
    return {
        "calls": [asdict(c) for c in calls],
        "total": len(calls),
        "filters": {
            "workspace": workspace,
            "service": service,
            "model": model,
            "status": status,
            "hours": hours
        }
    }


@app.get("/api/v1/stats")
async def get_stats(
    workspace: Optional[str] = None,
    hours: int = Query(default=24, ge=1, le=168)
):
    """Get aggregate statistics."""
    end_time = time.time()
    start_time = end_time - (hours * 3600)
    
    stats = store.get_stats(
        workspace=workspace,
        start_time=start_time,
        end_time=end_time
    )
    
    return {
        **stats,
        "period_hours": hours,
        "workspace": workspace or "all"
    }


@app.get("/api/v1/timeseries")
async def get_timeseries(
    workspace: Optional[str] = None,
    interval: str = Query(default="hour", regex="^(hour|day)$"),
    hours: int = Query(default=24, ge=1, le=168)
):
    """Get time-series data for charts."""
    end_time = time.time()
    start_time = end_time - (hours * 3600)
    
    series = store.get_time_series(
        interval=interval,
        workspace=workspace,
        start_time=start_time,
        end_time=end_time
    )
    
    return {
        "data": series,
        "interval": interval,
        "period_hours": hours,
        "workspace": workspace or "all"
    }


@app.get("/api/v1/workspaces")
async def get_workspaces():
    """Get list of workspaces with activity."""
    with sqlite3.connect(store.db_path) as conn:
        cursor = conn.execute("""
            SELECT workspace, COUNT(*) as calls, MAX(timestamp) as last_activity
            FROM llm_calls
            GROUP BY workspace
            ORDER BY calls DESC
        """)
        rows = cursor.fetchall()
        
        return {
            "workspaces": [
                {
                    "name": row[0],
                    "total_calls": row[1],
                    "last_activity": datetime.fromtimestamp(row[2]).isoformat() if row[2] else None
                }
                for row in rows
            ]
        }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "up", "service": "observd"}


def run():
    """Run the observability service."""
    config = get_config()
    host = config.get("observability", {}).get("host", "127.0.0.1")
    port = config.get("observability", {}).get("port", PORT_OBSERVD)
    
    log.info(f"Starting observability service on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
