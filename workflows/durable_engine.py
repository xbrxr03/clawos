# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Durable Workflow Engine
=======================
Survives crashes and restarts with checkpoint/resume capability.

This addresses the durable execution gap from CRITICAL_GAPS_RESEARCH.md
inspired by Inngest, Temporal, and modern workflow orchestration.

Features:
- Step-based workflows
- Automatic checkpointing after each step
- Resume from last checkpoint on restart
- Idempotent step execution
- Step timeout and retry with backoff
- Parent-child workflow composition
"""
import asyncio
import json
import logging
import sqlite3
import time
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional, Union
from uuid import uuid4

from clawos_core.constants import CLAWOS_DIR

log = logging.getLogger("durable_workflows")

# Database path
DURABLE_DB_PATH = CLAWOS_DIR / "durable_workflows.db"


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class WorkflowStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StepResult:
    """Result of a workflow step execution."""
    output: Any
    error: Optional[str] = None
    retry_count: int = 0
    duration_ms: float = 0.0


@dataclass
class StepDefinition:
    """Definition of a workflow step."""
    id: str
    name: str
    func: Callable[..., Coroutine[Any, Any, Any]]
    retries: int = 3
    timeout_s: int = 60
    backoff_base_s: float = 1.0


class WorkflowContext:
    """Context passed to each step with checkpoint/resume capability."""
    
    def __init__(
        self,
        workflow_id: str,
        run_id: str,
        workspace: str,
        args: dict,
        engine: "DurableWorkflowEngine"
    ):
        self.workflow_id = workflow_id
        self.run_id = run_id
        self.workspace = workspace
        self.args = args
        self.engine = engine
        self._step_results: dict[str, StepResult] = {}
        self._current_step: Optional[str] = None
    
    def step_result(self, step_id: str) -> Optional[StepResult]:
        """Get result of a previously executed step."""
        return self._step_results.get(step_id)
    
    def all_results(self) -> dict[str, Any]:
        """Get all step outputs."""
        return {
            step_id: result.output
            for step_id, result in self._step_results.items()
            if result.error is None
        }


class DurableWorkflowEngine:
    """
    Durable workflow engine with checkpoint/resume.
    
    Usage:
        engine = DurableWorkflowEngine()
        
        # Define workflow
        workflow = engine.workflow("my_workflow")
        
        @workflow.step("step1")
        async def step1(ctx: WorkflowContext):
            # Do work
            return result
        
        @workflow.step("step2")
        async def step2(ctx: WorkflowContext):
            # Access previous step result
            prev = ctx.step_result("step1")
            return process(prev.output)
        
        # Run workflow
        result = await engine.run("my_workflow", args={"key": "value"})
    """
    
    def __init__(self, db_path: Path = DURABLE_DB_PATH):
        self.db_path = db_path
        self._workflows: dict[str, "WorkflowDefinition"] = {}
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables."""
        DURABLE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            # Workflow runs
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_runs (
                    run_id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    workspace TEXT NOT NULL,
                    status TEXT NOT NULL,
                    args TEXT NOT NULL,
                    result TEXT,
                    error TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    completed_at REAL
                )
            """)
            
            # Step executions
            conn.execute("""
                CREATE TABLE IF NOT EXISTS step_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    input TEXT,
                    output TEXT,
                    error TEXT,
                    retry_count INTEGER DEFAULT 0,
                    started_at REAL,
                    completed_at REAL,
                    duration_ms REAL,
                    UNIQUE(run_id, step_id)
                )
            """)
            
            # Indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_run_status ON workflow_runs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_run_workspace ON workflow_runs(workspace)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_step_run ON step_executions(run_id)")
            
            conn.commit()
    
    def workflow(self, workflow_id: str):
        """Define a new workflow."""
        if workflow_id in self._workflows:
            return self._workflows[workflow_id]
        
        wf_def = WorkflowDefinition(workflow_id, self)
        self._workflows[workflow_id] = wf_def
        return wf_def
    
    async def run(
        self,
        workflow_id: str,
        args: dict = None,
        workspace: str = "nexus_default",
        resume: bool = True
    ) -> dict:
        """
        Run a workflow with checkpoint/resume support.
        
        If resume=True and there's a pending run for this workflow/workspace,
        it will resume from the last completed step.
        """
        if workflow_id not in self._workflows:
            raise ValueError(f"Unknown workflow: {workflow_id}")
        
        args = args or {}
        wf_def = self._workflows[workflow_id]
        
        # Check for existing pending run
        if resume:
            existing_run = self._get_pending_run(workflow_id, workspace)
            if existing_run:
                log.info(f"Resuming workflow {workflow_id} run {existing_run['run_id']}")
                return await self._resume_workflow(existing_run['run_id'], wf_def)
        
        # Create new run
        run_id = str(uuid4())
        log.info(f"Starting new workflow {workflow_id} run {run_id}")
        
        self._create_run(run_id, workflow_id, workspace, args)
        
        try:
            result = await self._execute_workflow(run_id, wf_def, args, workspace)
            self._complete_run(run_id, "completed", result=result)
            return {"status": "completed", "result": result, "run_id": run_id}
        except Exception as e:
            error_msg = str(e)
            log.error(f"Workflow {workflow_id} failed: {error_msg}")
            self._complete_run(run_id, "failed", error=error_msg)
            return {"status": "failed", "error": error_msg, "run_id": run_id}
    
    async def _execute_workflow(
        self,
        run_id: str,
        wf_def: "WorkflowDefinition",
        args: dict,
        workspace: str
    ) -> Any:
        """Execute workflow steps with checkpointing."""
        ctx = WorkflowContext(wf_def.workflow_id, run_id, workspace, args, self)
        
        # Load any previously completed steps
        completed_steps = self._get_completed_steps(run_id)
        for step_id, result_data in completed_steps.items():
            ctx._step_results[step_id] = StepResult(
                output=result_data.get("output"),
                error=result_data.get("error"),
                retry_count=result_data.get("retry_count", 0),
                duration_ms=result_data.get("duration_ms", 0)
            )
        
        # Execute each step
        for step in wf_def.steps:
            # Skip if already completed
            if step.id in ctx._step_results and ctx._step_results[step.id].error is None:
                log.debug(f"Skipping completed step {step.id}")
                continue
            
            ctx._current_step = step.id
            
            # Record step start
            self._start_step(run_id, step.id)
            
            # Execute with retry
            result = await self._execute_step_with_retry(run_id, step, ctx)
            
            # Store result
            ctx._step_results[step.id] = result
            
            if result.error:
                raise Exception(f"Step {step.id} failed: {result.error}")
        
        # Return final result (last step's output or all results)
        if wf_def.steps:
            last_step = wf_def.steps[-1]
            return ctx._step_results[last_step.id].output
        
        return None
    
    async def _resume_workflow(
        self,
        run_id: str,
        wf_def: "WorkflowDefinition"
    ) -> dict:
        """Resume a workflow from checkpoint."""
        # Get run details
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM workflow_runs WHERE run_id = ?",
                (run_id,)
            ).fetchone()
            
            if not row:
                return {"status": "error", "error": f"Run {run_id} not found"}
            
            args = json.loads(row["args"])
            workspace = row["workspace"]
        
        try:
            result = await self._execute_workflow(run_id, wf_def, args, workspace)
            self._complete_run(run_id, "completed", result=result)
            return {"status": "completed", "result": result, "run_id": run_id, "resumed": True}
        except Exception as e:
            error_msg = str(e)
            self._complete_run(run_id, "failed", error=error_msg)
            return {"status": "failed", "error": error_msg, "run_id": run_id}
    
    async def _execute_step_with_retry(
        self,
        run_id: str,
        step: StepDefinition,
        ctx: WorkflowContext
    ) -> StepResult:
        """Execute a step with retry logic."""
        start_time = time.time()
        retry_count = 0
        last_error = None
        
        while retry_count <= step.retries:
            try:
                # Execute step with timeout
                result = await asyncio.wait_for(
                    step.func(ctx),
                    timeout=step.timeout_s
                )
                
                duration_ms = (time.time() - start_time) * 1000
                
                # Record success
                self._complete_step(
                    run_id, step.id,
                    status="completed",
                    output=result,
                    retry_count=retry_count,
                    duration_ms=duration_ms
                )
                
                return StepResult(
                    output=result,
                    retry_count=retry_count,
                    duration_ms=duration_ms
                )
            
            except asyncio.TimeoutError:
                last_error = f"Timeout after {step.timeout_s}s"
                retry_count += 1
                
                if retry_count <= step.retries:
                    # Exponential backoff
                    backoff = step.backoff_base_s * (2 ** (retry_count - 1))
                    log.warning(f"Step {step.id} timeout, retrying in {backoff}s (attempt {retry_count}/{step.retries})")
                    self._update_step_status(run_id, step.id, "retrying", retry_count=retry_count)
                    await asyncio.sleep(backoff)
            
            except Exception as e:
                last_error = str(e)
                retry_count += 1
                
                if retry_count <= step.retries:
                    # Exponential backoff
                    backoff = step.backoff_base_s * (2 ** (retry_count - 1))
                    log.warning(f"Step {step.id} failed: {last_error}, retrying in {backoff}s (attempt {retry_count}/{step.retries})")
                    self._update_step_status(run_id, step.id, "retrying", retry_count=retry_count)
                    await asyncio.sleep(backoff)
        
        # All retries exhausted
        duration_ms = (time.time() - start_time) * 1000
        self._complete_step(
            run_id, step.id,
            status="failed",
            error=last_error,
            retry_count=retry_count,
            duration_ms=duration_ms
        )
        
        return StepResult(
            error=last_error,
            retry_count=retry_count,
            duration_ms=duration_ms
        )
    
    # Database operations
    
    def _create_run(self, run_id: str, workflow_id: str, workspace: str, args: dict):
        """Create a new workflow run record."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO workflow_runs 
                   (run_id, workflow_id, workspace, status, args, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (run_id, workflow_id, workspace, "running", json.dumps(args), time.time(), time.time())
            )
            conn.commit()
    
    def _complete_run(self, run_id: str, status: str, result: Any = None, error: str = None):
        """Mark workflow run as completed."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE workflow_runs 
                   SET status = ?, result = ?, error = ?, completed_at = ?, updated_at = ?
                   WHERE run_id = ?""",
                (status, json.dumps(result) if result else None, error, time.time(), time.time(), run_id)
            )
            conn.commit()
    
    def _start_step(self, run_id: str, step_id: str):
        """Record step start."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO step_executions
                   (run_id, step_id, status, started_at)
                   VALUES (?, ?, ?, ?)""",
                (run_id, step_id, "running", time.time())
            )
            conn.commit()
    
    def _update_step_status(self, run_id: str, step_id: str, status: str, retry_count: int = 0):
        """Update step status."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE step_executions 
                   SET status = ?, retry_count = ?
                   WHERE run_id = ? AND step_id = ?""",
                (status, retry_count, run_id, step_id)
            )
            conn.commit()
    
    def _complete_step(
        self,
        run_id: str,
        step_id: str,
        status: str,
        output: Any = None,
        error: str = None,
        retry_count: int = 0,
        duration_ms: float = 0
    ):
        """Mark step as completed."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE step_executions 
                   SET status = ?, output = ?, error = ?, retry_count = ?, 
                       completed_at = ?, duration_ms = ?
                   WHERE run_id = ? AND step_id = ?""",
                (status, json.dumps(output) if output else None, error, retry_count,
                 time.time(), duration_ms, run_id, step_id)
            )
            conn.commit()
    
    def _get_pending_run(self, workflow_id: str, workspace: str) -> Optional[dict]:
        """Get a pending run for resume."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """SELECT * FROM workflow_runs 
                   WHERE workflow_id = ? AND workspace = ? AND status = 'running'
                   ORDER BY created_at DESC LIMIT 1""",
                (workflow_id, workspace)
            ).fetchone()
            
            return dict(row) if row else None
    
    def _get_completed_steps(self, run_id: str) -> dict[str, dict]:
        """Get completed steps for a run."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT step_id, output, error, retry_count, duration_ms
                   FROM step_executions 
                   WHERE run_id = ? AND status = 'completed'""",
                (run_id,)
            ).fetchall()
            
            return {
                row["step_id"]: {
                    "output": json.loads(row["output"]) if row["output"] else None,
                    "error": row["error"],
                    "retry_count": row["retry_count"],
                    "duration_ms": row["duration_ms"]
                }
                for row in rows
            }
    
    # Query methods for CLI/dashboard
    
    def get_runs(
        self,
        workflow_id: Optional[str] = None,
        workspace: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> list[dict]:
        """Get workflow runs."""
        query = "SELECT * FROM workflow_runs WHERE 1=1"
        params = []
        
        if workflow_id:
            query += " AND workflow_id = ?"
            params.append(workflow_id)
        if workspace:
            query += " AND workspace = ?"
            params.append(workspace)
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            
            runs = []
            for row in rows:
                run = dict(row)
                run["args"] = json.loads(run["args"]) if run["args"] else {}
                run["result"] = json.loads(run["result"]) if run["result"] else None
                runs.append(run)
            
            return runs
    
    def get_run_details(self, run_id: str) -> Optional[dict]:
        """Get detailed information about a run including all steps."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Get run
            run_row = conn.execute(
                "SELECT * FROM workflow_runs WHERE run_id = ?",
                (run_id,)
            ).fetchone()
            
            if not run_row:
                return None
            
            run = dict(run_row)
            run["args"] = json.loads(run["args"]) if run["args"] else {}
            run["result"] = json.loads(run["result"]) if run["result"] else None
            
            # Get steps
            step_rows = conn.execute(
                """SELECT * FROM step_executions WHERE run_id = ? ORDER BY started_at""",
                (run_id,)
            ).fetchall()
            
            run["steps"] = []
            for row in step_rows:
                step = dict(row)
                step["input"] = json.loads(step["input"]) if step["input"] else None
                step["output"] = json.loads(step["output"]) if step["output"] else None
                run["steps"].append(step)
            
            return run
    
    def get_stats(self) -> dict:
        """Get aggregate statistics."""
        with sqlite3.connect(self.db_path) as conn:
            # Total runs
            total = conn.execute("SELECT COUNT(*) FROM workflow_runs").fetchone()[0]
            
            # By status
            status_counts = conn.execute(
                "SELECT status, COUNT(*) FROM workflow_runs GROUP BY status"
            ).fetchall()
            
            # Recent runs (last 24h)
            day_ago = time.time() - 86400
            recent = conn.execute(
                "SELECT COUNT(*) FROM workflow_runs WHERE created_at > ?",
                (day_ago,)
            ).fetchone()[0]
            
            # Average duration for completed runs
            avg_duration = conn.execute(
                """SELECT AVG(completed_at - created_at) 
                   FROM workflow_runs 
                   WHERE status = 'completed' AND completed_at IS NOT NULL"""
            ).fetchone()[0] or 0
            
            return {
                "total_runs": total,
                "recent_runs_24h": recent,
                "status_breakdown": {s: c for s, c in status_counts},
                "avg_duration_seconds": round(avg_duration, 1) if avg_duration else 0
            }


class WorkflowDefinition:
    """Builder for defining a durable workflow."""
    
    def __init__(self, workflow_id: str, engine: DurableWorkflowEngine):
        self.workflow_id = workflow_id
        self.engine = engine
        self.steps: list[StepDefinition] = []
    
    def step(
        self,
        step_id: str,
        name: Optional[str] = None,
        retries: int = 3,
        timeout_s: int = 60,
        backoff_base_s: float = 1.0
    ):
        """Decorator to define a workflow step."""
        def decorator(func: Callable[..., Coroutine[Any, Any, Any]]):
            step_def = StepDefinition(
                id=step_id,
                name=name or step_id,
                func=func,
                retries=retries,
                timeout_s=timeout_s,
                backoff_base_s=backoff_base_s
            )
            self.steps.append(step_def)
            return func
        return decorator


# Global engine instance
_global_engine: Optional[DurableWorkflowEngine] = None


def get_engine() -> DurableWorkflowEngine:
    """Get or create global engine instance."""
    global _global_engine
    if _global_engine is None:
        _global_engine = DurableWorkflowEngine()
    return _global_engine


# Convenience functions

async def run_workflow(
    workflow_id: str,
    args: dict = None,
    workspace: str = "nexus_default",
    resume: bool = True
) -> dict:
    """Run a workflow using the global engine."""
    engine = get_engine()
    return await engine.run(workflow_id, args, workspace, resume)


def get_workflow_runs(**kwargs) -> list[dict]:
    """Get workflow runs."""
    engine = get_engine()
    return engine.get_runs(**kwargs)


def get_run_details(run_id: str) -> Optional[dict]:
    """Get run details."""
    engine = get_engine()
    return engine.get_run_details(run_id)


def get_workflow_stats() -> dict:
    """Get workflow statistics."""
    engine = get_engine()
    return engine.get_stats()
