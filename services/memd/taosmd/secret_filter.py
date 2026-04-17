# SPDX-License-Identifier: AGPL-3.0-or-later
"""
secret_filter — 17-pattern secret redaction for memory writes.

Applied at every memory write entry point so secrets are never persisted.
Zero external dependencies — pure regex.
"""
from __future__ import annotations

import re
from typing import Tuple

# (pattern, label) pairs — order matters (more specific first)
_PATTERNS: list[Tuple[re.Pattern, str]] = [
    # OpenAI / Anthropic keys
    (re.compile(r'sk-[A-Za-z0-9\-_]{20,}'), "openai_key"),
    (re.compile(r'sk-ant-[A-Za-z0-9\-_]{20,}'), "anthropic_key"),
    # Generic Bearer / API tokens in headers or inline
    (re.compile(r'Bearer\s+[A-Za-z0-9\-_\.]{20,}'), "bearer_token"),
    (re.compile(r'(?i)api[_\-]?key["\s:=]+[A-Za-z0-9\-_]{16,}'), "api_key"),
    (re.compile(r'(?i)access[_\-]?token["\s:=]+[A-Za-z0-9\-_\.]{16,}'), "access_token"),
    (re.compile(r'(?i)secret[_\-]?key["\s:=]+[A-Za-z0-9\-_]{16,}'), "secret_key"),
    (re.compile(r'(?i)private[_\-]?key["\s:=]+[A-Za-z0-9\-_]{16,}'), "private_key"),
    # AWS
    (re.compile(r'AKIA[0-9A-Z]{16}'), "aws_access_key"),
    (re.compile(r'(?i)aws[_\-]?secret["\s:=]+[A-Za-z0-9/+=]{40}'), "aws_secret"),
    # Database URLs (contain credentials)
    (re.compile(r'(?i)(postgres|mysql|mongodb|redis)://[^\s"\'<>]+:[^\s"\'<>@]+@'), "db_url_creds"),
    # GitHub tokens
    (re.compile(r'gh[pousr]_[A-Za-z0-9]{36,}'), "github_token"),
    # JWT — header.payload.signature
    (re.compile(r'eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+'), "jwt"),
    # SSH private key header
    (re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'), "ssh_privkey"),
    # Generic hex/base64 secrets assigned to common variable names
    (re.compile(r'(?i)password["\s:=]+[^\s"\']{8,}'), "password"),
    (re.compile(r'(?i)passwd["\s:=]+[^\s"\']{8,}'), "passwd"),
    (re.compile(r'(?i)token["\s:=]+[A-Za-z0-9\-_\.]{20,}'), "token"),
    # Credit card (16-digit)
    (re.compile(r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b'), "credit_card"),
]


def redact_secrets(text: str) -> Tuple[str, list[str]]:
    """
    Replace secret patterns in *text* with [REDACTED:{label}].

    Returns (redacted_text, list_of_labels_found).
    Zero external dependencies.
    """
    found: list[str] = []
    for pattern, label in _PATTERNS:
        if pattern.search(text):
            found.append(label)
            # Preserve leading keyword for context, redact value
            text = pattern.sub(f"[REDACTED:{label}]", text)
    return text, found


def has_secrets(text: str) -> bool:
    return any(p.search(text) for p, _ in _PATTERNS)
