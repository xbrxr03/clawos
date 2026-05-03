# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Kizuna — Document Extractors.
Extracts raw text from: PDF, DOCX, TXT, MD, and code files.
Returns list of {filename, content, type, chunk_index} dicts.
"""
import logging
from pathlib import Path
from typing import Iterator
import subprocess

log = logging.getLogger("braind.extractors")

# Code file extensions we extract as plain text
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".cpp",
    ".c", ".h", ".cs", ".rb", ".php", ".swift", ".kt", ".scala", ".sh",
    ".bash", ".zsh", ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg",
    ".env", ".sql", ".graphql", ".proto", ".vue", ".svelte",
}

TEXT_EXTENSIONS = {".txt", ".md", ".mdx", ".rst", ".csv", ".log", ".xml", ".html"}

MAX_CHUNK_CHARS = 2000  # Chunk size for LLM extraction
MAX_FILE_CHARS = 20000  # Max per file before truncation


def extract_file(path: Path) -> list[dict]:
    """
    Extract text from a single file. Returns list of chunks.
    Each chunk: {filename, filepath, content, file_type, chunk_index, total_chunks}
    """
    suffix = path.suffix.lower()

    try:
        if suffix == ".pdf":
            return _extract_pdf(path)
        elif suffix == ".docx":
            return _extract_docx(path)
        elif suffix in TEXT_EXTENSIONS:
            return _extract_text(path, "markdown" if suffix in (".md", ".mdx") else "text")
        elif suffix in CODE_EXTENSIONS:
            return _extract_text(path, "code")
        else:
            # Try plain text for unknown types
            return _extract_text(path, "unknown")
    except (OSError, ValueError, ImportError) as e:
        log.warning(f"Failed to extract {path.name}: {e}")
        return []


def _chunk_text(text: str, filename: str, filepath: str, file_type: str) -> list[dict]:
    """Split text into overlapping chunks for LLM processing."""
    text = text.strip()
    if not text:
        return []

    # Truncate very large files
    if len(text) > MAX_FILE_CHARS:
        log.debug(f"Truncating {filename}: {len(text)} → {MAX_FILE_CHARS} chars")
        text = text[:MAX_FILE_CHARS] + "\n...[truncated]"

    chunks = []
    i = 0
    chunk_idx = 0
    overlap = 200  # chars of overlap between chunks

    while i < len(text):
        chunk = text[i:i + MAX_CHUNK_CHARS]
        chunks.append({
            "filename": filename,
            "filepath": filepath,
            "content": chunk,
            "file_type": file_type,
            "chunk_index": chunk_idx,
        })
        chunk_idx += 1
        i += MAX_CHUNK_CHARS - overlap

    # Set total_chunks
    for c in chunks:
        c["total_chunks"] = len(chunks)

    return chunks


def _extract_pdf(path: Path) -> list[dict]:
    """Extract text from PDF using pdfplumber (preferred) or pypdf fallback."""
    text = ""

    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            pages = []
            for page in pdf.pages[:50]:  # Cap at 50 pages
                t = page.extract_text()
                if t:
                    pages.append(t)
            text = "\n\n".join(pages)
        log.debug(f"pdfplumber extracted {len(text)} chars from {path.name}")
    except ImportError as e:
        log.debug(f"suppressed: {e}")
    except (OSError, PermissionError) as e:
        log.debug(f"pdfplumber failed for {path.name}: {e}")

    if not text:
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            pages = []
            for page in reader.pages[:50]:
                t = page.extract_text()
                if t:
                    pages.append(t)
            text = "\n\n".join(pages)
            log.debug(f"pypdf extracted {len(text)} chars from {path.name}")
        except (OSError, ValueError, ImportError) as e:
            log.warning(f"PDF extraction failed for {path.name}: {e}")
            return []

    return _chunk_text(text, path.name, str(path), "pdf")


def _extract_docx(path: Path) -> list[dict]:
    """Extract text from DOCX."""
    try:
        from docx import Document
        doc = Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n\n".join(paragraphs)
        return _chunk_text(text, path.name, str(path), "docx")
    except ImportError:
        log.warning("python-docx not installed — pip install python-docx")
        return []
    except (OSError, subprocess.SubprocessError, RuntimeError) as e:
        log.warning(f"DOCX extraction failed for {path.name}: {e}")
        return []


def _extract_text(path: Path, file_type: str) -> list[dict]:
    """Extract plain text / markdown / code file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return _chunk_text(text, path.name, str(path), file_type)
    except (OSError, UnicodeDecodeError) as e:
        log.warning(f"Text extraction failed for {path.name}: {e}")
        return []


def iter_zip_chunks(zip_path: Path) -> Iterator[dict]:
    """
    Extract all documents from a ZIP file, yielding chunks one by one.
    Skips: hidden files, __pycache__, .git, node_modules, binary files.
    """
    import zipfile
    import tempfile
    import shutil

    SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv",
                 "dist", "build", ".next", ".nuxt"}
    SKIP_EXTENSIONS = {
        ".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe", ".bin",
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico", ".svg", ".webp",
        ".mp3", ".mp4", ".wav", ".avi", ".mov",
        ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
        ".lock", ".cache",
    }

    extractable = CODE_EXTENSIONS | TEXT_EXTENSIONS | {".pdf", ".docx"}

    with tempfile.TemporaryDirectory(prefix="en_brain_") as tmpdir:
        tmp = Path(tmpdir)

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                # Security: check for path traversal
                for name in zf.namelist():
                    if name.startswith("/") or ".." in name:
                        log.warning(f"Skipping suspicious zip entry: {name}")
                        continue

                    # Skip directories
                    if name.endswith("/"):
                        continue

                    fpath = Path(name)
                    parts = fpath.parts

                    # Skip hidden dirs and known garbage
                    if any(p.startswith(".") for p in parts[:-1]):
                        continue
                    if any(p in SKIP_DIRS for p in parts):
                        continue

                    suffix = fpath.suffix.lower()
                    if suffix in SKIP_EXTENSIONS:
                        continue
                    if suffix not in extractable:
                        continue

                    # Extract this file
                    try:
                        zf.extract(name, tmp)
                        extracted = tmp / name
                        chunks = extract_file(extracted)
                        # Restore original relative path as filename
                        for chunk in chunks:
                            chunk["filename"] = name
                        yield from chunks
                    except (OSError, zipfile.BadZipFile, RuntimeError) as e:
                        log.debug(f"Skipping {name}: {e}")

        except zipfile.BadZipFile as e:
            log.error(f"Not a valid ZIP: {e}")
            return


def count_extractable(zip_path: Path) -> int:
    """Count how many extractable files are in the ZIP (for progress estimation)."""
    extractable = CODE_EXTENSIONS | TEXT_EXTENSIONS | {".pdf", ".docx"}
    SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}
    count = 0
    try:
        import zipfile
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                fpath = Path(name)
                if any(p in SKIP_DIRS for p in fpath.parts):
                    continue
                if fpath.suffix.lower() in extractable:
                    count += 1
    except (OSError, zipfile.BadZipFile, ValueError) as e:
        log.debug(f"unexpected: {e}")
        pass
    return count
