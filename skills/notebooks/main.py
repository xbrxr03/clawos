# SPDX-License-Identifier: AGPL-3.0-or-later
"""
DevOps Notebooks Skill
=======================
Executable markdown documentation like Jupyter but for DevOps.

Features:
- Execute markdown code blocks
- Variable passing between cells
- Multiple languages (bash, python, etc.)
- Output capture and display
- Session persistence
- Export to standalone scripts

Addresses Gap #13: DevOps Notebooks from CRITICAL_GAPS_RESEARCH.md

Example notebook:
```markdown
# Server Setup

## Check disk space
```bash
```
df -h
```

## Install packages
```bash
```
apt-get update
apt-get install -y nginx
```

## Configure
```python
```
# Python cell
import json
config = {"port": 80}
print(json.dumps(config))
```
```
"""
import re
import json
import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

log = logging.getLogger("notebooks")


class CellType(Enum):
    MARKDOWN = "markdown"
    CODE = "code"


class CodeLanguage(Enum):
    BASH = "bash"
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    RUBY = "ruby"
    GO = "go"
    RUST = "rust"
    SQL = "sql"


@dataclass
class Cell:
    """A notebook cell."""
    id: str
    cell_type: CellType
    content: str
    language: Optional[CodeLanguage] = None
    outputs: List[Dict] = field(default_factory=list)
    execution_count: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NotebookSession:
    """Notebook execution session."""
    variables: Dict[str, Any] = field(default_factory=dict)
    execution_history: List[Dict] = field(default_factory=list)
    working_dir: Path = field(default_factory=Path.cwd)


class NotebookParser:
    """Parse markdown into executable cells."""
    
    CODE_BLOCK_PATTERN = re.compile(
        r'```(\w+)?\s*\n(.*?)```',
        re.DOTALL
    )
    
    VARIABLE_PATTERN = re.compile(r'\$\{(\w+)\}')
    
    def parse(self, markdown: str) -> List[Cell]:
        """Parse markdown into cells."""
        cells = []
        cell_id = 0
        
        # Split by code blocks
        parts = self.CODE_BLOCK_PATTERN.split(markdown)
        
        # parts will be: [text_before, lang, code, text_after, lang, code, ...]
        i = 0
        while i < len(parts):
            if i == 0:
                # First text part (before any code block)
                text = parts[i].strip()
                if text:
                    cells.append(Cell(
                        id=f"cell_{cell_id}",
                        cell_type=CellType.MARKDOWN,
                        content=text
                    ))
                    cell_id += 1
                i += 1
            elif i + 2 <= len(parts):
                # Code block
                lang_str = parts[i] if parts[i] else "bash"
                code = parts[i + 1].strip()
                
                language = self._parse_language(lang_str)
                
                cells.append(Cell(
                    id=f"cell_{cell_id}",
                    cell_type=CellType.CODE,
                    content=code,
                    language=language
                ))
                cell_id += 1
                
                # Text after code block
                if i + 2 < len(parts):
                    text = parts[i + 2].strip()
                    if text:
                        cells.append(Cell(
                            id=f"cell_{cell_id}",
                            cell_type=CellType.MARKDOWN,
                            content=text
                        ))
                        cell_id += 1
                
                i += 3
            else:
                break
        
        return cells
    
    def _parse_language(self, lang_str: str) -> Optional[CodeLanguage]:
        """Parse language string."""
        lang_map = {
            'bash': CodeLanguage.BASH,
            'sh': CodeLanguage.BASH,
            'shell': CodeLanguage.BASH,
            'python': CodeLanguage.PYTHON,
            'py': CodeLanguage.PYTHON,
            'python3': CodeLanguage.PYTHON,
            'javascript': CodeLanguage.JAVASCRIPT,
            'js': CodeLanguage.JAVASCRIPT,
            'typescript': CodeLanguage.TYPESCRIPT,
            'ts': CodeLanguage.TYPESCRIPT,
            'ruby': CodeLanguage.RUBY,
            'rb': CodeLanguage.RUBY,
            'go': CodeLanguage.GO,
            'golang': CodeLanguage.GO,
            'rust': CodeLanguage.RUST,
            'rs': CodeLanguage.RUST,
            'sql': CodeLanguage.SQL,
        }
        
        return lang_map.get(lang_str.lower())


class NotebookExecutor:
    """Execute notebook cells."""
    
    def __init__(self, session: Optional[NotebookSession] = None):
        self.session = session or NotebookSession()
        self.execution_count = 0
    
    def execute_cell(self, cell: Cell) -> Cell:
        """Execute a single cell."""
        if cell.cell_type != CellType.CODE:
            return cell
        
        self.execution_count += 1
        cell.execution_count = self.execution_count
        
        # Substitute variables
        code = self._substitute_variables(cell.content)
        
        # Execute based on language
        if cell.language == CodeLanguage.BASH:
            result = self._execute_bash(code)
        elif cell.language == CodeLanguage.PYTHON:
            result = self._execute_python(code)
        elif cell.language in [CodeLanguage.JAVASCRIPT, CodeLanguage.TYPESCRIPT]:
            result = self._execute_node(code)
        elif cell.language == CodeLanguage.SQL:
            result = self._execute_sql(code)
        else:
            result = {
                "success": False,
                "output": "",
                "error": f"Language {cell.language} not supported yet"
            }
        
        cell.outputs.append(result)
        
        # Record execution
        self.session.execution_history.append({
            "cell_id": cell.id,
            "language": cell.language.value if cell.language else None,
            "success": result["success"],
            "timestamp": result.get("timestamp")
        })
        
        return cell
    
    def _substitute_variables(self, code: str) -> str:
        """Substitute ${variable} with values from session."""
        def replace_var(match):
            var_name = match.group(1)
            value = self.session.variables.get(var_name, match.group(0))
            return str(value)
        
        return NotebookParser.VARIABLE_PATTERN.sub(replace_var, code)
    
    def _execute_bash(self, code: str) -> Dict:
        """Execute bash code."""
        try:
            result = subprocess.run(
                ["bash", "-c", code],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.session.working_dir)
            )
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else "",
                "exit_code": result.returncode,
                "timestamp": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": "Execution timeout (30s)",
                "exit_code": -1
            }
        except (OSError, subprocess.SubprocessError) as e:
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "exit_code": -1
            }
    
    def _execute_python(self, code: str) -> Dict:
        """Execute Python code."""
        import sys
        from io import StringIO
        
        # Capture stdout/stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = StringIO()
        sys.stderr = StringIO()
        
        try:
            # Execute with session variables
            exec_globals = self.session.variables.copy()
            exec_globals['__name__'] = '__notebook__'
            
            exec(code, exec_globals)
            
            # Update session variables
            for key, value in exec_globals.items():
                if not key.startswith('_'):
                    self.session.variables[key] = value
            
            output = sys.stdout.getvalue()
            error = sys.stderr.getvalue()
            
            return {
                "success": True,
                "output": output,
                "error": error,
                "exit_code": 0
            }
        
        except (OSError, RuntimeError, TimeoutError) as e:
            return {
                "success": False,
                "output": sys.stdout.getvalue(),
                "error": f"{type(e).__name__}: {str(e)}",
                "exit_code": 1
            }
        
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
    
    def _execute_node(self, code: str) -> Dict:
        """Execute Node.js code."""
        try:
            result = subprocess.run(
                ["node", "-e", code],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else "",
                "exit_code": result.returncode
            }
        except FileNotFoundError:
            return {
                "success": False,
                "output": "",
                "error": "Node.js not installed",
                "exit_code": -1
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": "Execution timeout (30s)",
                "exit_code": -1
            }
    
    def _execute_sql(self, code: str) -> Dict:
        """Execute SQL (placeholder - would need DB connection)."""
        return {
            "success": False,
            "output": "",
            "error": "SQL execution requires database connection",
            "exit_code": -1
        }


class NotebookExporter:
    """Export notebooks to various formats."""
    
    def to_script(self, cells: List[Cell], language: CodeLanguage = CodeLanguage.BASH) -> str:
        """Export to standalone script."""
        lines = []
        
        if language == CodeLanguage.BASH:
            lines.append("#!/bin/bash")
            lines.append("# Auto-generated from ClawOS Notebook")
            lines.append("")
            
            for cell in cells:
                if cell.cell_type == CellType.CODE and cell.language == CodeLanguage.BASH:
                    lines.append(f"# Cell: {cell.id}")
                    lines.append(cell.content)
                    lines.append("")
        
        elif language == CodeLanguage.PYTHON:
            lines.append("#!/usr/bin/env python3")
            lines.append("# Auto-generated from ClawOS Notebook")
            lines.append("")
            
            for cell in cells:
                if cell.cell_type == CellType.CODE and cell.language == CodeLanguage.PYTHON:
                    lines.append(f"# Cell: {cell.id}")
                    lines.append(cell.content)
                    lines.append("")
        
        return '\n'.join(lines)
    
    def to_html(self, cells: List[Cell]) -> str:
        """Export to HTML."""
        html = ['<div class="clawos-notebook">']
        
        for cell in cells:
            if cell.cell_type == CellType.MARKDOWN:
                # Convert markdown to HTML (simplified)
                content = cell.content.replace('\n', '<br>')
                html.append(f'<div class="markdown-cell">{content}</div>')
            
            elif cell.cell_type == CellType.CODE:
                lang = cell.language.value if cell.language else "text"
                html.append(f'<div class="code-cell">')
                html.append(f'<pre><code class="language-{lang}">{cell.content}</code></pre>')
                
                # Add outputs
                for output in cell.outputs:
                    if output.get("output"):
                        html.append(f'<pre class="output">{output["output"]}</pre>')
                    if output.get("error"):
                        html.append(f'<pre class="error">{output["error"]}</pre>')
                
                html.append('</div>')
        
        html.append('</div>')
        return '\n'.join(html)


# Convenience functions

def execute_notebook(markdown: str) -> Tuple[List[Cell], NotebookSession]:
    """Execute a notebook from markdown."""
    parser = NotebookParser()
    cells = parser.parse(markdown)
    
    session = NotebookSession()
    executor = NotebookExecutor(session)
    
    for cell in cells:
        executor.execute_cell(cell)
    
    return cells, session


def export_to_script(markdown: str, language: str = "bash") -> str:
    """Export notebook to script."""
    parser = NotebookParser()
    cells = parser.parse(markdown)
    
    lang_enum = CodeLanguage(language)
    exporter = NotebookExporter()
    return exporter.to_script(cells, lang_enum)


# Example notebooks

EXAMPLE_SERVER_SETUP = """# Server Setup Guide

This notebook sets up a basic web server.

## Check Prerequisites

First, let's check if we have the required tools.

```bash
which nginx
echo "Nginx check complete"
```

## Install Nginx

```bash
sudo apt-get update
sudo apt-get install -y nginx
```

## Configure Site

```python
# Generate configuration
config = '''
server {
    listen 80;
    server_name localhost;
    root /var/www/html;
}
'''
print(config)
```

## Start Service

```bash
sudo systemctl start nginx
sudo systemctl status nginx
```

## Test

```bash
curl -I http://localhost
```

Done!
"""

if __name__ == "__main__":
    # Demo execution
    logging.basicConfig(level=logging.INFO)
    
    cells, session = execute_notebook(EXAMPLE_SERVER_SETUP)
    
    print("\n=== EXECUTION RESULTS ===\n")
    for cell in cells:
        print(f"\n--- {cell.cell_type.value.upper()} CELL ---")
        if cell.cell_type == CellType.CODE:
            print(f"Language: {cell.language}")
            print(f"Code:\n{cell.content}")
            for output in cell.outputs:
                print(f"Output: {output.get('output', '')}")
                if output.get('error'):
                    print(f"Error: {output['error']}")
        else:
            print(cell.content[:100] + "...")
