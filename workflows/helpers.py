# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import os
import re
import subprocess
from collections import deque
from pathlib import Path
from typing import Iterable


TRUE_VALUES = {"1", "true", "yes", "y", "on"}
SUPPORTED_PLATFORMS = ["linux", "macos", "windows"]
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "in", "is", "it", "its", "of", "on", "or", "that", "the", "to", "was",
    "were", "will", "with", "this", "these", "those", "their", "there",
    "about", "after", "before", "into", "over", "under", "than", "then",
    "them", "they", "you", "your", "our", "we", "can", "may", "should",
}


def parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in TRUE_VALUES


def format_bytes(size: int | float) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(max(size, 0))
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)}{unit}"
            return f"{value:.1f}{unit}"
        value /= 1024
    return "0B"


def tail_lines(path: Path, count: int) -> list[str]:
    maxlen = max(1, count)
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return [line.rstrip("\n") for line in deque(handle, maxlen=maxlen)]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def split_sentences(text: str) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    parts = re.split(r"(?<=[.!?])\s+", normalized)
    return [part.strip() for part in parts if part.strip()]


def keyword_terms(text: str, limit: int = 6) -> list[str]:
    counts: dict[str, int] = {}
    for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", normalize_text(text).lower()):
        if token in STOP_WORDS:
            continue
        counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [word for word, _count in ranked[:limit]]


def summarize_sentences(text: str, limit: int = 4, min_words: int = 4) -> list[str]:
    sentences = split_sentences(text)
    if not sentences:
        return []

    frequencies: dict[str, int] = {}
    for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", normalize_text(text).lower()):
        if token in STOP_WORDS:
            continue
        frequencies[token] = frequencies.get(token, 0) + 1

    scored: list[tuple[float, int, str]] = []
    for index, sentence in enumerate(sentences):
        tokens = [
            token for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", sentence.lower())
            if token not in STOP_WORDS
        ]
        if len(tokens) < min_words:
            continue
        score = sum(frequencies.get(token, 0) for token in tokens) / max(len(tokens), 1)
        scored.append((score, index, sentence))

    if not scored:
        return sentences[:limit]

    top = sorted(scored, key=lambda item: (-item[0], item[1]))[:limit]
    return [sentence for _score, _index, sentence in sorted(top, key=lambda item: item[1])]


def run_command(args: list[str], cwd: Path | None = None, timeout: int = 15) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(cwd) if cwd else None,
    )


def extract_pdf_text(path: Path, max_pages: int = 12) -> tuple[str, int]:
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # type: ignore[assignment]
        except ImportError as exc:
            raise RuntimeError("pypdf is required to summarize PDFs") from exc

    reader = PdfReader(str(path), strict=False)
    chunks: list[str] = []
    pages_used = 0
    for page in reader.pages[:max_pages]:
        raw = page.extract_text() or ""
        text = normalize_text(raw)
        if len(text.split()) < 8:
            continue
        chunks.append(text)
        pages_used += 1
    return "\n".join(chunks).strip(), pages_used


def iter_files(root: Path, skip_dirs: set[str] | None = None, max_files: int | None = None) -> Iterable[Path]:
    skip_dirs = skip_dirs or set()
    seen = 0
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            name for name in dirnames
            if name not in skip_dirs and not name.startswith(".")
        ]
        for filename in filenames:
            path = Path(current_root) / filename
            try:
                if path.is_symlink() or not path.is_file():
                    continue
            except OSError:
                continue
            yield path
            seen += 1
            if max_files is not None and seen >= max_files:
                return
