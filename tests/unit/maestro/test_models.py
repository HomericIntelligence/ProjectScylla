"""Unit tests for Maestro Pydantic models."""

import pytest
from pydantic import ValidationError

from scylla.maestro.models import (
    FailureSpec,
    HealthResponse,
    InjectionResult,
    MaestroConfig,
)


class TestMaestroConfig:
    """Tests for MaestroConfig model."""

    def test_default_values(self) -> None:
        """Test that default values are correctly set."""
        config = MaestroConfig()
        assert config.base_url == "http://localhost:23000"
        assert config.enabled is False
        assert config.timeout_seconds == 10
        assert config.health_check_timeout_seconds == 5
        assert config.max_retries == 3

    def test_custom_values(self) -> None:
        """Test that custom values override defaults."""
        config = MaestroConfig(
            base_url="http://example.com:8080",
            enabled=True,
            timeout_seconds=20,
            health_check_timeout_seconds=3,
            max_retries=5,
        )
        assert config.base_url == "http://example.com:8080"
        assert config.enabled is True
        assert config.timeout_seconds == 20
        assert config.health_check_timeout_seconds == 3
        assert config.max_retries == 5

    def test_max_retries_bounds(self) -> None:
        """Test that max_retries respects the 0-10 range."""
        # Valid edge cases
        config_zero = MaestroConfig(max_retries=0)
        assert config_zero.max_retries == 0

        config_ten = MaestroConfig(max_retries=10)
        assert config_ten.max_retries == 10

        # Invalid cases
        with pytest.raises(ValidationError):
            MaestroConfig(max_retries=-1)

        with pytest.raises(ValidationError):
            MaestroConfig(max_retries=11)

    def test_timeout_bounds(self) -> None:
        """Test that timeout_seconds respects bounds."""
        # Valid edge cases
        config_one = MaestroConfig(timeout_seconds=1)
        assert config_one.timeout_seconds == 1

        config_max = MaestroConfig(timeout_seconds=300)
        assert config_max.timeout_seconds == 300

        # Invalid cases
        with pytest.raises(ValidationError):
            MaestroConfig(timeout_seconds=0)

        with pytest.raises(ValidationError):
            MaestroConfig(timeout_seconds=301)


class TestFailureSpec:
    """Tests for FailureSpec model."""

    def test_required_fields(self) -> None:
        """Test that agent_id and failure_type are required."""
        spec = FailureSpec(agent_id="agent-1", failure_type="network_delay")
        assert spec.agent_id == "agent-1"
        assert spec.failure_type == "network_delay"

    def test_missing_required_field(self) -> None:
        """Test that validation fails when required fields are missing."""
        with pytest.raises(ValidationError):
            FailureSpec(failure_type="network_delay")

        with pytest.raises(ValidationError):
            FailureSpec(agent_id="agent-1")

    def test_optional_fields(self) -> None:
        """Test optional fields with defaults."""
        spec = FailureSpec(agent_id="agent-1", failure_type="crash")
        assert spec.duration_seconds is None
        assert spec.parameters == {}

    def test_with_optional_fields(self) -> None:
        """Test setting optional fields."""
        spec = FailureSpec(
            agent_id="agent-1",
            failure_type="timeout",
            duration_seconds=30,
            parameters={"delay_ms": 500},
        )
        assert spec.duration_seconds == 30
        assert spec.parameters == {"delay_ms": 500}

    def test_duration_seconds_bounds(self) -> None:
        """Test that duration_seconds respects bounds."""
        # Valid case
        spec = FailureSpec(agent_id="agent-1", failure_type="delay", duration_seconds=1)
        assert spec.duration_seconds == 1

        # Invalid case
        with pytest.raises(ValidationError):
            FailureSpec(agent_id="agent-1", failure_type="delay", duration_seconds=0)


class TestHealthResponse:
    """Tests for HealthResponse model."""

    def test_required_status(self) -> None:
        """Test that status is required."""
        response = HealthResponse(status="ok")
        assert response.status == "ok"

    def test_missing_status(self) -> None:
        """Test that validation fails without status."""
        with pytest.raises(ValidationError):
            HealthResponse()

    def test_with_version(self) -> None:
        """Test setting optional version field."""
        response = HealthResponse(status="ok", version="1.0.0")
        assert response.status == "ok"
        assert response.version == "1.0.0"

    def test_version_none_by_default(self) -> None:
        """Test that version defaults to None."""
        response = HealthResponse(status="ok")
        assert response.version is None


class TestInjectionResult:
    """Tests for InjectionResult model."""

    def test_required_fields(self) -> None:
        """Test that injection_id and status are required."""
        result = InjectionResult(injection_id="inj-123", status="active")
        assert result.injection_id == "inj-123"
        assert result.status == "active"

    def test_missing_fields(self) -> None:
        """Test that validation fails without required fields."""
        with pytest.raises(ValidationError):
            InjectionResult(status="active")

        with pytest.raises(ValidationError):
            InjectionResult(injection_id="inj-123")
