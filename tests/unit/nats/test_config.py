"""Tests for scylla.nats.config module."""

from typing import Any
from unittest.mock import patch

import pytest

from scylla.nats.config import NATSConfig, load_nats_config


class TestNATSConfig:
    """Test NATSConfig Pydantic model defaults and validation."""

    def test_defaults(self) -> None:
        """All fields have sensible defaults."""
        config = NATSConfig()
        assert config.enabled is False
        assert config.url == "nats://localhost:4222"
        assert config.stream == "TASKS"
        assert config.subjects == ["hi.tasks.>"]
        assert config.durable_name == "scylla-subscriber"
        assert config.deliver_policy == "new"

    def test_custom_values(self) -> None:
        """Custom values are accepted and stored."""
        config = NATSConfig(
            enabled=True,
            url="nats://custom:4222",
            stream="EVENTS",
            subjects=["hi.events.>"],
            durable_name="custom-consumer",
            deliver_policy="all",
        )
        assert config.enabled is True
        assert config.url == "nats://custom:4222"
        assert config.stream == "EVENTS"
        assert config.subjects == ["hi.events.>"]
        assert config.durable_name == "custom-consumer"
        assert config.deliver_policy == "all"

    def test_model_serialization_roundtrip(self) -> None:
        """Model can be serialized and deserialized without loss."""
        config = NATSConfig(enabled=True, url="nats://test:4222")
        data = config.model_dump()
        restored = NATSConfig(**data)
        assert restored == config


class TestLoadNATSConfig:
    """Test load_nats_config with YAML dict and env var overrides."""

    def test_from_yaml_dict(self) -> None:
        """YAML dict values are loaded correctly."""
        yaml_data: dict[str, Any] = {
            "enabled": True,
            "url": "nats://yaml:4222",
            "stream": "YAML_STREAM",
        }
        config = load_nats_config(yaml_data, env_override=False)
        assert config.enabled is True
        assert config.url == "nats://yaml:4222"
        assert config.stream == "YAML_STREAM"
        assert config.durable_name == "scylla-subscriber"

    def test_empty_yaml_uses_defaults(self) -> None:
        """Empty YAML dict falls back to model defaults."""
        config = load_nats_config({}, env_override=False)
        assert config.enabled is False
        assert config.url == "nats://localhost:4222"

    @patch.dict("os.environ", {"NATS_URL": "nats://env:4222"})
    def test_env_override_url(self) -> None:
        """NATS_URL env var overrides the url field."""
        config = load_nats_config({"enabled": True}, env_override=True)
        assert config.url == "nats://env:4222"

    @patch.dict("os.environ", {"NATS_STREAM": "ENV_STREAM"})
    def test_env_override_stream(self) -> None:
        """NATS_STREAM env var overrides the stream field."""
        config = load_nats_config({}, env_override=True)
        assert config.stream == "ENV_STREAM"

    @patch.dict("os.environ", {"NATS_DURABLE_NAME": "env-consumer"})
    def test_env_override_durable_name(self) -> None:
        """NATS_DURABLE_NAME env var overrides the durable_name field."""
        config = load_nats_config({}, env_override=True)
        assert config.durable_name == "env-consumer"

    @patch.dict(
        "os.environ",
        {"NATS_URL": "nats://env:4222", "NATS_STREAM": "ENV_STREAM"},
    )
    def test_env_overrides_yaml(self) -> None:
        """Env vars take precedence over YAML values."""
        yaml_data: dict[str, Any] = {
            "url": "nats://yaml:4222",
            "stream": "YAML_STREAM",
        }
        config = load_nats_config(yaml_data, env_override=True)
        assert config.url == "nats://env:4222"
        assert config.stream == "ENV_STREAM"

    def test_env_override_disabled(self) -> None:
        """Env vars are ignored when env_override=False."""
        with patch.dict("os.environ", {"NATS_URL": "nats://env:4222"}):
            config = load_nats_config({"url": "nats://yaml:4222"}, env_override=False)
            assert config.url == "nats://yaml:4222"

    @pytest.mark.parametrize(
        "env_var,field",
        [
            ("NATS_URL", "url"),
            ("NATS_STREAM", "stream"),
            ("NATS_DURABLE_NAME", "durable_name"),
        ],
    )
    def test_empty_env_var_does_not_override(self, env_var: str, field: str) -> None:
        """Empty string env vars should not override YAML values."""
        yaml_data: dict[str, Any] = {
            "url": "nats://yaml:4222",
            "stream": "YAML_STREAM",
            "durable_name": "yaml-consumer",
        }
        with patch.dict("os.environ", {env_var: ""}):
            config = load_nats_config(yaml_data, env_override=True)
            assert getattr(config, field) == yaml_data[field]
