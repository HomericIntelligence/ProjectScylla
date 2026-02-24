"""Tests for tier configuration loading."""

from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scylla.executor.tier_config import (
    TierConfig,
    TierConfigError,
    TierConfigLoader,
    TierDefinition,
    TiersDefinitionFile,
)


class TestTierDefinition:
    """Tests for the TierDefinition model."""

    def test_tier_definition_with_all_fields(self) -> None:
        """Test creating a tier definition with all fields."""
        tier = TierDefinition(
            name="Test Tier",
            description="A test tier",
            tools_enabled=True,
            delegation_enabled=False,
        )
        assert tier.name == "Test Tier"
        assert tier.description == "A test tier"
        assert tier.tools_enabled is True
        assert tier.delegation_enabled is False

    def test_tier_definition_with_defaults(self) -> None:
        """Test creating a tier definition with default values."""
        tier = TierDefinition(
            name="Vanilla",
            description="Base tier",
            tools_enabled=None,
            delegation_enabled=None,
        )
        assert tier.name == "Vanilla"
        assert tier.description == "Base tier"
        assert tier.tools_enabled is None
        assert tier.delegation_enabled is None


class TestTiersDefinitionFile:
    """Tests for the TiersDefinitionFile model."""

    def test_valid_tiers_definition(self) -> None:
        """Test validating a complete tiers definition."""
        tiers_def = TiersDefinitionFile(
            tiers={
                "T0": TierDefinition(
                    name="Prompts",
                    description="System prompt ablation",
                    tools_enabled=None,
                    delegation_enabled=None,
                ),
                "T1": TierDefinition(
                    name="Skills",
                    description="Domain expertise",
                    tools_enabled=None,
                    delegation_enabled=None,
                ),
                "T2": TierDefinition(
                    name="Tooling",
                    description="External tools and MCP",
                    tools_enabled=None,
                    delegation_enabled=None,
                ),
                "T3": TierDefinition(
                    name="Delegation",
                    description="Flat multi-agent",
                    tools_enabled=None,
                    delegation_enabled=None,
                ),
                "T4": TierDefinition(
                    name="Hierarchy",
                    description="Nested orchestration",
                    tools_enabled=None,
                    delegation_enabled=None,
                ),
                "T5": TierDefinition(
                    name="Hybrid",
                    description="Best combinations",
                    tools_enabled=None,
                    delegation_enabled=None,
                ),
                "T6": TierDefinition(
                    name="Super",
                    description="Everything enabled",
                    tools_enabled=None,
                    delegation_enabled=None,
                ),
            }
        )
        assert len(tiers_def.tiers) == 7

    def test_missing_required_tiers(self) -> None:
        """Test that missing required tiers raises error."""
        with pytest.raises(ValueError, match="Missing required tier definitions"):
            TiersDefinitionFile(
                tiers={
                    "T0": TierDefinition(
                        name="Vanilla",
                        description="Base",
                        tools_enabled=None,
                        delegation_enabled=None,
                    ),
                    "T1": TierDefinition(
                        name="Prompted",
                        description="With prompts",
                        tools_enabled=None,
                        delegation_enabled=None,
                    ),
                }
            )


class TestTierConfig:
    """Tests for the TierConfig model."""

    def test_tier_config_with_tools(self) -> None:
        """Test creating a tier config with tools enabled."""
        config = TierConfig(
            tier_id="T1",
            name="Skills",
            description="Domain expertise",
            tools_enabled=False,
            delegation_enabled=False,
        )
        assert config.tier_id == "T1"
        assert config.tools_enabled is False

    def test_tier_config_defaults(self) -> None:
        """Test creating a tier config with default values (T0 style)."""
        config = TierConfig(
            tier_id="T0",
            name="Vanilla",
            description="Base LLM",
            tools_enabled=None,
            delegation_enabled=None,
        )
        assert config.tier_id == "T0"
        assert config.tools_enabled is None
        assert config.delegation_enabled is None


class TestTierConfigLoader:
    """Tests for the TierConfigLoader class."""

    @pytest.fixture
    def tiers_dir(self) -> Generator[Path, None, None]:
        """Create a temporary directory with tiers.yaml."""
        with TemporaryDirectory() as tmpdir:
            tiers_dir = Path(tmpdir)

            # Create tiers.yaml with new tier structure (no prompt_file)
            tiers_yaml = tiers_dir / "tiers.yaml"
            tiers_yaml.write_text("""
tiers:
  T0:
    name: "Prompts"
    description: "System prompt ablation"
    tools_enabled: null
    delegation_enabled: false

  T1:
    name: "Skills"
    description: "Domain expertise via installed skills"
    tools_enabled: null
    delegation_enabled: false

  T2:
    name: "Tooling"
    description: "External tools and MCP servers"
    tools_enabled: true
    delegation_enabled: false

  T3:
    name: "Delegation"
    description: "Flat multi-agent with specialist agents"
    tools_enabled: true
    delegation_enabled: true

  T4:
    name: "Hierarchy"
    description: "Nested orchestration with orchestrators"
    tools_enabled: true
    delegation_enabled: true

  T5:
    name: "Hybrid"
    description: "Best combinations and permutations"
    tools_enabled: true
    delegation_enabled: true

  T6:
    name: "Super"
    description: "Everything enabled at maximum capability"
    tools_enabled: true
    delegation_enabled: true
""")

            yield tiers_dir

    def test_load_tiers_successfully(self, tiers_dir: Path) -> None:
        """Test loading tier configurations successfully."""
        loader = TierConfigLoader(tiers_dir)
        assert len(loader.get_tier_ids()) == 7

    def test_get_t0_tier(self, tiers_dir: Path) -> None:
        """Test getting T0 tier (Prompts)."""
        loader = TierConfigLoader(tiers_dir)
        t0 = loader.get_tier("T0")

        assert t0.tier_id == "T0"
        assert t0.name == "Prompts"
        assert t0.tools_enabled is None
        assert t0.delegation_enabled is False

    def test_get_t1_tier(self, tiers_dir: Path) -> None:
        """Test getting T1 tier (Skills)."""
        loader = TierConfigLoader(tiers_dir)
        t1 = loader.get_tier("T1")

        assert t1.tier_id == "T1"
        assert t1.name == "Skills"
        assert t1.tools_enabled is None
        assert t1.delegation_enabled is False

    def test_get_t2_tier(self, tiers_dir: Path) -> None:
        """Test getting T2 tier (Tooling) with tools enabled but no delegation."""
        loader = TierConfigLoader(tiers_dir)
        t2 = loader.get_tier("T2")

        assert t2.tier_id == "T2"
        assert t2.name == "Tooling"
        assert t2.tools_enabled is True
        assert t2.delegation_enabled is False  # T2 has tools but no delegation

    def test_get_all_tiers(self, tiers_dir: Path) -> None:
        """Test getting all tier configurations."""
        loader = TierConfigLoader(tiers_dir)
        all_tiers = loader.get_all_tiers()

        assert len(all_tiers) == 7
        tier_ids = [t.tier_id for t in all_tiers]
        assert set(tier_ids) == {"T0", "T1", "T2", "T3", "T4", "T5", "T6"}

    def test_get_tier_ids(self, tiers_dir: Path) -> None:
        """Test getting list of tier IDs."""
        loader = TierConfigLoader(tiers_dir)
        tier_ids = loader.get_tier_ids()

        assert len(tier_ids) == 7
        assert "T0" in tier_ids
        assert "T6" in tier_ids

    def test_validate_tier_id_valid(self, tiers_dir: Path) -> None:
        """Test validating a valid tier ID."""
        loader = TierConfigLoader(tiers_dir)
        assert loader.validate_tier_id("T0") is True
        assert loader.validate_tier_id("T3") is True

    def test_validate_tier_id_invalid(self, tiers_dir: Path) -> None:
        """Test validating an invalid tier ID."""
        loader = TierConfigLoader(tiers_dir)
        assert loader.validate_tier_id("T99") is False
        assert loader.validate_tier_id("invalid") is False

    def test_unknown_tier_raises_error(self, tiers_dir: Path) -> None:
        """Test that requesting unknown tier raises error."""
        loader = TierConfigLoader(tiers_dir)
        with pytest.raises(TierConfigError, match="Unknown tier"):
            loader.get_tier("T99")

    def test_missing_tiers_file_raises_error(self) -> None:
        """Test that missing tiers.yaml raises error."""
        with TemporaryDirectory() as tmpdir:
            with pytest.raises(TierConfigError, match="Tiers file not found"):
                TierConfigLoader(Path(tmpdir))

    def test_invalid_yaml_raises_error(self) -> None:
        """Test that invalid YAML raises error."""
        with TemporaryDirectory() as tmpdir:
            tiers_dir = Path(tmpdir)

            # Create invalid YAML
            tiers_yaml = tiers_dir / "tiers.yaml"
            tiers_yaml.write_text("invalid: yaml: content: [")

            with pytest.raises(TierConfigError, match="Failed to parse"):
                TierConfigLoader(tiers_dir)


class TestTierConfigLoaderWithActualConfig:
    """Integration tests using actual config files."""

    def test_load_actual_config(self) -> None:
        """Test loading the actual tier configuration."""
        # This test uses the actual shared tiers directory
        tiers_dir = Path(__file__).parent.parent.parent.parent / "tests" / "claude-code" / "shared"

        loader = TierConfigLoader(tiers_dir)

        # Verify all tiers can be loaded
        all_tiers = loader.get_all_tiers()
        assert len(all_tiers) == 7  # T0-T6

        # Verify T0 (Prompts)
        t0 = loader.get_tier("T0")
        assert t0.name == "Prompts"
        assert t0.tools_enabled is None

        # Verify T1 (Skills)
        t1 = loader.get_tier("T1")
        assert t1.name == "Skills"

        # Verify T6 (Super) exists
        t6 = loader.get_tier("T6")
        assert t6.name == "Super"
