# SPDX-License-Identifier: AGPL-3.0-or-later
"""
clawctl durable — Durable Workflow Management
==============================================
Manage durable workflows with checkpoint/resume capability.

Usage:
  clawctl durable runs              List workflow runs
  clawctl durable show <run_id>     Show run details
  clawctl durable resume <run_id>   Resume a failed/pending run
  clawctl durable cancel <run_id>   Cancel a running run
  clawctl durable stats             Show workflow statistics

Addresses the durable execution gap from CRITICAL_GAPS_RESEARCH.md
"""
import json
from datetime import datetime
from typing import Optional

import click

from workflows.durable_engine import get_engine, get_workflow_runs, get_run_details, get_workflow_stats


@click.group(name="durable", help="Durable workflow management (checkpoint/resume)")
def durable_group():
    """Manage durable workflows with checkpoint/resume."""
    pass


@durable_group.command(name="runs", help="List workflow runs")
@click.option("--workflow", "-w", help="Filter by workflow ID")
@click.option("--status", "-s", type=click.Choice(["pending", "running", "completed", "failed", "cancelled"]), help="Filter by status")
@click.option("--limit", "-l", default=20, help="Number of runs to show (default: 20)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def durable_runs(workflow, status, limit, as_json):
    """List workflow runs with status."""
    try:
        runs = get_workflow_runs(
            workflow_id=workflow,
            status=status,
            limit=limit
        )
        
        if as_json:
            click.echo(json.dumps(runs, indent=2))
            return
        
        if not runs:
            click.echo("No workflow runs found")
            return
        
        click.echo(f"\nWorkflow Runs ({len(runs)} total):\n")
        click.echo(f"{'Run ID':<36} {'Workflow':<25} {'Status':<12} {'Created':<20} {'Duration'}")
        click.echo("-" * 120)
        
        for run in runs:
            run_id = run['run_id'][:35]
            wf_id = run['workflow_id'][:24]
            status = run['status']
            
            # Status icon
            icon = "✓" if status == "completed" else "✗" if status == "failed" else "○" if status == "running" else "⊘"
            
            # Format time
            created = datetime.fromtimestamp(run['created_at'])
            time_str = created.strftime("%Y-%m-%d %H:%M:%S")
            
            # Duration
            if run.get('completed_at'):
                duration = run['completed_at'] - run['created_at']
                duration_str = f"{duration:.1f}s"
            elif status == "running":
                duration = datetime.now().timestamp() - run['created_at']
                duration_str = f"{duration:.1f}s (running)"
            else:
                duration_str = "-"
            
            click.echo(f"{run_id:<36} {wf_id:<25} {icon} {status:<10} {time_str:<20} {duration_str}")
        
    except (TypeError, ValueError) as e:
        click.echo(f"✗ Error listing runs: {e}")


@durable_group.command(name="show", help="Show run details")
@click.argument("run_id")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def durable_show(run_id, as_json):
    """Show detailed information about a workflow run."""
    try:
        run = get_run_details(run_id)
        
        if not run:
            click.echo(f"✗ Run not found: {run_id}")
            return
        
        if as_json:
            click.echo(json.dumps(run, indent=2, default=str))
            return
        
        click.echo(f"\nWorkflow Run Details\n")
        click.echo(f"Run ID:       {run['run_id']}")
        click.echo(f"Workflow:     {run['workflow_id']}")
        click.echo(f"Workspace:    {run['workspace']}")
        click.echo(f"Status:       {run['status']}")
        click.echo(f"Created:      {datetime.fromtimestamp(run['created_at']).strftime('%Y-%m-%d %H:%M:%S')}")
        
        if run.get('completed_at'):
            completed = datetime.fromtimestamp(run['completed_at'])
            click.echo(f"Completed:    {completed.strftime('%Y-%m-%d %H:%M:%S')}")
            duration = run['completed_at'] - run['created_at']
            click.echo(f"Duration:     {duration:.1f}s")
        
        # Args
        if run.get('args'):
            click.echo(f"\nArguments:")
            for key, value in run['args'].items():
                click.echo(f"  {key}: {value}")
        
        # Result
        if run.get('result'):
            click.echo(f"\nResult:")
            click.echo(f"  {json.dumps(run['result'], indent=2)[:500]}")
        
        # Error
        if run.get('error'):
            click.echo(f"\nError:")
            click.echo(f"  {run['error']}")
        
        # Steps
        steps = run.get('steps', [])
        if steps:
            click.echo(f"\nSteps ({len(steps)} total):")
            click.echo(f"{'Step ID':<20} {'Status':<12} {'Retries':<8} {'Duration':<12} {'Error'}")
            click.echo("-" * 80)
            
            for step in steps:
                step_id = step['step_id'][:19]
                status = step['status']
                retries = step.get('retry_count', 0)
                duration = f"{step.get('duration_ms', 0):.0f}ms" if step.get('duration_ms') else "-"
                error = step.get('error', "")[:30]
                
                icon = "✓" if status == "completed" else "✗" if status == "failed" else "○"
                
                click.echo(f"{step_id:<20} {icon} {status:<10} {retries:<8} {duration:<12} {error}")
        
    except (TypeError, ValueError) as e:
        click.echo(f"✗ Error showing run: {e}")


@durable_group.command(name="resume", help="Resume a workflow run")
@click.argument("run_id")
def durable_resume(run_id):
    """Resume a failed or pending workflow run from last checkpoint."""
    import asyncio
    
    try:
        run = get_run_details(run_id)
        
        if not run:
            click.echo(f"✗ Run not found: {run_id}")
            return
        
        if run['status'] not in ['failed', 'running']:
            click.echo(f"✗ Cannot resume run with status '{run['status']}'")
            click.echo(f"  Only 'failed' or 'running' runs can be resumed")
            return
        
        workflow_id = run['workflow_id']
        
        click.echo(f"Resuming workflow '{workflow_id}' run {run_id[:8]}...")
        
        # Resume via engine
        engine = get_engine()
        
        # Get the workflow definition
        if workflow_id not in engine._workflows:
            click.echo(f"✗ Workflow '{workflow_id}' not found in registry")
            click.echo(f"  Make sure the workflow is registered before resuming")
            return
        
        wf_def = engine._workflows[workflow_id]
        
        # Run the resume
        result = asyncio.run(engine._resume_workflow(run_id, wf_def))
        
        if result['status'] == 'completed':
            click.echo(f"✓ Workflow completed successfully")
        else:
            click.echo(f"✗ Workflow failed: {result.get('error', 'Unknown error')}")
        
    except (RuntimeError, OSError, TypeError) as e:
        click.echo(f"✗ Error resuming run: {e}")


@durable_group.command(name="cancel", help="Cancel a running workflow")
@click.argument("run_id")
def durable_cancel(run_id):
    """Cancel a running workflow run."""
    try:
        run = get_run_details(run_id)
        
        if not run:
            click.echo(f"✗ Run not found: {run_id}")
            return
        
        if run['status'] != 'running':
            click.echo(f"✗ Run is not running (status: {run['status']})")
            return
        
        # Update status to cancelled
        import sqlite3
        from workflows.durable_engine import DURABLE_DB_PATH
        
        with sqlite3.connect(DURABLE_DB_PATH) as conn:
            conn.execute(
                "UPDATE workflow_runs SET status = ?, completed_at = ? WHERE run_id = ?",
                ('cancelled', datetime.now().timestamp(), run_id)
            )
            conn.commit()
        
        click.echo(f"✓ Workflow run {run_id[:8]}... cancelled")
        
    except (sqlite3.Error, OSError) as e:
        click.echo(f"✗ Error cancelling run: {e}")


@durable_group.command(name="stats", help="Show workflow statistics")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def durable_stats(as_json):
    """Show aggregate workflow statistics."""
    try:
        stats = get_workflow_stats()
        
        if as_json:
            click.echo(json.dumps(stats, indent=2))
            return
        
        click.echo(f"\nWorkflow Statistics\n")
        click.echo(f"Total runs:           {stats['total_runs']:,}")
        click.echo(f"Runs (last 24h):      {stats['recent_runs_24h']:,}")
        click.echo(f"Avg duration:         {stats['avg_duration_seconds']:.1f}s")
        
        if stats.get('status_breakdown'):
            click.echo(f"\nStatus breakdown:")
            for status, count in stats['status_breakdown'].items():
                icon = "✓" if status == "completed" else "✗" if status == "failed" else "○"
                pct = (count / stats['total_runs'] * 100) if stats['total_runs'] > 0 else 0
                click.echo(f"  {icon} {status:<12} {count:>6} ({pct:.1f}%)")
        
    except (TypeError, ValueError) as e:
        click.echo(f"✗ Error getting stats: {e}")


@durable_group.command(name="cleanup", help="Clean up old workflow runs")
@click.option("--days", "-d", default=30, help="Delete runs older than N days (default: 30)")
@click.option("--yes", is_flag=True, help="Skip confirmation")
def durable_cleanup(days, yes):
    """Delete old workflow runs and their step records."""
    import sqlite3
    from workflows.durable_engine import DURABLE_DB_PATH
    
    try:
        cutoff = datetime.now().timestamp() - (days * 86400)
        
        if not yes:
            click.confirm(f"Delete all workflow runs older than {days} days?", abort=True)
        
        with sqlite3.connect(DURABLE_DB_PATH) as conn:
            # Get count first
            cursor = conn.execute(
                "SELECT COUNT(*) FROM workflow_runs WHERE created_at < ?",
                (cutoff,)
            )
            count = cursor.fetchone()[0]
            
            # Delete step executions first (foreign key constraint)
            conn.execute(
                """DELETE FROM step_executions 
                   WHERE run_id IN (SELECT run_id FROM workflow_runs WHERE created_at < ?)""",
                (cutoff,)
            )
            
            # Delete runs
            conn.execute(
                "DELETE FROM workflow_runs WHERE created_at < ?",
                (cutoff,)
            )
            
            conn.commit()
        
        click.echo(f"✓ Deleted {count} old workflow runs")
        
    except (sqlite3.Error, OSError) as e:
        click.echo(f"✗ Error cleaning up: {e}")
