"""Configuration and data models for the Agamemnon Chaos Client."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgamemnonConfig(BaseModel):
    """Configuration for the Agamemnon Chaos Client.

    Attributes:
        base_url: Agamemnon REST API base URL.
        enabled: Whether the integration is active.
        timeout_seconds: Timeout for mutation requests (1-300).
        health_check_timeout_seconds: Timeout for health checks (1-60).
        max_retries: Retry attempts for transient failures (0-10).

    """

    base_url: str = "http://localhost:8080"
    enabled: bool = False
    timeout_seconds: int = Field(default=10, ge=1, le=300)
    health_check_timeout_seconds: int = Field(default=5, ge=1, le=60)
    max_retries: int = Field(default=3, ge=0, le=10)


class FailureSpec(BaseModel):
    """Describes a failure to inject into an agent.

    Attributes:
        agent_id: Identifier of the target agent.
        failure_type: Type of failure to inject.
        duration_seconds: How long the failure should last.
        parameters: Additional failure-specific parameters.

    """

    agent_id: str
    failure_type: str
    duration_seconds: int = Field(ge=1)
    parameters: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    """API health status response.

    Attributes:
        status: Current health status string.
        version: API version string.

    """

    status: str
    version: str


class InjectionResult(BaseModel):
    """Result of a successful failure injection.

    Attributes:
        injection_id: Unique identifier for the injection.
        status: Status of the injection.

    """

    injection_id: str
    status: str
