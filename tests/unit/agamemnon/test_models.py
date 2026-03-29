"""Tests for scylla.agamemnon.models."""

import pytest
from pydantic import ValidationError

from scylla.agamemnon.models import (
    AgamemnonConfig,
    FailureSpec,
    HealthResponse,
    InjectionResult,
)


class TestAgamemnonConfig:
    """Tests for AgamemnonConfig defaults and validation."""

    def test_defaults(self) -> None:
        """Default config is disabled with localhost URL."""
        config = AgamemnonConfig()
        assert config.base_url == "http://localhost:8080"
        assert config.enabled is False
        assert config.timeout_seconds == 10
        assert config.health_check_timeout_seconds == 5

    def test_custom_values(self) -> None:
        """Custom values override defaults."""
        config = AgamemnonConfig(
            base_url="http://agamemnon.example.com:8080",
            enabled=True,
            timeout_seconds=30,
            health_check_timeout_seconds=3,
        )
        assert config.base_url == "http://agamemnon.example.com:8080"
        assert config.enabled is True
        assert config.timeout_seconds == 30
        assert config.health_check_timeout_seconds == 3

    def test_timeout_minimum(self) -> None:
        """Timeout must be >= 1."""
        with pytest.raises(ValidationError):
            AgamemnonConfig(timeout_seconds=0)

    def test_timeout_maximum(self) -> None:
        """Timeout must be <= 300."""
        with pytest.raises(ValidationError):
            AgamemnonConfig(timeout_seconds=301)

    def test_health_check_timeout_maximum(self) -> None:
        """Health check timeout must be <= 60."""
        with pytest.raises(ValidationError):
            AgamemnonConfig(health_check_timeout_seconds=61)


class TestFailureSpec:
    """Tests for FailureSpec model."""

    def test_required_fields(self) -> None:
        """agent_id and failure_type are required."""
        spec = FailureSpec(agent_id="agent-1", failure_type="crash")
        assert spec.agent_id == "agent-1"
        assert spec.failure_type == "crash"
        assert spec.duration_seconds is None
        assert spec.parameters == {}

    def test_with_optional_fields(self) -> None:
        """All fields populated correctly."""
        spec = FailureSpec(
            agent_id="agent-2",
            failure_type="network_delay",
            duration_seconds=60,
            parameters={"latency_ms": 500},
        )
        assert spec.duration_seconds == 60
        assert spec.parameters == {"latency_ms": 500}

    def test_missing_required_raises(self) -> None:
        """Missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            FailureSpec()  # type: ignore[call-arg]

    def test_duration_minimum(self) -> None:
        """Duration must be >= 1 when provided."""
        with pytest.raises(ValidationError):
            FailureSpec(agent_id="a", failure_type="x", duration_seconds=0)


class TestHealthResponse:
    """Tests for HealthResponse model."""

    def test_from_dict(self) -> None:
        """Parse a health response from a dictionary."""
        resp = HealthResponse(status="ok", version="1.2.3")
        assert resp.status == "ok"
        assert resp.version == "1.2.3"

    def test_version_optional(self) -> None:
        """Version is optional and defaults to None."""
        resp = HealthResponse(status="ok")
        assert resp.version is None

    def test_missing_status_raises(self) -> None:
        """Missing status raises ValidationError."""
        with pytest.raises(ValidationError):
            HealthResponse()  # type: ignore[call-arg]


class TestInjectionResult:
    """Tests for InjectionResult model."""

    def test_from_dict(self) -> None:
        """Parse an injection result from a dictionary."""
        result = InjectionResult(injection_id="inj-001", status="active")
        assert result.injection_id == "inj-001"
        assert result.status == "active"

    def test_missing_fields_raises(self) -> None:
        """Missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            InjectionResult()  # type: ignore[call-arg]
