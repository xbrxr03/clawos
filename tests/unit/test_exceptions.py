# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unit tests for clawos_core.exceptions module."""

import pytest
from clawos_core.exceptions import (
    ClawOSError,
    AuthenticationError,
    ValidationError,
    ResourceNotFoundError,
    ServiceUnavailableError,
    CircuitBreakerError,
    DatabaseError,
    ErrorCode,
    ErrorSeverity,
    ErrorContext,
    handle_exception,
    _get_http_status,
)


class TestClawOSError:
    """Test base ClawOSError class."""
    
    def test_basic_error(self):
        error = ClawOSError("Test error")
        assert error.message == "Test error"
        assert error.code == ErrorCode.INTERNAL_UNKNOWN
        assert error.severity == ErrorSeverity.ERROR
    
    def test_error_with_context(self):
        context = ErrorContext(service="test", operation="test_op")
        error = ClawOSError("Test", context=context)
        assert error.context.service == "test"
        assert error.context.operation == "test_op"
    
    def test_error_to_dict(self):
        error = ClawOSError("Test error", code=ErrorCode.VALIDATION_ERROR)
        data = error.to_dict()
        assert data["error"]["message"] == "Test error"
        assert data["error"]["code"] == ErrorCode.VALIDATION_ERROR.value
    
    def test_error_severity_levels(self):
        for severity in ErrorSeverity:
            error = ClawOSError("Test", severity=severity)
            assert error.severity == severity


class TestSpecificErrors:
    """Test specific error types."""
    
    def test_authentication_error(self):
        error = AuthenticationError("Auth failed")
        assert error.code == ErrorCode.AUTH_UNAUTHORIZED
        assert error.severity == ErrorSeverity.WARNING
    
    def test_validation_error(self):
        error = ValidationError("Invalid input")
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert error.severity == ErrorSeverity.WARNING
    
    def test_resource_not_found_error(self):
        error = ResourceNotFoundError("Not found")
        assert error.code == ErrorCode.RESOURCE_NOT_FOUND
        assert error.severity == ErrorSeverity.WARNING
    
    def test_service_unavailable_error(self):
        error = ServiceUnavailableError("Service down")
        assert error.code == ErrorCode.SERVICE_UNAVAILABLE
        assert error.severity == ErrorSeverity.ERROR
    
    def test_circuit_breaker_error(self):
        error = CircuitBreakerError("Circuit open")
        assert error.code == ErrorCode.CIRCUIT_BREAKER_OPEN
        assert error.severity == ErrorSeverity.ERROR
    
    def test_database_error(self):
        error = DatabaseError("DB failed")
        assert error.code == ErrorCode.INTERNAL_DATABASE_ERROR
        assert error.severity == ErrorSeverity.ERROR


class TestHttpStatusMapping:
    """Test HTTP status code mapping."""
    
    def test_auth_errors_return_401(self):
        assert _get_http_status(ErrorCode.AUTH_UNAUTHORIZED) == 401
        assert _get_http_status(ErrorCode.AUTH_TOKEN_EXPIRED) == 401
    
    def test_forbidden_returns_403(self):
        assert _get_http_status(ErrorCode.AUTH_FORBIDDEN) == 403
    
    def test_not_found_returns_404(self):
        assert _get_http_status(ErrorCode.RESOURCE_NOT_FOUND) == 404
    
    def test_validation_returns_422(self):
        assert _get_http_status(ErrorCode.VALIDATION_ERROR) == 422
    
    def test_rate_limit_returns_429(self):
        assert _get_http_status(ErrorCode.RESOURCE_RATE_LIMITED) == 429
    
    def test_service_unavailable_returns_503(self):
        assert _get_http_status(ErrorCode.SERVICE_UNAVAILABLE) == 503
        assert _get_http_status(ErrorCode.CIRCUIT_BREAKER_OPEN) == 503
    
    def test_unknown_error_returns_500(self):
        assert _get_http_status(ErrorCode.INTERNAL_UNKNOWN) == 500


class TestHandleException:
    """Test exception handling utility."""
    
    def test_handles_regular_exception(self):
        original = ValueError("Something went wrong")
        result = handle_exception(original, "test_service", "test_op")
        assert isinstance(result, ClawOSError)
        assert result.message == "Something went wrong"
        assert result.context.service == "test_service"
        assert result.context.operation == "test_op"
    
    def test_preserves_clawos_error(self):
        original = ValidationError("Already a ClawOSError")
        result = handle_exception(original, "other", "other_op")
        assert result is original
