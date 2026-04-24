"""Data models for the Agamemnon chaos fault injection client.

Defines configuration, request, and response models used by both
the synchronous and asynchronous client implementations.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgamemnonConfig(BaseModel):
    """Configuration for the Agamemnon chaos client."""

    base_url: str = Field(
        default="http://localhost:8080",
        description="Agamemnon REST API base URL",
    )
    enabled: bool = Field(
        default=False,
        description="Whether Agamemnon integration is active",
    )
    timeout_seconds: int = Field(
        default=10,
        ge=1,
        le=300,
        description="Timeout for mutation requests",
    )
    health_check_timeout_seconds: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Timeout for health checks",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Retry attempts for transient failures",
    )


class FailureSpec(BaseModel):
    """Specification for a chaos failure to inject."""

    agent_id: str = Field(..., description="Target agent identifier")
    failure_type: str = Field(..., description="Type of failure to inject")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional failure parameters",
    )


class HealthResponse(BaseModel):
    """Response from the Agamemnon health endpoint."""

    status: str = Field(..., description="Health status string")
    version: str = Field(default="", description="Server version")


class InjectionResult(BaseModel):
    """Result of a successful fault injection."""

    injection_id: str = Field(..., description="Unique identifier for the injection")
    status: str = Field(..., description="Injection status")
