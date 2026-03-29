"""Shared test fixtures for agamemnon tests."""

import pytest

from scylla.agamemnon.models import AgamemnonConfig


@pytest.fixture
def agamemnon_config() -> AgamemnonConfig:
    """Create a test AgamemnonConfig with defaults."""
    return AgamemnonConfig(
        base_url="http://localhost:8080",
        enabled=True,
        timeout_seconds=5,
        health_check_timeout_seconds=2,
    )
