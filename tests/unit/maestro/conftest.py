"""Shared fixtures for Maestro client tests."""

import pytest

from scylla.maestro.models import MaestroConfig


@pytest.fixture
def maestro_config() -> MaestroConfig:
    """Provide a default Maestro configuration for testing.

    Returns:
        A MaestroConfig with standard test defaults.

    """
    return MaestroConfig(
        base_url="http://localhost:23000",
        enabled=True,
        timeout_seconds=10,
        health_check_timeout_seconds=5,
        max_retries=3,
    )
