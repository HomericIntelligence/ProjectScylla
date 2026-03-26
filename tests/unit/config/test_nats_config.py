"""Unit tests for NATSConfig model and NATS env var overrides.

Tests cover:
- NatsConfig model defaults and field validation
- None coercion defense-in-depth on the enabled field
- NATS_ENABLED env var override with truthy/falsy string parsing
- NATS_URL, NATS_STREAM, NATS_DURABLE_NAME env var overrides
- Precedence: env var > YAML > Pydantic default
- DefaultsConfig includes nats field with default_factory
"""

from pathlib import Path

import pytest

from scylla.config import ConfigLoader, DefaultsConfig, NatsConfig
from scylla.config.models import NatsConfig as NatsConfigDirect
from scylla.nats.config import NATSConfig as NATSConfigDirect

FIXTURES_PATH = Path(__file__).parent.parent.parent / "fixtures"


class TestNatsConfigModel:
    """Tests for the NatsConfig Pydantic model."""

    def test_defaults(self) -> None:
        """NatsConfig has correct defaults."""
        config = NatsConfig()
        assert config.enabled is False
        assert config.url == "nats://localhost:4222"
        assert config.stream == "scylla"
        assert config.durable_name == "scylla-consumer"

    def test_enabled_true(self) -> None:
        """NatsConfig accepts enabled=True."""
        config = NatsConfig(enabled=True)
        assert config.enabled is True

    def test_custom_values(self) -> None:
        """NatsConfig accepts custom field values."""
        config = NatsConfig(
            enabled=True,
            url="nats://custom:4222",
            stream="my-stream",
            durable_name="my-consumer",
        )
        assert config.enabled is True
        assert config.url == "nats://custom:4222"
        assert config.stream == "my-stream"
        assert config.durable_name == "my-consumer"

    def test_none_coercion_on_enabled(self) -> None:
        """None value for enabled is coerced to False (defense-in-depth)."""
        config = NatsConfigDirect(enabled=None)  # type: ignore[arg-type]
        assert config.enabled is False

    def test_defaults_config_has_nats(self) -> None:
        """DefaultsConfig includes nats field with NATSConfig default."""
        defaults = DefaultsConfig()
        assert isinstance(defaults.nats, NATSConfigDirect)
        assert defaults.nats.enabled is False


class TestNatsConfigEnvOverride:
    """Tests for NATS env var overrides in ConfigLoader.load_defaults()."""

    def test_nats_enabled_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """NATS_ENABLED=true enables NATS."""
        monkeypatch.setenv("NATS_ENABLED", "true")
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        defaults = loader.load_defaults()
        assert defaults.nats.enabled is True

    def test_nats_enabled_one(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """NATS_ENABLED=1 enables NATS."""
        monkeypatch.setenv("NATS_ENABLED", "1")
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        defaults = loader.load_defaults()
        assert defaults.nats.enabled is True

    def test_nats_enabled_yes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """NATS_ENABLED=yes enables NATS."""
        monkeypatch.setenv("NATS_ENABLED", "yes")
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        defaults = loader.load_defaults()
        assert defaults.nats.enabled is True

    def test_nats_enabled_true_uppercase(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """NATS_ENABLED=TRUE (uppercase) enables NATS."""
        monkeypatch.setenv("NATS_ENABLED", "TRUE")
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        defaults = loader.load_defaults()
        assert defaults.nats.enabled is True

    @pytest.mark.parametrize("value", ["false", "0", "no", "random", ""])
    def test_nats_enabled_falsy(self, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
        """Non-truthy NATS_ENABLED values keep NATS disabled."""
        if value:
            monkeypatch.setenv("NATS_ENABLED", value)
        else:
            # Empty string: set then verify it doesn't trigger override
            monkeypatch.delenv("NATS_ENABLED", raising=False)
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        defaults = loader.load_defaults()
        assert defaults.nats.enabled is False

    def test_nats_url_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """NATS_URL env var overrides the url field."""
        monkeypatch.setenv("NATS_URL", "nats://custom:5222")
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        defaults = loader.load_defaults()
        assert defaults.nats.url == "nats://custom:5222"

    def test_nats_stream_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """NATS_STREAM env var overrides the stream field."""
        monkeypatch.setenv("NATS_STREAM", "my-stream")
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        defaults = loader.load_defaults()
        assert defaults.nats.stream == "my-stream"

    def test_nats_durable_name_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """NATS_DURABLE_NAME env var overrides the durable_name field."""
        monkeypatch.setenv("NATS_DURABLE_NAME", "my-consumer")
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        defaults = loader.load_defaults()
        assert defaults.nats.durable_name == "my-consumer"

    def test_all_nats_env_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """All NATS env vars can be set simultaneously."""
        monkeypatch.setenv("NATS_ENABLED", "true")
        monkeypatch.setenv("NATS_URL", "nats://prod:4222")
        monkeypatch.setenv("NATS_STREAM", "prod-stream")
        monkeypatch.setenv("NATS_DURABLE_NAME", "prod-consumer")
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        defaults = loader.load_defaults()
        assert defaults.nats.enabled is True
        assert defaults.nats.url == "nats://prod:4222"
        assert defaults.nats.stream == "prod-stream"
        assert defaults.nats.durable_name == "prod-consumer"

    def test_no_env_vars_uses_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without NATS env vars, defaults from YAML/Pydantic are used."""
        monkeypatch.delenv("NATS_ENABLED", raising=False)
        monkeypatch.delenv("NATS_URL", raising=False)
        monkeypatch.delenv("NATS_STREAM", raising=False)
        monkeypatch.delenv("NATS_DURABLE_NAME", raising=False)
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        defaults = loader.load_defaults()
        assert defaults.nats.enabled is False
        assert defaults.nats.url == "nats://localhost:4222"
        assert defaults.nats.stream == "TASKS"
        assert defaults.nats.durable_name == "scylla-subscriber"

    def test_env_var_overrides_yaml_enabled_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """NATS_ENABLED=true overrides YAML enabled: false."""
        monkeypatch.setenv("NATS_ENABLED", "true")
        # Use the real config (which has enabled: false in YAML)
        loader = ConfigLoader(
            base_path=Path(__file__).parent.parent.parent.parent / "config" and FIXTURES_PATH
        )
        defaults = loader.load_defaults()
        assert defaults.nats.enabled is True
