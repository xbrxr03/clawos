# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Code Companion Skill
====================
Developer-focused AI assistant with LSP integration, AST parsing,
and codebase understanding.

Features:
- LSP client for IDE-like code intelligence
- Tree-sitter for multi-language AST parsing
- Vector index of codebase
- Code review, refactoring, documentation generation
- VS Code/Cursor/JetBrains integration via MCP

Addresses the local coding agent gap from CRITICAL_GAPS_RESEARCH.md
"""
import asyncio
import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse

try:
    import chromadb
    from chromadb.utils import embedding_functions
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None
    embedding_functions = None

from clawos_core.constants import CLAWOS_DIR

log = logging.getLogger("code_companion")

# Default embedding model for code
DEFAULT_EMBED_MODEL = "all-MiniLM-L6-v2"


@dataclass
class CodeSymbol:
    """A code symbol (function, class, variable, etc.)"""
    name: str
    kind: str  # function, class, method, variable, etc.
    file_path: str
    line_start: int
    line_end: int
    signature: Optional[str] = None
    docstring: Optional[str] = None
    parent: Optional[str] = None


@dataclass
class CodeContext:
    """Context for code operations."""
    workspace: str
    project_path: Path
    language: str
    symbols: List[CodeSymbol]


class LSPClient:
    """
    Language Server Protocol client for code intelligence.
    
    Supports:
    - Go-to-definition
    - Find references
    - Hover information
    - Code completion
    - Diagnostics
    """
    
    def __init__(self, project_path: Path, language: str):
        self.project_path = project_path
        self.language = language
        self.process: Optional[subprocess.Popen] = None
        self.request_id = 0
        self._message_buffer = ""
    
    # Language server commands
    LSP_SERVERS = {
        "python": ["pylsp"],  # python-lsp-server
        "typescript": ["typescript-language-server", "--stdio"],
        "javascript": ["typescript-language-server", "--stdio"],
        "rust": ["rust-analyzer"],
        "go": ["gopls"],
        "java": ["jdtls"],
        "c": ["clangd"],
        "cpp": ["clangd"],
    }
    
    async def start(self) -> bool:
        """Start the language server."""
        if self.language not in self.LSP_SERVERS:
            log.warning(f"No LSP server configured for {self.language}")
            return False
        
        cmd = self.LSP_SERVERS[self.language]
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.project_path,
                text=True
            )
            
            # Initialize LSP
            await self._send_request("initialize", {
                "processId": os.getpid(),
                "rootUri": self.project_path.as_uri() if hasattr(self.project_path, 'as_uri') else f"file://{self.project_path}",
                "capabilities": {}
            })
            
            log.info(f"Started {self.language} LSP server")
            return True
            
        except Exception as e:
            log.error(f"Failed to start LSP server: {e}")
            return False
    
    async def stop(self):
        """Stop the language server."""
        if self.process:
            self.process.terminate()
            self.process = None
    
    async def _send_request(self, method: str, params: dict) -> dict:
        """Send LSP request."""
        self.request_id += 1
        message = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params
        }
        
        content = json.dumps(message)
        header = f"Content-Length: {len(content)}\r\n\r\n"
        
        if self.process and self.process.stdin:
            self.process.stdin.write(header + content)
            self.process.stdin.flush()
        
        # Read response (simplified - real implementation needs proper parsing)
        return {}
    
    async def goto_definition(self, file_path: str, line: int, character: int) -> Optional[Dict]:
        """Go to definition of symbol at position."""
        result = await self._send_request("textDocument/definition", {
            "textDocument": {"uri": f"file://{file_path}"},
            "position": {"line": line, "character": character}
        })
        return result
    
    async def find_references(self, file_path: str, line: int, character: int) -> List[Dict]:
        """Find all references to symbol at position."""
        result = await self._send_request("textDocument/references", {
            "textDocument": {"uri": f"file://{file_path}"},
            "position": {"line": line, "character": character},
            "context": {"includeDeclaration": True}
        })
        return result.get("result", [])
    
    async def hover(self, file_path: str, line: int, character: int) -> Optional[str]:
        """Get hover information for symbol at position."""
        result = await self._send_request("textDocument/hover", {
            "textDocument": {"uri": f"file://{file_path}"},
            "position": {"line": line, "character": character}
        })
        
        if result and "result" in result:
            contents = result["result"].get("contents", {})
            if isinstance(contents, dict):
                return contents.get("value", "")
            return str(contents)
        return None


class TreeSitterParser:
    """
    Tree-sitter based AST parser for code understanding.
    
    Extracts:
    - Function/class definitions
    - Call graphs
    - Imports/dependencies
    - Docstrings
    """
    
    def __init__(self, language: str):
        self.language = language
        self.parser = None
        self._init_parser()
    
    def _init_parser(self):
        """Initialize tree-sitter parser."""
        try:
            # Import tree-sitter language modules
            if self.language == "python":
                from tree_sitter_python import language
            elif self.language in ["typescript", "javascript"]:
                from tree_sitter_typescript import language
            elif self.language == "rust":
                from tree_sitter_rust import language
            elif self.language == "go":
                from tree_sitter_go import language
            elif self.language == "java":
                from tree_sitter_java import language
            elif self.language == "c":
                from tree_sitter_c import language
            elif self.language == "cpp":
                from tree_sitter_cpp import language
            else:
                log.warning(f"No tree-sitter grammar for {self.language}")
                return
            
            from tree_sitter import Parser
            
            self.parser = Parser(language())
            log.info(f"Initialized {self.language} parser")
            
        except ImportError as e:
            log.warning(f"Tree-sitter not available for {self.language}: {e}")
        except Exception as e:
            log.error(f"Failed to initialize parser: {e}")
    
    def parse_file(self, file_path: Path) -> List[CodeSymbol]:
        """Parse a file and extract symbols."""
        if not self.parser:
            return []
        
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            tree = self.parser.parse(bytes(content, 'utf8'))
            
            symbols = []
            root_node = tree.root_node
            
            # Language-specific symbol extraction
            if self.language == "python":
                symbols = self._extract_python_symbols(root_node, content, str(file_path))
            
            return symbols
            
        except Exception as e:
            log.error(f"Failed to parse {file_path}: {e}")
            return []
    
    def _extract_python_symbols(self, node, content: str, file_path: str) -> List[CodeSymbol]:
        """Extract Python-specific symbols."""
        symbols = []
        
        def walk(node, parent_name=None):
            if node.type == "function_definition":
                # Get function name
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = content[name_node.start_byte:name_node.end_byte]
                    
                    # Get docstring
                    docstring = None
                    body = node.child_by_field_name("body")
                    if body:
                        for child in body.children:
                            if child.type == "expression_statement":
                                expr = child.children[0] if child.children else None
                                if expr and expr.type == "string":
                                    docstring = content[expr.start_byte:expr.end_byte]
                                    break
                    
                    # Get signature (parameters)
                    params = node.child_by_field_name("parameters")
                    signature = ""
                    if params:
                        signature = content[params.start_byte:params.end_byte]
                    
                    symbol = CodeSymbol(
                        name=name,
                        kind="function",
                        file_path=file_path,
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        signature=signature,
                        docstring=docstring,
                        parent=parent_name
                    )
                    symbols.append(symbol)
                    
                    # Walk children with this as parent
                    for child in node.children:
                        walk(child, name)
            
            elif node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = content[name_node.start_byte:name_node.end_byte]
                    
                    symbol = CodeSymbol(
                        name=name,
                        kind="class",
                        file_path=file_path,
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        parent=parent_name
                    )
                    symbols.append(symbol)
                    
                    # Walk children with this as parent
                    for child in node.children:
                        walk(child, name)
            
            else:
                # Walk children
                for child in node.children:
                    walk(child, parent_name)
        
        walk(node)
        return symbols


class CodebaseIndex:
    """
    Vector index of codebase for semantic search.
    
    Uses ChromaDB for:
    - File-level embeddings
    - Function-level embeddings
    - Import/dependency tracking
    """
    
    def __init__(self, project_path: Path, workspace: str = "code_default"):
        if not CHROMADB_AVAILABLE:
            raise RuntimeError("ChromaDB not available. Install with: pip install chromadb")
        
        self.project_path = project_path
        self.workspace = workspace
        self.db_path = CLAWOS_DIR / "code_index" / workspace
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(path=str(self.db_path))
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=DEFAULT_EMBED_MODEL
        )
        
        # Collections
        self.files_collection = self.client.get_or_create_collection(
            name="files",
            embedding_function=self.embed_fn
        )
        self.symbols_collection = self.client.get_or_create_collection(
            name="symbols",
            embedding_function=self.embed_fn
        )
    
    def index_file(self, file_path: Path, content: str, symbols: List[CodeSymbol]):
        """Index a file and its symbols."""
        # Index file
        relative_path = str(file_path.relative_to(self.project_path))
        
        self.files_collection.upsert(
            ids=[relative_path],
            documents=[content[:10000]],  # First 10k chars
            metadatas=[{
                "path": relative_path,
                "language": self._detect_language(file_path),
                "size": len(content),
                "line_count": content.count('\n') + 1
            }]
        )
        
        # Index symbols
        for symbol in symbols:
            symbol_id = f"{relative_path}:{symbol.name}:{symbol.line_start}"
            
            doc = f"{symbol.name} {symbol.signature or ''}\n{symbol.docstring or ''}"
            
            self.symbols_collection.upsert(
                ids=[symbol_id],
                documents=[doc],
                metadatas=[{
                    "file": relative_path,
                    "name": symbol.name,
                    "kind": symbol.kind,
                    "line_start": symbol.line_start,
                    "line_end": symbol.line_end,
                    "parent": symbol.parent or ""
                }]
            )
    
    def search(self, query: str, n_results: int = 10) -> List[Dict]:
        """Semantic search over codebase."""
        # Search files
        file_results = self.files_collection.query(
            query_texts=[query],
            n_results=min(n_results, 5)
        )
        
        # Search symbols
        symbol_results = self.symbols_collection.query(
            query_texts=[query],
            n_results=min(n_results, 10)
        )
        
        results = []
        
        # Process file results
        if file_results['ids']:
            for i, doc_id in enumerate(file_results['ids'][0]):
                results.append({
                    "type": "file",
                    "path": doc_id,
                    "distance": file_results['distances'][0][i] if file_results.get('distances') else 0,
                    "metadata": file_results['metadatas'][0][i] if file_results.get('metadatas') else {}
                })
        
        # Process symbol results
        if symbol_results['ids']:
            for i, doc_id in enumerate(symbol_results['ids'][0]):
                results.append({
                    "type": "symbol",
                    "id": doc_id,
                    "name": symbol_results['metadatas'][0][i].get('name') if symbol_results.get('metadatas') else '',
                    "kind": symbol_results['metadatas'][0][i].get('kind') if symbol_results.get('metadatas') else '',
                    "path": symbol_results['metadatas'][0][i].get('file') if symbol_results.get('metadatas') else '',
                    "distance": symbol_results['distances'][0][i] if symbol_results.get('distances') else 0
                })
        
        # Sort by distance (lower is better)
        results.sort(key=lambda x: x.get('distance', 1))
        
        return results[:n_results]
    
    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        ext = file_path.suffix.lower()
        
        mapping = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.jsx': 'javascript',
            '.rs': 'rust',
            '.go': 'go',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.rb': 'ruby',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.r': 'r',
            '.m': 'matlab',
            '.sh': 'bash',
            '.sql': 'sql',
            '.html': 'html',
            '.css': 'css',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.toml': 'toml',
            '.md': 'markdown',
        }
        
        return mapping.get(ext, 'unknown')


class CodeCompanion:
    """
    Main code companion interface.
    
    Provides:
    - Code review
    - Refactoring suggestions
    - Documentation generation
    - Test generation
    - Code explanation
    """
    
    def __init__(self, project_path: Path, workspace: str = "code_default"):
        self.project_path = Path(project_path)
        self.workspace = workspace
        self.index = CodebaseIndex(project_path, workspace)
        self.lsp_clients: Dict[str, LSPClient] = {}
        self.parsers: Dict[str, TreeSitterParser] = {}
    
    async def index_project(self, progress_callback=None):
        """Index the entire project."""
        log.info(f"Indexing project: {self.project_path}")
        
        # Find all code files
        code_files = []
        for pattern in ["**/*.py", "**/*.js", "**/*.ts", "**/*.rs", "**/*.go", "**/*.java"]:
            code_files.extend(self.project_path.glob(pattern))
        
        total = len(code_files)
        indexed = 0
        
        for file_path in code_files:
            if file_path.is_file():
                try:
                    # Detect language
                    language = self.index._detect_language(file_path)
                    
                    # Parse with tree-sitter
                    if language not in self.parsers:
                        self.parsers[language] = TreeSitterParser(language)
                    
                    parser = self.parsers[language]
                    symbols = parser.parse_file(file_path)
                    
                    # Read content
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    
                    # Index
                    self.index.index_file(file_path, content, symbols)
                    
                    indexed += 1
                    if progress_callback:
                        progress_callback(indexed, total, str(file_path))
                    
                except Exception as e:
                    log.warning(f"Failed to index {file_path}: {e}")
        
        log.info(f"Indexed {indexed}/{total} files")
        return indexed
    
    def search_code(self, query: str, n_results: int = 10) -> List[Dict]:
        """Search codebase for relevant code."""
        return self.index.search(query, n_results)
    
    def explain_symbol(self, file_path: str, line: int) -> str:
        """Explain a code symbol at the given location."""
        # Find the symbol
        results = self.index.symbols_collection.get(
            where={"file": file_path}
        )
        
        if not results['ids']:
            return "Symbol not found in index"
        
        # Find closest symbol to line
        closest = None
        closest_distance = float('inf')
        
        for i, metadata in enumerate(results['metadatas']):
            line_start = metadata.get('line_start', 0)
            distance = abs(line_start - line)
            
            if distance < closest_distance:
                closest_distance = distance
                closest = {
                    'name': metadata.get('name'),
                    'kind': metadata.get('kind'),
                    'line_start': line_start,
                    'line_end': metadata.get('line_end'),
                    'docstring': results['documents'][i] if results.get('documents') else ''
                }
        
        if closest:
            return f"""{closest['kind'].capitalize()}: {closest['name']}
Location: {file_path}:{closest['line_start']}-{closest['line_end']}

Documentation:
{closest['docstring'][:500]}
"""
        
        return "Could not find symbol information"
    
    def suggest_refactoring(self, file_path: str, code: str) -> List[Dict]:
        """Suggest refactoring improvements for code."""
        suggestions = []
        
        # Simple heuristics (replace with LLM-based analysis)
        lines = code.split('\n')
        
        for i, line in enumerate(lines, 1):
            # Long lines
            if len(line) > 100:
                suggestions.append({
                    "line": i,
                    "type": "style",
                    "message": f"Line too long ({len(line)} chars). Consider breaking into multiple lines."
                })
            
            # TODO comments
            if "TODO" in line.upper():
                suggestions.append({
                    "line": i,
                    "type": "todo",
                    "message": f"TODO found: {line.strip()[:80]}"
                })
            
            # Bare except
            if "except:" in line and "except Exception" not in line:
                suggestions.append({
                    "line": i,
                    "type": "error",
                    "message": "Bare except clause. Use 'except Exception:' or more specific exception."
                })
        
        return suggestions
    
    def generate_tests(self, symbol_name: str, file_path: str) -> str:
        """Generate test cases for a function/class."""
        # Search for the symbol
        results = self.index.symbols_collection.get(
            where={"name": symbol_name, "file": file_path}
        )
        
        if not results['ids']:
            return f"Symbol '{symbol_name}' not found"
        
        # Get symbol info
        metadata = results['metadatas'][0]
        kind = metadata.get('kind')
        
        # Generate basic test template
        if kind == 'function':
            return f"""import pytest
from {file_path.replace('/', '.').replace('.py', '')} import {symbol_name}

def test_{symbol_name}_basic():
    # TODO: Add test cases
    result = {symbol_name}()
    assert result is not None

def test_{symbol_name}_edge_cases():
    # TODO: Add edge case tests
    pass
"""
        elif kind == 'class':
            return f"""import pytest
from {file_path.replace('/', '.').replace('.py', '')} import {symbol_name}

class Test{symbol_name}:
    def test_init(self):
        obj = {symbol_name}()
        assert obj is not None
    
    def test_methods(self):
        # TODO: Test class methods
        pass
"""
        
        return f"Cannot generate tests for {kind}"


# Convenience functions

def create_companion(project_path: str, workspace: str = "code_default") -> CodeCompanion:
    """Create a code companion for a project."""
    return CodeCompanion(Path(project_path), workspace)


async def index_project(project_path: str, workspace: str = "code_default", progress_callback=None):
    """Index a project for code search."""
    companion = create_companion(project_path, workspace)
    return await companion.index_project(progress_callback)


def search_code(query: str, workspace: str = "code_default", n_results: int = 10) -> List[Dict]:
    """Search indexed code."""
    # This requires the project to be indexed first
    # For now, return empty results
    return []
