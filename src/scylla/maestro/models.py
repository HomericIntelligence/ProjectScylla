"""Pydantic models for AI Maestro REST API integration.

Defines configuration, request, and response models used by MaestroClient.
"""

from typing import Any

from pydantic import BaseModel, Field


class MaestroConfig(BaseModel):
    """Configuration for the AI Maestro REST API connection.

    When ``enabled`` is ``False`` (the default), the client is not instantiated
    and no HTTP calls are made.  This keeps the integration fully opt-in.
    """

    base_url: str = Field(
        default="http://localhost:23000",
        description="Base URL for the Maestro REST API",
    )
    enabled: bool = Field(
        default=False,
        description="Whether to activate the Maestro integration",
    )
    timeout_seconds: int = Field(
        default=10,
        ge=1,
        le=300,
        description="Timeout in seconds for mutation requests",
    )
    health_check_timeout_seconds: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Timeout in seconds for health-check requests",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts for transient network failures (0 disables retry)",
    )


class FailureSpec(BaseModel):
    """Specification for a failure to inject via the Maestro API.

    Attributes:
        agent_id: Target agent identifier.
        failure_type: Kind of failure (e.g. ``network_delay``, ``crash``, ``timeout``).
        duration_seconds: Optional duration; ``None`` means permanent until cleared.
        parameters: Arbitrary key-value parameters for the failure type.

    """

    agent_id: str = Field(..., description="Target agent identifier")
    failure_type: str = Field(..., description="Kind of failure to inject")
    duration_seconds: int | None = Field(
        default=None,
        ge=1,
        description="Duration in seconds; None means permanent until cleared",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Extra parameters for the failure type",
    )


class HealthResponse(BaseModel):
    """Response model for the Maestro health endpoint."""

    status: str = Field(..., description="Health status string (e.g. 'ok')")
    version: str | None = Field(default=None, description="API version string")


class InjectionResult(BaseModel):
    """Response model for a successful failure injection."""

    injection_id: str = Field(..., description="Unique identifier for this injection")
    status: str = Field(..., description="Injection status (e.g. 'active')")
