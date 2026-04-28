# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Security Hardening Module
==========================
Input validation, rate limiting, and security utilities for ClawOS.
"""
import re
import hashlib
import secrets
from typing import Optional, List, Dict, Any
from functools import wraps
from datetime import datetime, timedelta
import logging

log = logging.getLogger("security")


class InputValidator:
    """Input sanitization and validation."""
    
    # Dangerous patterns for code injection
    DANGEROUS_PATTERNS = [
        r'__import__\s*\(',
        r'eval\s*\(',
        r'exec\s*\(',
        r'compile\s*\(',
        r'os\.system\s*\(',
        r'subprocess\.call\s*\(',
        r'subprocess\.run\s*\(',
        r'\bimport\s+os\b',
        r'\bimport\s+subprocess\b',
        r'\bimport\s+sys\b',
        r'open\s*\([^)]*[\"\'][^\"\']*\.[^\"\']*[\"\']',
        r'\.read\s*\(\s*\)',
        r'\.write\s*\(',
    ]
    
    # Safe path characters
    SAFE_PATH_PATTERN = re.compile(r'^[a-zA-Z0-9_\-\.\/]+$')
    
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
            log.warning(f"Invalid path characters: {path}")
            return None
        
        return path
    
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
        
        return workspace.lower()


class RateLimiter:
    """Simple rate limiter for API endpoints."""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)
        self.requests: Dict[str, List[datetime]] = {}
    
    def is_allowed(self, key: str) -> bool:
        """Check if request is allowed for key."""
        now = datetime.now()
        
        # Clean old entries
        if key in self.requests:
            self.requests[key] = [
                t for t in self.requests[key]
                if now - t < self.window
            ]
        
        # Check count
        request_times = self.requests.get(key, [])
        if len(request_times) >= self.max_requests:
            log.warning(f"Rate limit exceeded for {key}")
            return False
        
        # Record request
        request_times.append(now)
        self.requests[key] = request_times
        
        return True


class SecurityContext:
    """Security context for operations."""
    
    def __init__(self, user_id: Optional[str] = None, permissions: List[str] = None):
        self.user_id = user_id or "anonymous"
        self.permissions = permissions or []
        self.session_id = secrets.token_hex(16)
        self.created_at = datetime.now()
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has permission."""
        return permission in self.permissions or "admin" in self.permissions
    
    def check_permission(self, permission: str):
        """Raise if permission not granted."""
        if not self.has_permission(permission):
            raise PermissionError(f"Missing permission: {permission}")


class AuditLogger:
    """Security audit logging."""

    def __init__(self, log_file: str = "/var/log/clawos/audit.log"):
        self.logger = logging.getLogger("clawos.audit")
        if not self.logger.handlers:
            import os
            from logging.handlers import RotatingFileHandler
            try:
                os.makedirs(os.path.dirname(log_file), exist_ok=True)
                fh = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
                fh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
                self.logger.addHandler(fh)
            except OSError:
                # Fall back to stderr if log dir isn't writable (e.g. dev mode)
                self.logger.addHandler(logging.StreamHandler())
            self.logger.setLevel(logging.INFO)

    def log_action(self, action: str, context: "SecurityContext", details: Dict = None):
        """Log security-relevant action."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "user_id": context.user_id,
            "session_id": context.session_id,
            "details": details or {},
        }
        self.logger.info("AUDIT: %s", entry)


# Decorators for common security patterns

def require_permission(permission: str):
    """Decorator to require permission."""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if hasattr(self, 'security_context'):
                self.security_context.check_permission(permission)
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


def sanitize_input(**validators):
    """Decorator to validate function inputs using InputValidator rules.

    Each keyword arg maps a parameter name to a validator callable that raises
    ValueError if the value is unsafe.  Pass-through when no validator defined.
    """
    def decorator(func):
        import inspect
        sig = inspect.signature(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            for param, validate in validators.items():
                if param in bound.arguments:
                    validate(bound.arguments[param])
            return func(*args, **kwargs)
        return wrapper
    return decorator


def rate_limit(limiter: RateLimiter, key_func = None):
    """Decorator to apply rate limiting."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = key_func(*args, **kwargs) if key_func else "default"
            if not limiter.is_allowed(key):
                raise RuntimeError("Rate limit exceeded")
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Security utilities

def generate_token(length: int = 32) -> str:
    """Generate secure random token."""
    return secrets.token_urlsafe(length)


def hash_sensitive(data: str) -> str:
    """Hash sensitive data."""
    return hashlib.sha256(data.encode()).hexdigest()


def mask_sensitive(text: str, visible_chars: int = 4) -> str:
    """Mask sensitive data (e.g., API keys)."""
    if len(text) <= visible_chars * 2:
        return "*" * len(text)
    return text[:visible_chars] + "*" * (len(text) - visible_chars * 2) + text[-visible_chars:]


# Common security headers
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'",
}


def add_security_headers(response):
    """Add security headers to response."""
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    return response
