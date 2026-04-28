# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS Core Exceptions Module

Centralized exception handling for the ClawOS microservices architecture.
Provides standardized error types, error codes, and utilities for consistent
error handling across all services.

This module ensures:
- Consistent error types across all services
- Proper error serialization for API responses
- Structured error logging with context
- Error severity classification
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels for classification and alerting."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCode(Enum):
    """Standardized error codes across ClawOS services."""
    # Authentication errors (1000-1099)
    AUTH_UNAUTHORIZED = 1000
    AUTH_FORBIDDEN = 1001
    AUTH_TOKEN_EXPIRED = 1002
    AUTH_INVALID_CREDENTIALS = 1003
    
    # Validation errors (2000-2099)
    VALIDATION_ERROR = 2000
    VALIDATION_REQUIRED_FIELD = 2001
    VALIDATION_INVALID_FORMAT = 2002
    VALIDATION_OUT_OF_RANGE = 2003
    
    # Resource errors (3000-3099)
    RESOURCE_NOT_FOUND = 3000
    RESOURCE_CONFLICT = 3001
    RESOURCE_UNAVAILABLE = 3002
    RESOURCE_RATE_LIMITED = 3003
    
    # Service errors (4000-4099)
    SERVICE_UNAVAILABLE = 4000
    SERVICE_TIMEOUT = 4001
    SERVICE_OVERLOADED = 4002
    SERVICE_DEPENDENCY_FAILED = 4003
    
    # Circuit breaker errors (5000-5099)
    CIRCUIT_BREAKER_OPEN = 5000
    CIRCUIT_BREAKER_HALF_OPEN = 5001
    CIRCUIT_BREAKER_TIMEOUT = 5002
    
    # Internal errors (9000-9099)
    INTERNAL_ERROR = 9000
    INTERNAL_DATABASE_ERROR = 9001
    INTERNAL_CACHE_ERROR = 9002
    INTERNAL_UNKNOWN = 9999


@dataclass
class ErrorContext:
    """Context information for error tracking and debugging."""
    service: str
    operation: str
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "service": self.service,
            "operation": self.operation,
            "user_id": self.user_id,
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "additional_data": self.additional_data,
        }


class ClawOSError(Exception):
    """Base exception for all ClawOS errors."""
    
    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.INTERNAL_UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.severity = severity
        self.context = context or ErrorContext(
            service="unknown",
            operation="unknown"
        )
        self.cause = cause
        
    def to_dict(self) -> Dict[str, Any]:
        """Serialize error to dictionary for API responses."""
        result = {
            "error": {
                "code": self.code.value,
                "code_name": self.code.name,
                "message": self.message,
                "severity": self.severity.value,
            }
        }
        
        if self.context:
            result["error"]["context"] = self.context.to_dict()
            
        if self.cause:
            result["error"]["cause"] = str(self.cause)
            
        return result
    
    def log(self, logger: Optional[logging.Logger] = None):
        """Log the error with appropriate severity."""
        log = logger or logging.getLogger(__name__)
        
        log_method = {
            ErrorSeverity.DEBUG: log.debug,
            ErrorSeverity.INFO: log.info,
            ErrorSeverity.WARNING: log.warning,
            ErrorSeverity.ERROR: log.error,
            ErrorSeverity.CRITICAL: log.critical,
        }.get(self.severity, log.error)
        
        log_method(
            f"[{self.code.name}] {self.message}",
            extra={
                "error_code": self.code.value,
                "error_context": self.context.to_dict() if self.context else None,
            }
        )


# Specific exception classes for common error types

class AuthenticationError(ClawOSError):
    """Authentication-related errors."""
    
    def __init__(self, message: str, code: ErrorCode = ErrorCode.AUTH_UNAUTHORIZED, **kwargs):
        super().__init__(message, code=code, severity=ErrorSeverity.WARNING, **kwargs)


class ValidationError(ClawOSError):
    """Input validation errors."""
    
    def __init__(self, message: str, code: ErrorCode = ErrorCode.VALIDATION_ERROR, **kwargs):
        super().__init__(message, code=code, severity=ErrorSeverity.WARNING, **kwargs)


class ResourceNotFoundError(ClawOSError):
    """Resource not found errors."""
    
    def __init__(self, message: str, code: ErrorCode = ErrorCode.RESOURCE_NOT_FOUND, **kwargs):
        super().__init__(message, code=code, severity=ErrorSeverity.WARNING, **kwargs)


class ServiceUnavailableError(ClawOSError):
    """Service unavailable errors."""
    
    def __init__(self, message: str, code: ErrorCode = ErrorCode.SERVICE_UNAVAILABLE, **kwargs):
        super().__init__(message, code=code, severity=ErrorSeverity.ERROR, **kwargs)


class CircuitBreakerError(ClawOSError):
    """Circuit breaker related errors."""
    
    def __init__(self, message: str, code: ErrorCode = ErrorCode.CIRCUIT_BREAKER_OPEN, **kwargs):
        super().__init__(message, code=code, severity=ErrorSeverity.ERROR, **kwargs)


class DatabaseError(ClawOSError):
    """Database-related errors."""
    
    def __init__(self, message: str, code: ErrorCode = ErrorCode.INTERNAL_DATABASE_ERROR, **kwargs):
        super().__init__(message, code=code, severity=ErrorSeverity.ERROR, **kwargs)


# Utility functions

def handle_exception(
    exception: Exception,
    service: str,
    operation: str,
    raise_http: bool = False,
) -> ClawOSError:
    """
    Convert any exception to a ClawOSError with proper context.
    
    Args:
        exception: The original exception
        service: Name of the service where the error occurred
        operation: Name of the operation being performed
        raise_http: If True, raise an HTTPException for FastAPI
        
    Returns:
        A ClawOSError with proper context
    """
    context = ErrorContext(service=service, operation=operation)
    
    if isinstance(exception, ClawOSError):
        if not exception.context.service:
            exception.context = context
        error = exception
    else:
        error = ClawOSError(
            message=str(exception),
            code=ErrorCode.INTERNAL_UNKNOWN,
            severity=ErrorSeverity.ERROR,
            context=context,
            cause=exception,
        )
    
    error.log()
    
    if raise_http:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=_get_http_status(error.code),
            detail=error.to_dict(),
        )
    
    return error


def _get_http_status(code: ErrorCode) -> int:
    """Map error codes to HTTP status codes."""
    mapping = {
        ErrorCode.AUTH_UNAUTHORIZED: 401,
        ErrorCode.AUTH_FORBIDDEN: 403,
        ErrorCode.AUTH_TOKEN_EXPIRED: 401,
        ErrorCode.AUTH_INVALID_CREDENTIALS: 401,
        ErrorCode.VALIDATION_ERROR: 422,
        ErrorCode.VALIDATION_REQUIRED_FIELD: 422,
        ErrorCode.VALIDATION_INVALID_FORMAT: 422,
        ErrorCode.VALIDATION_OUT_OF_RANGE: 422,
        ErrorCode.RESOURCE_NOT_FOUND: 404,
        ErrorCode.RESOURCE_CONFLICT: 409,
        ErrorCode.RESOURCE_UNAVAILABLE: 503,
        ErrorCode.RESOURCE_RATE_LIMITED: 429,
        ErrorCode.SERVICE_UNAVAILABLE: 503,
        ErrorCode.SERVICE_TIMEOUT: 504,
        ErrorCode.SERVICE_OVERLOADED: 503,
        ErrorCode.CIRCUIT_BREAKER_OPEN: 503,
    }
    return mapping.get(code, 500)


# Exception handler for FastAPI

def register_exception_handlers(app):
    """Register exception handlers with a FastAPI application."""
    from fastapi import Request, HTTPException
    from fastapi.responses import JSONResponse
    
    @app.exception_handler(ClawOSError)
    async def clawos_exception_handler(request: Request, exc: ClawOSError):
        exc.log()
        return JSONResponse(
            status_code=_get_http_status(exc.code),
            content=exc.to_dict(),
        )
    
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        error = handle_exception(
            exc,
            service="unknown",
            operation=request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content=error.to_dict(),
        )
