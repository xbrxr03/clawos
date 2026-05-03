# SPDX-License-Identifier: AGPL-3.0-or-later
"""
clawctl code — Code Companion Commands
======================================
Developer-focused AI assistant with code understanding.

Usage:
  clawctl code index <path>          Index a codebase
  clawctl code search <query>        Search codebase
  clawctl code explain <file>:<line>  Explain code at location
  clawctl code review <file>          Review code for issues
  clawctl code test <function>       Generate tests

Addresses the local coding agent gap from CRITICAL_GAPS_RESEARCH.md
"""
import asyncio
import json
from pathlib import Path
from typing import Optional

import click

from skills.code_companion.main import create_companion, index_project


@click.group(name="code", help="Code companion - developer AI assistant")
def code_group():
    """Developer-focused AI assistant with code understanding."""
    pass


@code_group.command(name="index", help="Index a codebase for search")
@click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option("--workspace", "-w", default="code_default", help="Workspace name")
@click.option("--verbose", "-v", is_flag=True, help="Show progress")
def code_index(path, workspace, verbose):
    """Index a codebase for semantic search."""
    try:
        click.echo(f"Indexing codebase: {path}")
        click.echo(f"Workspace: {workspace}")
        
        def progress_callback(indexed, total, current_file):
            if verbose and indexed % 10 == 0:
                pct = (indexed / total * 100) if total > 0 else 0
                click.echo(f"  [{pct:.0f}%] {indexed}/{total} files - {current_file[:60]}")
        
        indexed = asyncio.run(index_project(path, workspace, progress_callback))
        
        click.echo(f"✓ Indexed {indexed} files")
        click.echo(f"  Search with: clawctl code search '<query>' --workspace {workspace}")
        
    except (OSError, RuntimeError, AttributeError) as e:
        click.echo(f"✗ Error indexing: {e}")


@code_group.command(name="search", help="Search indexed codebase")
@click.argument("query")
@click.option("--workspace", "-w", default="code_default", help="Workspace name")
@click.option("--limit", "-l", default=10, help="Number of results")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def code_search(query, workspace, limit, as_json):
    """Search codebase using semantic search."""
    try:
        from skills.code_companion.main import CodebaseIndex
        
        # Create index (will use existing if available)
        index = CodebaseIndex(Path("."), workspace)
        
        results = index.search(query, limit)
        
        if as_json:
            click.echo(json.dumps(results, indent=2))
            return
        
        if not results:
            click.echo("No results found. Try indexing first: clawctl code index <path>")
            return
        
        click.echo(f"\nSearch results for: '{query}'\n")
        
        for i, result in enumerate(results, 1):
            result_type = result.get('type', 'unknown')
            
            if result_type == 'file':
                path = result.get('path', 'unknown')
                metadata = result.get('metadata', {})
                click.echo(f"{i}. 📄 {path}")
                click.echo(f"   Language: {metadata.get('language', 'unknown')}, " +
                          f"Lines: {metadata.get('line_count', 0)}")
            
            elif result_type == 'symbol':
                name = result.get('name', 'unknown')
                kind = result.get('kind', 'unknown')
                path = result.get('path', 'unknown')
                click.echo(f"{i}. 🔧 {name} ({kind})")
                click.echo(f"   {path}")
            
            click.echo("")
        
    except (TypeError, ValueError) as e:
        click.echo(f"✗ Error searching: {e}")


@code_group.command(name="explain", help="Explain code at location")
@click.argument("location")  # format: path/to/file.py:line
@click.option("--workspace", "-w", default="code_default", help="Workspace name")
def code_explain(location, workspace):
    """Explain code at a specific location (file:line)."""
    try:
        # Parse location
        if ":" not in location:
            click.echo("✗ Location must be in format: path/to/file.py:line")
            return
        
        file_path, line_str = location.rsplit(":", 1)
        try:
            line = int(line_str)
        except ValueError:
            click.echo(f"✗ Invalid line number: {line_str}")
            return
        
        from skills.code_companion.main import create_companion
        
        companion = create_companion(".", workspace)
        explanation = companion.explain_symbol(file_path, line)
        
        click.echo(explanation)
        
    except (ValueError, OSError, AttributeError) as e:
        click.echo(f"✗ Error explaining: {e}")


@code_group.command(name="review", help="Review code for issues")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def code_review(file_path, as_json):
    """Review code for style issues, TODOs, and potential bugs."""
    try:
        from skills.code_companion.main import create_companion
        
        companion = create_companion(".")
        
        # Read file
        content = Path(file_path).read_text(encoding='utf-8', errors='ignore')
        
        suggestions = companion.suggest_refactoring(file_path, content)
        
        if as_json:
            click.echo(json.dumps(suggestions, indent=2))
            return
        
        if not suggestions:
            click.echo(f"✓ No issues found in {file_path}")
            return
        
        click.echo(f"\nReview results for {file_path}:\n")
        click.echo(f"Found {len(suggestions)} suggestions:\n")
        
        for s in suggestions:
            icon = "⚠️" if s['type'] == 'error' else "💡" if s['type'] == 'style' else "📝"
            click.echo(f"{icon} Line {s['line']} ({s['type']})")
            click.echo(f"   {s['message']}")
            click.echo("")
        
    except (TypeError, ValueError) as e:
        click.echo(f"✗ Error reviewing: {e}")


@code_group.command(name="test", help="Generate test cases")
@click.argument("symbol")
@click.option("--file", "-f", required=True, help="File containing the symbol")
@click.option("--workspace", "-w", default="code_default", help="Workspace name")
def code_test(symbol, file, workspace):
    """Generate test cases for a function or class."""
    try:
        from skills.code_companion.main import create_companion
        
        companion = create_companion(".", workspace)
        tests = companion.generate_tests(symbol, file)
        
        click.echo(f"Generated tests for {symbol}:\n")
        click.echo("```python")
        click.echo(tests)
        click.echo("```")
        
    except (ImportError, ModuleNotFoundError) as e:
        click.echo(f"✗ Error generating tests: {e}")


@code_group.command(name="status", help="Show code companion status")
@click.option("--workspace", "-w", default="code_default", help="Workspace name")
def code_status(workspace):
    """Show code companion status and index statistics."""
    try:
        from skills.code_companion.main import CodebaseIndex
        
        index = CodebaseIndex(Path("."), workspace)
        
        # Get collection stats
        try:
            files_count = index.files_collection.count()
            symbols_count = index.symbols_collection.count()
            
            click.echo(f"\nCode Companion Status\n")
            click.echo(f"Workspace: {workspace}")
            click.echo(f"Indexed files: {files_count}")
            click.echo(f"Indexed symbols: {symbols_count}")
            
            if files_count > 0:
                click.echo(f"\n✓ Index is ready for search")
                click.echo(f"  Use: clawctl code search '<query>'")
            else:
                click.echo(f"\n⚠ No files indexed")
                click.echo(f"  Run: clawctl code index <path>")
        
        except (ImportError, ModuleNotFoundError) as e:
            click.echo(f"✗ Error getting status: {e}")
        
    except (OSError, ValueError) as e:
        click.echo(f"✗ Error: {e}")
