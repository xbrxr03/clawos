# SPDX-License-Identifier: AGPL-3.0-or-later
"""Security utilities for ClawOS."""

import logging
import re
from typing import List, Optional
from urllib.parse import urlparse

log = logging.getLogger("clawos_core.security")


class InputValidator:
    """Input validation and sanitization."""

    DANGEROUS_PATTERNS = [
        # Only block patterns that bypass sandbox isolation.
        # The sandbox itself handles resource limits, timeouts, and filesystem isolation.
        # Standard Python (import os, open, read, write) is ALLOWED — that's the point of a sandbox.
        r'__import__\s*\(',          # bypass import controls
        r'os\.system\s*\(',         # shell execution
        r'subprocess\.(call|run|Popen|check_output)\s*\(',  # process spawning
        r'ctypes\.',                 # FFI / memory manipulation
        r'multiprocessing\.',        # process creation
        r'pty\.',                    # pseudo-terminal manipulation
    ]

    # Safe path characters
    SAFE_PATH_PATTERN = re.compile(r'^[a-zA-Z0-9_\-\.\/]+$')

    @classmethod
    def check_code_injection(cls, code: str) -> tuple[bool, List[str]]:
        """
        Check code for dangerous patterns.

        Returns (is_safe, found_patterns).
        """
        found = []
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                found.append(pattern)

        return len(found) == 0, found

    @classmethod
    def sanitize_string(cls, text: str, max_length: int = 1000) -> str:
        """Sanitize string input."""
        if not text:
            return ""

        # Truncate
        text = text[:max_length]

        # Remove control characters except newlines
        text = ''.join(c for c in text if c == '\n' or (c.isprintable() or c.isspace()))

        return text

    @classmethod
    def validate_port(cls, port: int) -> bool:
        """Validate port number."""
        return isinstance(port, int) and 1024 <= port <= 65535

    @classmethod
    def validate_workspace(cls, workspace: str) -> Optional[str]:
        """Validate workspace name."""
        if not workspace:
            return None

        # Allow alphanumeric, underscore, hyphen
        if not re.match(r'^[a-zA-Z0-9_-]+$', workspace):
            return None

        return workspace

    @classmethod
    def sanitize_path(cls, path: str) -> Optional[str]:
        """
        Sanitize file path to prevent directory traversal.

        Returns sanitized path or None if invalid.
        """
        if not path:
            return None

        # Remove null bytes
        path = path.replace('\x00', '')

        # Normalize path
        path = path.replace('..', '')  # Prevent traversal
        path = path.replace('//', '/')  # Normalize slashes

        # Remove leading slash (relative paths only)
        path = path.lstrip('/')

        # Validate characters
        if not cls.SAFE_PATH_PATTERN.match(path):
            log.warning("Invalid path characters: %s", path)
            return None

        return path

    @classmethod
    def validate_url(cls, url: str, allowed_schemes: Optional[List[str]] = None) -> bool:
        """
        Validate URL and check for SSRF.

        Returns True if URL is safe.
        """
        if allowed_schemes is None:
            allowed_schemes = ['http', 'https']

        try:
            parsed = urlparse(url)
        except (ValueError, TypeError):
            return False

        if parsed.scheme not in allowed_schemes:
            return False

        # Block internal IPs (SSRF prevention)
        hostname = parsed.hostname
        if not hostname:
            return False

        # Block localhost, private IPs, link-local
        blocked = ['localhost', '127.0.0.1', '0.0.0.0', '::1',
                    '169.254.', '10.', '172.16.', '192.168.']
        for block in blocked:
            if hostname == block or hostname.startswith(block):
                return False

        return True

    @classmethod
    def validate_api_key(cls, key: str) -> bool:
        """Validate API key format."""
        if not key:
            return False

        # API keys should be alphanumeric with some special chars
        if not re.match(r'^[a-zA-Z0-9_\-]{8,256}$', key):
            return False

        return True

    @classmethod
    def sanitize_html(cls, html: str) -> str:
        """Basic HTML sanitization."""
        if not html:
            return ""

        # Remove script tags
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # Remove event handlers
        html = re.sub(r'\son\w+\s*=\s*["\'][^"\']*["\']', '', html, flags=re.IGNORECASE)

        return html

    @classmethod
    def check_path_traversal(cls, path: str) -> bool:
        """
        Check if path contains directory traversal.

        Returns True if path is SAFE (no traversal detected).
        """
        if not path:
            return True

        # Check for ..
        if '..' in path:
            return False

        # Check for null bytes
        if '\x00' in path:
            return False

        return True

    @classmethod
    def validate_model_name(cls, name: str) -> bool:
        """Validate model name format."""
        if not name:
            return False

        # Allow alphanumeric, dots, hyphens, underscores, colons (for tags)
        return bool(re.match(r'^[a-zA-Z0-9._\-:]+$', name))

    @classmethod
    def rate_limit_key(cls, identifier: str) -> str:
        """Generate a rate limit key from an identifier."""
        # Sanitize and hash for privacy
        import hashlib
        return hashlib.sha256(identifier.encode()).hexdigest()[:16]