"""Tests for tier configuration loading.

Python justification: Required for pytest testing framework.
"""

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
            prompt_file="test.md",
            tools_enabled=True,
            delegation_enabled=False,
        )
        assert tier.name == "Test Tier"
        assert tier.description == "A test tier"
        assert tier.prompt_file == "test.md"
        assert tier.tools_enabled is True
        assert tier.delegation_enabled is False

    def test_tier_definition_with_defaults(self) -> None:
        """Test creating a tier definition with default values."""
        tier = TierDefinition(
            name="Vanilla",
            description="Base tier",
        )
        assert tier.name == "Vanilla"
        assert tier.description == "Base tier"
        assert tier.prompt_file is None
        assert tier.tools_enabled is None
        assert tier.delegation_enabled is None


class TestTiersDefinitionFile:
    """Tests for the TiersDefinitionFile model."""

    def test_valid_tiers_definition(self) -> None:
        """Test validating a complete tiers definition."""
        tiers_def = TiersDefinitionFile(
            tiers={
                "T0": TierDefinition(name="Prompts", description="System prompt ablation"),
                "T1": TierDefinition(name="Skills", description="Domain expertise"),
                "T2": TierDefinition(name="Tooling", description="External tools and MCP"),
                "T3": TierDefinition(name="Delegation", description="Flat multi-agent"),
                "T4": TierDefinition(name="Hierarchy", description="Nested orchestration"),
                "T5": TierDefinition(name="Hybrid", description="Best combinations"),
                "T6": TierDefinition(name="Super", description="Everything enabled"),
            }
        )
        assert len(tiers_def.tiers) == 7

    def test_missing_required_tiers(self) -> None:
        """Test that missing required tiers raises error."""
        with pytest.raises(ValueError, match="Missing required tier definitions"):
            TiersDefinitionFile(
                tiers={
                    "T0": TierDefinition(name="Vanilla", description="Base"),
                    "T1": TierDefinition(name="Prompted", description="With prompts"),
                }
            )


class TestTierConfig:
    """Tests for the TierConfig model."""

    def test_tier_config_with_prompt(self) -> None:
        """Test creating a tier config with prompt content."""
        config = TierConfig(
            tier_id="T1",
            name="Prompted",
            description="With chain-of-thought",
            prompt_file=Path("/config/tiers/t1.md"),
            prompt_content="Think step by step",
            tools_enabled=False,
            delegation_enabled=False,
        )
        assert config.tier_id == "T1"
        assert config.prompt_content == "Think step by step"

    def test_tier_config_without_prompt(self) -> None:
        """Test creating a tier config without prompt (T0 style)."""
        config = TierConfig(
            tier_id="T0",
            name="Vanilla",
            description="Base LLM",
            prompt_file=None,
            prompt_content=None,
            tools_enabled=None,
            delegation_enabled=None,
        )
        assert config.tier_id == "T0"
        assert config.prompt_file is None
        assert config.prompt_content is None


class TestTierConfigLoader:
    """Tests for the TierConfigLoader class."""

    @pytest.fixture
    def config_dir(self) -> Path:
        """Create a temporary config directory with tier files."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir)
            tiers_dir = config_path / "tiers"
            tiers_dir.mkdir(parents=True)

            # Create tiers.yaml with new tier structure
            tiers_yaml = tiers_dir / "tiers.yaml"
            tiers_yaml.write_text("""
tiers:
  T0:
    name: "Prompts"
    description: "System prompt ablation"
    prompt_file: "t0-prompts.md"
    tools_enabled: null
    delegation_enabled: false

  T1:
    name: "Skills"
    description: "Domain expertise via installed skills"
    prompt_file: "t1-skills.md"
    tools_enabled: null
    delegation_enabled: false

  T2:
    name: "Tooling"
    description: "External tools and MCP servers"
    prompt_file: "t2-tooling.md"
    tools_enabled: true
    delegation_enabled: false

  T3:
    name: "Delegation"
    description: "Flat multi-agent with specialist agents"
    prompt_file: "t3-delegation.md"
    tools_enabled: true
    delegation_enabled: true

  T4:
    name: "Hierarchy"
    description: "Nested orchestration with orchestrators"
    prompt_file: "t4-hierarchy.md"
    tools_enabled: true
    delegation_enabled: true

  T5:
    name: "Hybrid"
    description: "Best combinations and permutations"
    prompt_file: "t5-hybrid.md"
    tools_enabled: true
    delegation_enabled: true

  T6:
    name: "Super"
    description: "Everything enabled at maximum capability"
    prompt_file: "t6-super.md"
    tools_enabled: true
    delegation_enabled: true
""")

            # Create prompt files
            (tiers_dir / "t0-prompts.md").write_text("System prompt ablation tier.")
            (tiers_dir / "t1-skills.md").write_text("You have domain expertise.")
            (tiers_dir / "t2-tooling.md").write_text("Use tools as needed.")
            (tiers_dir / "t3-delegation.md").write_text("Delegate to specialists.")
            (tiers_dir / "t4-hierarchy.md").write_text("Use hierarchical orchestration.")
            (tiers_dir / "t5-hybrid.md").write_text("Combine optimal components.")
            (tiers_dir / "t6-super.md").write_text("Maximum capability mode.")

            yield config_path

    def test_load_tiers_successfully(self, config_dir: Path) -> None:
        """Test loading tier configurations successfully."""
        loader = TierConfigLoader(config_dir)
        assert len(loader.get_tier_ids()) == 7

    def test_get_t0_tier(self, config_dir: Path) -> None:
        """Test getting T0 tier (Prompts) with prompt file."""
        loader = TierConfigLoader(config_dir)
        t0 = loader.get_tier("T0")

        assert t0.tier_id == "T0"
        assert t0.name == "Prompts"
        assert t0.prompt_file is not None
        assert t0.prompt_content == "System prompt ablation tier."
        assert t0.tools_enabled is None
        assert t0.delegation_enabled is False

    def test_get_t1_tier_with_prompt(self, config_dir: Path) -> None:
        """Test getting T1 tier (Skills) with prompt content loaded."""
        loader = TierConfigLoader(config_dir)
        t1 = loader.get_tier("T1")

        assert t1.tier_id == "T1"
        assert t1.name == "Skills"
        assert t1.prompt_file is not None
        assert t1.prompt_content == "You have domain expertise."
        assert t1.tools_enabled is None
        assert t1.delegation_enabled is False

    def test_get_t2_tier(self, config_dir: Path) -> None:
        """Test getting T2 tier (Tooling) with tools enabled but no delegation."""
        loader = TierConfigLoader(config_dir)
        t2 = loader.get_tier("T2")

        assert t2.tier_id == "T2"
        assert t2.name == "Tooling"
        assert t2.tools_enabled is True
        assert t2.delegation_enabled is False  # T2 has tools but no delegation

    def test_get_all_tiers(self, config_dir: Path) -> None:
        """Test getting all tier configurations."""
        loader = TierConfigLoader(config_dir)
        all_tiers = loader.get_all_tiers()

        assert len(all_tiers) == 7
        tier_ids = [t.tier_id for t in all_tiers]
        assert set(tier_ids) == {"T0", "T1", "T2", "T3", "T4", "T5", "T6"}

    def test_get_tier_ids(self, config_dir: Path) -> None:
        """Test getting list of tier IDs."""
        loader = TierConfigLoader(config_dir)
        tier_ids = loader.get_tier_ids()

        assert len(tier_ids) == 7
        assert "T0" in tier_ids
        assert "T6" in tier_ids

    def test_validate_tier_id_valid(self, config_dir: Path) -> None:
        """Test validating a valid tier ID."""
        loader = TierConfigLoader(config_dir)
        assert loader.validate_tier_id("T0") is True
        assert loader.validate_tier_id("T3") is True

    def test_validate_tier_id_invalid(self, config_dir: Path) -> None:
        """Test validating an invalid tier ID."""
        loader = TierConfigLoader(config_dir)
        assert loader.validate_tier_id("T99") is False
        assert loader.validate_tier_id("invalid") is False

    def test_unknown_tier_raises_error(self, config_dir: Path) -> None:
        """Test that requesting unknown tier raises error."""
        loader = TierConfigLoader(config_dir)
        with pytest.raises(TierConfigError, match="Unknown tier"):
            loader.get_tier("T99")

    def test_missing_tiers_file_raises_error(self) -> None:
        """Test that missing tiers.yaml raises error."""
        with TemporaryDirectory() as tmpdir:
            with pytest.raises(TierConfigError, match="Tiers file not found"):
                TierConfigLoader(Path(tmpdir))

    def test_missing_prompt_file_raises_error(self) -> None:
        """Test that missing prompt file raises error."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir)
            tiers_dir = config_path / "tiers"
            tiers_dir.mkdir(parents=True)

            # Create tiers.yaml with missing prompt file
            tiers_yaml = tiers_dir / "tiers.yaml"
            tiers_yaml.write_text("""
tiers:
  T0:
    name: "Vanilla"
    description: "Base"

  T1:
    name: "Prompted"
    description: "With prompts"
    prompt_file: "missing.md"

  T2:
    name: "Skills"
    description: "With skills"

  T3:
    name: "Tooling"
    description: "With tools"

  T4:
    name: "Delegation"
    description: "Multi-agent"

  T5:
    name: "Hierarchy"
    description: "Nested"

  T6:
    name: "Hybrid"
    description: "Optimal"
""")

            loader = TierConfigLoader(config_path)
            # T0 should work
            t0 = loader.get_tier("T0")
            assert t0.tier_id == "T0"

            # T1 should fail due to missing prompt file
            with pytest.raises(TierConfigError, match="Prompt file not found"):
                loader.get_tier("T1")

    def test_invalid_yaml_raises_error(self) -> None:
        """Test that invalid YAML raises error."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir)
            tiers_dir = config_path / "tiers"
            tiers_dir.mkdir(parents=True)

            # Create invalid YAML
            tiers_yaml = tiers_dir / "tiers.yaml"
            tiers_yaml.write_text("invalid: yaml: content: [")

            with pytest.raises(TierConfigError, match="Failed to parse"):
                TierConfigLoader(config_path)


class TestTierConfigLoaderWithActualConfig:
    """Integration tests using actual config files."""

    def test_load_actual_config(self) -> None:
        """Test loading the actual tier configuration."""
        # This test uses the actual config directory
        config_dir = Path(__file__).parent.parent.parent.parent / "config"

        if not (config_dir / "tiers" / "tiers.yaml").exists():
            pytest.skip("Actual config not available")

        loader = TierConfigLoader(config_dir)

        # Verify all tiers can be loaded
        all_tiers = loader.get_all_tiers()
        assert len(all_tiers) == 7  # T0-T6

        # Verify T0 (Prompts) has prompt content
        t0 = loader.get_tier("T0")
        assert t0.name == "Prompts"
        assert t0.prompt_content is not None

        # Verify T1 (Skills) has prompts
        t1 = loader.get_tier("T1")
        assert t1.name == "Skills"
        assert t1.prompt_content is not None
        assert len(t1.prompt_content) > 0

        # Verify T6 (Super) exists and has prompts
        t6 = loader.get_tier("T6")
        assert t6.name == "Super"
        assert t6.prompt_content is not None
