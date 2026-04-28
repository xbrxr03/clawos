# SPDX-License-Identifier: AGPL-3.0-or-later
"""
clawctl observ — Observability and Tracing
===========================================
View LLM call traces, token usage, costs, and performance metrics.

Usage:
  clawctl observ status      Check observability service status
  clawctl observ calls      Show recent LLM calls
  clawctl observ stats      Show aggregate statistics
  clawctl observ cost       Show cost breakdown
  clawctl observ latency    Show latency analysis
  clawctl observ export     Export data to CSV/JSON

Addresses the observability gap from CRITICAL_GAPS_RESEARCH.md
"""
import json
import urllib.request
from datetime import datetime, timedelta
from typing import Optional

import click

from clawos_core.constants import PORT_OBSERVD

API_BASE = f"http://127.0.0.1:{PORT_OBSERVD}/api/v1"
HEALTH_ENDPOINT = f"http://127.0.0.1:{PORT_OBSERVD}/health"


def _is_running() -> bool:
    """Check if observability service is running."""
    try:
        req = urllib.request.Request(HEALTH_ENDPOINT, method="GET", timeout=2)
        with urllib.request.urlopen(req) as resp:
            return resp.status == 200
    except:
        return False


def _api_get(endpoint: str, params: dict = None) -> dict:
    """Make GET request to observability API."""
    url = f"{API_BASE}{endpoint}"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
        if query:
            url += f"?{query}"
    
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


@click.group(name="observ", help="Observability and tracing for LLM calls")
def observ_group():
    """View LLM call traces, costs, and performance metrics."""
    pass


@observ_group.command(name="status", help="Check observability service status")
def observ_status():
    """Check if observability service is running."""
    if _is_running():
        click.echo("✓ Observability service is running on port 7078")
        click.echo("  Tracing LLM calls, costs, and latency")
    else:
        click.echo("✗ Observability service is not running")
        click.echo("  Start with: python3 -m services.observd.main")


@observ_group.command(name="calls", help="Show recent LLM calls")
@click.option("--workspace", "-w", help="Filter by workspace")
@click.option("--service", "-s", help="Filter by service (nexus, agentd, etc.)")
@click.option("--model", "-m", help="Filter by model name")
@click.option("--hours", "-h", default=24, help="Time window in hours (default: 24)")
@click.option("--limit", "-l", default=20, help="Number of calls to show (default: 20)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def observ_calls(workspace, service, model, hours, limit, as_json):
    """Show recent LLM calls with filtering."""
    if not _is_running():
        click.echo("✗ Observability service is not running")
        return
    
    try:
        params = {
            "hours": hours,
            "limit": limit
        }
        if workspace:
            params["workspace"] = workspace
        if service:
            params["service"] = service
        if model:
            params["model"] = model
        
        data = _api_get("/calls", params)
        calls = data.get("calls", [])
        
        if as_json:
            click.echo(json.dumps(calls, indent=2))
            return
        
        if not calls:
            click.echo(f"No calls found in the last {hours} hours")
            return
        
        click.echo(f"\nRecent LLM Calls ({len(calls)} in last {hours}h):\n")
        click.echo(f"{'Time':<20} {'Service':<12} {'Model':<25} {'Tokens':<10} {'Latency':<10} {'Status'}")
        click.echo("-" * 100)
        
        for call in calls:
            ts = datetime.fromtimestamp(call.get("timestamp", 0))
            time_str = ts.strftime("%Y-%m-%d %H:%M:%S")
            service_name = call.get("service", "unknown")[:11]
            model_name = call.get("model", "unknown")[:24]
            tokens = call.get("total_tokens", 0)
            latency = f"{call.get('latency_ms', 0):.0f}ms"
            status = call.get("status", "unknown")
            
            status_icon = "✓" if status == "success" else "✗" if status == "error" else "○"
            
            click.echo(f"{time_str:<20} {service_name:<12} {model_name:<25} {tokens:<10} {latency:<10} {status_icon} {status}")
        
    except Exception as e:
        click.echo(f"✗ Error fetching calls: {e}")


@observ_group.command(name="stats", help="Show aggregate statistics")
@click.option("--workspace", "-w", help="Filter by workspace")
@click.option("--hours", "-h", default=24, help="Time window in hours (default: 24)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def observ_stats(workspace, hours, as_json):
    """Show aggregate statistics for LLM calls."""
    if not _is_running():
        click.echo("✗ Observability service is not running")
        return
    
    try:
        params = {"hours": hours}
        if workspace:
            params["workspace"] = workspace
        
        stats = _api_get("/stats", params)
        
        if as_json:
            click.echo(json.dumps(stats, indent=2))
            return
        
        click.echo(f"\n{'Workspace: ' + workspace if workspace else 'All Workspaces'} (last {hours}h)\n")
        
        # Summary
        click.echo("Summary:")
        click.echo(f"  Total calls:     {stats.get('total_calls', 0):,}")
        click.echo(f"  Success rate:    {stats.get('success_rate', 0):.1f}%")
        click.echo(f"  Total tokens:    {stats.get('total_tokens', 0):,}")
        click.echo(f"  Prompt tokens:   {stats.get('prompt_tokens', 0):,}")
        click.echo(f"  Completion:      {stats.get('completion_tokens', 0):,}")
        
        # Cost
        cost = stats.get('estimated_cost_usd', 0)
        if cost > 0:
            click.echo(f"  Est. cost:       ${cost:.4f}")
        else:
            click.echo(f"  Est. cost:       $0.00 (local/ollama)")
        
        # Latency
        click.echo(f"\nLatency:")
        click.echo(f"  Average:         {stats.get('avg_latency_ms', 0):.0f}ms")
        click.echo(f"  Min:             {stats.get('min_latency_ms', 0):.0f}ms")
        click.echo(f"  Max:             {stats.get('max_latency_ms', 0):.0f}ms")
        
        # Top models
        top_models = stats.get('top_models', [])
        if top_models:
            click.echo(f"\nTop Models:")
            for m in top_models:
                click.echo(f"  {m['model'][:30]:<32} {m['count']:>6} calls")
        
        # Top services
        top_services = stats.get('top_services', [])
        if top_services:
            click.echo(f"\nTop Services:")
            for s in top_services:
                click.echo(f"  {s['service'][:30]:<32} {s['count']:>6} calls")
        
    except Exception as e:
        click.echo(f"✗ Error fetching stats: {e}")


@observ_group.command(name="cost", help="Show cost breakdown")
@click.option("--workspace", "-w", help="Filter by workspace")
@click.option("--days", "-d", default=7, help="Time window in days (default: 7)")
def observ_cost(workspace, days):
    """Show cost breakdown over time."""
    if not _is_running():
        click.echo("✗ Observability service is not running")
        return
    
    try:
        hours = days * 24
        params = {"hours": hours}
        if workspace:
            params["workspace"] = workspace
        
        stats = _api_get("/stats", params)
        
        click.echo(f"\nCost Analysis (last {days} days)\n")
        
        total_cost = stats.get('estimated_cost_usd', 0)
        total_calls = stats.get('total_calls', 0)
        total_tokens = stats.get('total_tokens', 0)
        
        if total_calls == 0:
            click.echo("No calls recorded in this period.")
            return
        
        click.echo(f"Total cost:        ${total_cost:.4f}")
        click.echo(f"Total calls:       {total_calls:,}")
        click.echo(f"Total tokens:      {total_tokens:,}")
        click.echo(f"Cost per call:     ${total_cost / total_calls:.4f}")
        click.echo(f"Cost per 1K tokens: ${(total_cost / total_tokens * 1000) if total_tokens > 0 else 0:.4f}")
        
        # Daily breakdown
        series = _api_get("/timeseries", {**params, "interval": "day"})
        data = series.get("data", [])
        
        if data:
            click.echo(f"\nDaily breakdown:")
            click.echo(f"{'Date':<15} {'Calls':>8} {'Tokens':>12} {'Cost':>10}")
            click.echo("-" * 50)
            for day in data:
                date = day.get('time', 'unknown')[:10]
                calls = day.get('calls', 0)
                tokens = day.get('tokens', 0)
                cost = day.get('cost_usd', 0)
                click.echo(f"{date:<15} {calls:>8} {tokens:>12,} ${cost:>9.4f}")
        
    except Exception as e:
        click.echo(f"✗ Error fetching cost data: {e}")


@observ_group.command(name="latency", help="Show latency analysis")
@click.option("--workspace", "-w", help="Filter by workspace")
@click.option("--hours", "-h", default=24, help="Time window in hours (default: 24)")
def observ_latency(workspace, hours):
    """Show latency analysis over time."""
    if not _is_running():
        click.echo("✗ Observability service is not running")
        return
    
    try:
        params = {"hours": hours}
        if workspace:
            params["workspace"] = workspace
        
        # Get time series data
        series = _api_get("/timeseries", {**params, "interval": "hour"})
        data = series.get("data", [])
        
        if not data:
            click.echo(f"No data available for the last {hours} hours")
            return
        
        click.echo(f"\nLatency Analysis (last {hours} hours)\n")
        click.echo(f"{'Time':<20} {'Calls':>8} {'Avg Latency':>15}")
        click.echo("-" * 50)
        
        for hour in data:
            time_str = hour.get('time', 'unknown')[:16]
            calls = hour.get('calls', 0)
            latency = hour.get('avg_latency_ms', 0)
            click.echo(f"{time_str:<20} {calls:>8} {latency:>13.0f}ms")
        
        # Overall stats
        stats = _api_get("/stats", params)
        click.echo(f"\nOverall:")
        click.echo(f"  Average: {stats.get('avg_latency_ms', 0):.0f}ms")
        click.echo(f"  Min:     {stats.get('min_latency_ms', 0):.0f}ms")
        click.echo(f"  Max:     {stats.get('max_latency_ms', 0):.0f}ms")
        
    except Exception as e:
        click.echo(f"✗ Error fetching latency data: {e}")


@observ_group.command(name="workspaces", help="List workspaces with activity")
def observ_workspaces():
    """Show all workspaces and their activity."""
    if not _is_running():
        click.echo("✗ Observability service is not running")
        return
    
    try:
        data = _api_get("/workspaces")
        workspaces = data.get("workspaces", [])
        
        if not workspaces:
            click.echo("No workspaces found with activity")
            return
        
        click.echo(f"\nWorkspaces ({len(workspaces)} total):\n")
        click.echo(f"{'Name':<30} {'Calls':>10} {'Last Activity'}")
        click.echo("-" * 70)
        
        for ws in workspaces:
            name = ws.get('name', 'unknown')[:28]
            calls = ws.get('total_calls', 0)
            last = ws.get('last_activity', 'never')
            if last and last != 'never':
                # Format timestamp
                try:
                    dt = datetime.fromisoformat(last.replace('Z', '+00:00'))
                    last = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    pass
            click.echo(f"{name:<30} {calls:>10} {last}")
        
    except Exception as e:
        click.echo(f"✗ Error fetching workspaces: {e}")


@observ_group.command(name="export", help="Export observability data")
@click.option("--format", "fmt", type=click.Choice(["json", "csv"]), default="json", help="Export format")
@click.option("--output", "-o", help="Output file (default: stdout)")
@click.option("--hours", "-h", default=168, help="Time window in hours (default: 168 = 7 days)")
@click.option("--workspace", "-w", help="Filter by workspace")
def observ_export(fmt, output, hours, workspace):
    """Export observability data to file."""
    if not _is_running():
        click.echo("✗ Observability service is not running")
        return
    
    try:
        params = {"hours": hours, "limit": 10000}
        if workspace:
            params["workspace"] = workspace
        
        data = _api_get("/calls", params)
        calls = data.get("calls", [])
        
        if fmt == "json":
            content = json.dumps(calls, indent=2)
        else:  # CSV
            import csv
            import io
            
            output_buffer = io.StringIO()
            if calls:
                writer = csv.DictWriter(
                    output_buffer,
                    fieldnames=["timestamp", "workspace", "service", "provider", "model",
                               "prompt_tokens", "completion_tokens", "total_tokens",
                               "latency_ms", "cost_usd", "status"]
                )
                writer.writeheader()
                for call in calls:
                    writer.writerow({
                        "timestamp": datetime.fromtimestamp(call.get("timestamp", 0)).isoformat(),
                        "workspace": call.get("workspace", ""),
                        "service": call.get("service", ""),
                        "provider": call.get("provider", ""),
                        "model": call.get("model", ""),
                        "prompt_tokens": call.get("prompt_tokens", 0),
                        "completion_tokens": call.get("completion_tokens", 0),
                        "total_tokens": call.get("total_tokens", 0),
                        "latency_ms": call.get("latency_ms", 0),
                        "cost_usd": call.get("cost_usd", 0),
                        "status": call.get("status", "")
                    })
            content = output_buffer.getvalue()
        
        if output:
            with open(output, 'w') as f:
                f.write(content)
            click.echo(f"✓ Exported {len(calls)} calls to {output}")
        else:
            click.echo(content)
        
    except Exception as e:
        click.echo(f"✗ Error exporting data: {e}")
