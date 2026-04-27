# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for DevOps Notebooks skill."""

import pytest
from pathlib import Path
import tempfile

from skills.notebooks.main import (
    NotebookParser,
    NotebookExecutor,
    NotebookExporter,
    execute_notebook,
    Cell,
    CellType,
    CodeLanguage,
    EXAMPLE_SERVER_SETUP
)


class TestNotebookParser:
    """Test notebook parsing."""
    
    def test_parse_markdown(self):
        """Test parsing markdown into cells."""
        markdown = """# Test Notebook

## Section 1

```bash
echo "Hello"
```

Some text.

```python
print("World")
```
"""
        
        parser = NotebookParser()
        cells = parser.parse(markdown)
        
        assert len(cells) == 5  # Heading, bash, text, python
        
        # First cell is markdown
        assert cells[0].cell_type == CellType.MARKDOWN
        assert "# Test Notebook" in cells[0].content
        
        # Code cells
        code_cells = [c for c in cells if c.cell_type == CellType.CODE]
        assert len(code_cells) == 2
    
    def test_parse_code_languages(self):
        """Test parsing different languages."""
        markdown = """
```python
print("py")
```

```bash
echo "bash"
```

```javascript
console.log("js");
```
"""
        
        parser = NotebookParser()
        cells = parser.parse(markdown)
        
        code_cells = [c for c in cells if c.cell_type == CellType.CODE]
        assert len(code_cells) == 3
        
        # Check languages
        assert code_cells[0].language == CodeLanguage.PYTHON
        assert code_cells[1].language == CodeLanguage.BASH
        assert code_cells[2].language == CodeLanguage.JAVASCRIPT
    
    def test_parse_no_code(self):
        """Test parsing markdown without code."""
        markdown = "# Just a heading\n\nSome text."
        
        parser = NotebookParser()
        cells = parser.parse(markdown)
        
        assert len(cells) == 1
        assert cells[0].cell_type == CellType.MARKDOWN


class TestNotebookExecutor:
    """Test notebook execution."""
    
    @pytest.mark.asyncio
    async def test_execute_bash_cell(self):
        """Test bash cell execution."""
        cell = Cell(
            id="test-1",
            cell_type=CellType.CODE,
            content="echo 'Hello World'",
            language=CodeLanguage.BASH
        )
        
        executor = NotebookExecutor()
        result = executor.execute_cell(cell)
        
        assert result.execution_count == 1
        assert len(result.outputs) == 1
        assert result.outputs[0]["success"] is True
        assert "Hello World" in result.outputs[0]["output"]
    
    @pytest.mark.asyncio
    async def test_execute_python_cell(self):
        """Test Python cell execution."""
        cell = Cell(
            id="test-2",
            cell_type=CellType.CODE,
            content="x = 5 + 5\nprint(x)",
            language=CodeLanguage.PYTHON
        )
        
        executor = NotebookExecutor()
        result = executor.execute_cell(cell)
        
        assert result.execution_count == 1
        assert "10" in result.outputs[0]["output"]
    
    @pytest.mark.asyncio
    async def test_execute_markdown_cell(self):
        """Test markdown cell (no execution)."""
        cell = Cell(
            id="test-3",
            cell_type=CellType.MARKDOWN,
            content="# Title"
        )
        
        executor = NotebookExecutor()
        result = executor.execute_cell(cell)
        
        assert result.execution_count is None
        assert len(result.outputs) == 0
    
    @pytest.mark.asyncio
    async def test_variable_passing(self):
        """Test variable passing between cells."""
        executor = NotebookExecutor()
        
        # First cell sets variable
        cell1 = Cell(
            id="test-1",
            cell_type=CellType.CODE,
            content="name = 'ClawOS'",
            language=CodeLanguage.PYTHON
        )
        executor.execute_cell(cell1)
        
        # Check variable persisted
        assert executor.session.variables.get("name") == "ClawOS"


class TestNotebookExporter:
    """Test notebook export."""
    
    def test_export_to_bash(self):
        """Test export to bash script."""
        cells = [
            Cell(
                id="1",
                cell_type=CellType.MARKDOWN,
                content="# Test"
            ),
            Cell(
                id="2",
                cell_type=CellType.CODE,
                content="echo 'Hello'",
                language=CodeLanguage.BASH
            ),
            Cell(
                id="3",
                cell_type=CellType.CODE,
                content="echo 'World'",
                language=CodeLanguage.BASH
            )
        ]
        
        exporter = NotebookExporter()
        script = exporter.to_script(cells, CodeLanguage.BASH)
        
        assert "#!/bin/bash" in script
        assert 'echo "Hello"' in script
        assert 'echo "World"' in script
    
    def test_export_to_python(self):
        """Test export to Python script."""
        cells = [
            Cell(
                id="1",
                cell_type=CellType.CODE,
                content="print('Hello')",
                language=CodeLanguage.PYTHON
            )
        ]
        
        exporter = NotebookExporter()
        script = exporter.to_script(cells, CodeLanguage.PYTHON)
        
        assert "#!/usr/bin/env python3" in script
        assert "print('Hello')" in script
    
    def test_export_to_html(self):
        """Test export to HTML."""
        cells = [
            Cell(
                id="1",
                cell_type=CellType.MARKDOWN,
                content="# Title"
            ),
            Cell(
                id="2",
                cell_type=CellType.CODE,
                content="echo 'test'",
                language=CodeLanguage.BASH,
                outputs=[{"output": "test", "success": True}]
            )
        ]
        
        exporter = NotebookExporter()
        html = exporter.to_html(cells)
        
        assert "clawos-notebook" in html
        assert "Title" in html
        assert "test" in html


class TestIntegration:
    """Integration tests."""
    
    def test_execute_notebook_function(self):
        """Test execute_notebook convenience function."""
        markdown = """# Test

```bash
echo "integration test"
```

```python
print("success")
```
"""
        
        cells, session = execute_notebook(markdown)
        
        assert len(cells) == 4
        
        # Check outputs
        code_cells = [c for c in cells if c.cell_type == CellType.CODE]
        assert len(code_cells) == 2
        
        for cell in code_cells:
            assert len(cell.outputs) > 0
            assert cell.outputs[0]["success"] is True
    
    def test_example_notebook(self):
        """Test the example notebook parses."""
        parser = NotebookParser()
        cells = parser.parse(EXAMPLE_SERVER_SETUP)
        
        assert len(cells) > 0
        
        # Should have bash and python cells
        languages = set()
        for cell in cells:
            if cell.language:
                languages.add(cell.language)
        
        assert CodeLanguage.BASH in languages
        assert CodeLanguage.PYTHON in languages
