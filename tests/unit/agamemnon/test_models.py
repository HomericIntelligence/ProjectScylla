"""Tests for Agamemnon data models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from scylla.agamemnon.models import (
    AgamemnonConfig,
    FailureSpec,
    HealthResponse,
    InjectionResult,
)


class TestAgamemnonConfig:
    """Tests for AgamemnonConfig."""

    def test_defaults(self) -> None:
        """Verify default field values."""
        config = AgamemnonConfig()
        assert config.base_url == "http://localhost:8080"
        assert config.enabled is False
        assert config.timeout_seconds == 10
        assert config.health_check_timeout_seconds == 5
        assert config.max_retries == 3

    def test_custom_values(self) -> None:
        """Verify custom field values are accepted."""
        config = AgamemnonConfig(
            base_url="http://agamemnon:9090",
            enabled=True,
            timeout_seconds=30,
            health_check_timeout_seconds=15,
            max_retries=5,
        )
        assert config.base_url == "http://agamemnon:9090"
        assert config.enabled is True
        assert config.timeout_seconds == 30
        assert config.health_check_timeout_seconds == 15
        assert config.max_retries == 5

    def test_timeout_out_of_range(self) -> None:
        """Verify out-of-range timeout values are rejected."""
        with pytest.raises(ValidationError):
            AgamemnonConfig(timeout_seconds=0)
        with pytest.raises(ValidationError):
            AgamemnonConfig(timeout_seconds=301)

    def test_retries_out_of_range(self) -> None:
        """Verify out-of-range retry values are rejected."""
        with pytest.raises(ValidationError):
            AgamemnonConfig(max_retries=-1)
        with pytest.raises(ValidationError):
            AgamemnonConfig(max_retries=11)


class TestFailureSpec:
    """Tests for FailureSpec."""

    def test_minimal(self) -> None:
        """Verify minimal FailureSpec construction."""
        spec = FailureSpec(
            agent_id="agent-1",
            failure_type="latency",
            duration_seconds=60,
        )
        assert spec.agent_id == "agent-1"
        assert spec.failure_type == "latency"
        assert spec.duration_seconds == 60
        assert spec.parameters == {}

    def test_with_parameters(self) -> None:
        """Verify FailureSpec with custom parameters."""
        spec = FailureSpec(
            agent_id="agent-2",
            failure_type="error",
            duration_seconds=120,
            parameters={"error_rate": 0.5},
        )
        assert spec.parameters == {"error_rate": 0.5}

    def test_duration_must_be_positive(self) -> None:
        """Verify zero duration is rejected."""
        with pytest.raises(ValidationError):
            FailureSpec(
                agent_id="agent-1",
                failure_type="latency",
                duration_seconds=0,
            )


class TestHealthResponse:
    """Tests for HealthResponse."""

    def test_construction(self) -> None:
        """Verify HealthResponse field values."""
        hr = HealthResponse(status="ok", version="1.0.0")
        assert hr.status == "ok"
        assert hr.version == "1.0.0"


class TestInjectionResult:
    """Tests for InjectionResult."""

    def test_construction(self) -> None:
        """Verify InjectionResult field values."""
        result = InjectionResult(injection_id="inj-123", status="active")
        assert result.injection_id == "inj-123"
        assert result.status == "active"
