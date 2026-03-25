"""Shared test fixtures for maestro tests."""

import pytest

from scylla.maestro.models import MaestroConfig


@pytest.fixture
def maestro_config() -> MaestroConfig:
    """Create a test MaestroConfig with defaults."""
    return MaestroConfig(
        base_url="http://localhost:23000",
        enabled=True,
        timeout_seconds=5,
        health_check_timeout_seconds=2,
    )
