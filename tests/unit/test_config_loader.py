"""Unit tests for the configuration loading system.

Tests cover:
- Loading defaults configuration
- Loading test cases and rubrics
- Loading tier configurations
- Loading model configurations
- Merged configuration with priority hierarchy
- Error handling for invalid/missing configurations
- Filename/model_id validation
"""

import logging
from pathlib import Path

import pytest

from scylla.config import (
    ConfigLoader,
    ConfigurationError,
    DefaultsConfig,
    EvalCase,
    ModelConfig,
    Requirement,
    Rubric,
    ScyllaConfig,
    TierConfig,
)
from scylla.metrics.grading import DEFAULT_PASS_THRESHOLD

# Path to test fixtures
FIXTURES_PATH = Path(__file__).parent.parent / "fixtures"


class TestConfigLoaderDefaults:
    """Tests for loading defaults configuration."""

    def test_load_defaults(self) -> None:
        """Load defaults.yaml successfully."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        defaults = loader.load_defaults()

        assert isinstance(defaults, DefaultsConfig)
        assert defaults.evaluation.runs_per_tier == 10
        assert defaults.evaluation.timeout == 300
        assert defaults.output.runs_dir == "runs"
        assert defaults.logging.level == "INFO"

    def test_load_defaults_missing_file(self) -> None:
        """Missing defaults.yaml raises ConfigurationError."""
        loader = ConfigLoader(base_path=Path("/nonexistent"))

        with pytest.raises(ConfigurationError, match="not found"):
            loader.load_defaults()

    def test_load_defaults_invalid_yaml(self) -> None:
        """Malformed YAML raises ConfigurationError."""
        loader = ConfigLoader(base_path=FIXTURES_PATH / "invalid")

        with pytest.raises(ConfigurationError, match="Invalid YAML"):
            loader.load_defaults()


class TestConfigLoaderEvalCase:
    """Tests for loading test case configurations."""

    def test_load_test(self) -> None:
        """Load test.yaml successfully."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        test = loader.load_test("test-001")

        assert isinstance(test, EvalCase)
        assert test.id == "test-001"
        assert test.name == "Hello World Task"
        assert test.source.repo == "https://github.com/mvillmow/Hello-World"
        assert test.source.hash == "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"
        assert test.task.prompt_file == "prompt.md"
        assert test.task.timeout_seconds == 300

    def test_load_test_missing(self) -> None:
        """Missing test raises ConfigurationError."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)

        with pytest.raises(ConfigurationError, match="not found"):
            loader.load_test("nonexistent-test")

    def test_load_test_with_defaults(self) -> None:
        """Test case uses default values for optional fields."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        test = loader.load_test("test-001")

        # ValidationConfig should use defaults
        assert test.validation.criteria_file == "expected/criteria.md"
        assert test.validation.rubric_file == "expected/rubric.yaml"


class TestConfigLoaderRubric:
    """Tests for loading rubric configurations."""

    def test_load_rubric(self) -> None:
        """Load rubric.yaml successfully."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        rubric = loader.load_rubric("test-config-loader")

        assert isinstance(rubric, Rubric)
        assert len(rubric.requirements) == 2

        # Check first requirement
        req1 = rubric.requirements[0]
        assert req1.id == "R001"
        assert req1.weight == 2.0
        assert req1.evaluation == "binary"

        # Check grading uses centralized defaults
        assert rubric.grading.pass_threshold == DEFAULT_PASS_THRESHOLD

    def test_load_rubric_missing(self) -> None:
        """Missing rubric raises ConfigurationError."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)

        with pytest.raises(ConfigurationError, match="not found"):
            loader.load_rubric("nonexistent-test")

    def test_rubric_total_weight(self) -> None:
        """Calculate total weight of requirements."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        rubric = loader.load_rubric("test-config-loader")

        assert rubric.total_weight() == 3.0  # 2.0 + 1.0

    def test_rubric_weighted_score(self) -> None:
        """Calculate weighted score from requirement scores."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        rubric = loader.load_rubric("test-config-loader")

        scores = {"R001": 1.0, "R002": 0.5}  # Full score, half score
        weighted = rubric.weighted_score(scores)

        # (2.0 * 1.0 + 1.0 * 0.5) / 3.0 = 2.5 / 3.0 = 0.833...
        assert abs(weighted - 0.8333333333) < 0.001


class TestConfigLoaderTier:
    """Tests for loading tier configurations."""

    def test_load_tier(self) -> None:
        """Load tier configuration successfully."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        tier = loader.load_tier("t0")

        assert isinstance(tier, TierConfig)
        assert tier.tier == "t0"
        assert tier.name == "Vanilla"
        assert tier.uses_tools is False

    def test_load_tier_with_system_prompt(self) -> None:
        """Load tier with system prompt."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        tier = loader.load_tier("t1")

        assert tier.tier == "t1"
        assert tier.name == "Prompted"
        assert tier.system_prompt == "You are a helpful assistant."

    def test_load_tier_normalize_name(self) -> None:
        """Tier name is normalized (lowercase, prefixed)."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)

        # Should work with various formats
        tier1 = loader.load_tier("T0")  # uppercase
        tier2 = loader.load_tier("0")  # no prefix
        tier3 = loader.load_tier(" t0 ")  # whitespace

        assert tier1.tier == "t0"
        assert tier2.tier == "t0"
        assert tier3.tier == "t0"

    def test_load_tier_missing(self) -> None:
        """Missing tier raises ConfigurationError."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)

        with pytest.raises(ConfigurationError, match="not found"):
            loader.load_tier("t99")

    def test_load_all_tiers(self) -> None:
        """Load all tier configurations."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        tiers = loader.load_all_tiers()

        assert len(tiers) == 2
        assert "t0" in tiers
        assert "t1" in tiers
        assert tiers["t0"].name == "Vanilla"
        assert tiers["t1"].name == "Prompted"


class TestConfigLoaderModel:
    """Tests for loading model configurations."""

    def test_load_model(self) -> None:
        """Load model configuration successfully."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        model = loader.load_model("test-model")

        assert isinstance(model, ModelConfig)
        assert model.model_id == "test-model"
        assert model.name == "Test Model"
        assert model.provider == "test_provider"
        assert model.adapter == "test_adapter"
        assert model.temperature == 0.5
        assert model.max_tokens == 4096
        assert model.cost_per_1k_input == 0.01
        assert model.cost_per_1k_output == 0.03

    def test_load_model_missing_returns_none(self) -> None:
        """Missing model config returns None (not error)."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        model = loader.load_model("nonexistent-model")

        assert model is None

    def test_load_all_models(self) -> None:
        """Load all model configurations from directory."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        models = loader.load_all_models()

        # Fixtures should have test-model and test-model-2
        assert len(models) >= 2
        assert "test-model" in models
        assert "test-model-2" in models
        assert models["test-model"].model_id == "test-model"
        assert models["test-model"].name == "Test Model"
        assert models["test-model-2"].name == "Test Model Two"

    def test_load_all_models_empty_directory(self) -> None:
        """Empty models directory returns empty dict."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal config structure
            config_dir = Path(tmpdir) / "config"
            models_dir = config_dir / "models"
            models_dir.mkdir(parents=True)

            # Create defaults.yaml (required)
            defaults_path = config_dir / "defaults.yaml"
            defaults_path.write_text("evaluation:\n  runs_per_eval: 1\n")

            loader = ConfigLoader(base_path=Path(tmpdir))
            models = loader.load_all_models()

            assert models == {}

    def test_load_all_models_missing_directory(self) -> None:
        """Missing models directory returns empty dict."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            loader = ConfigLoader(base_path=Path(tmpdir))
            models = loader.load_all_models()

            assert models == {}


class TestConfigLoaderMerged:
    """Tests for merged configuration loading."""

    def test_load_merged_defaults_only(self) -> None:
        """Load merged config with only defaults."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        config = loader.load(test_id="nonexistent", model_id="nonexistent")

        assert isinstance(config, ScyllaConfig)
        assert config.runs_per_tier == 10
        assert config.test_id == "nonexistent"
        assert config.model_id == "nonexistent"
        assert config.model is None

    def test_load_merged_with_model(self) -> None:
        """Load merged config with model configuration."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        config = loader.load(test_id="nonexistent", model_id="test-model")

        assert config.model is not None
        assert config.model.model_id == "test-model"
        assert config.model.temperature == 0.5

    def test_load_merged_with_test_override(self) -> None:
        """Test-specific config overrides other layers."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        config = loader.load(test_id="test-001", model_id="test-model")

        # Test override should apply
        assert config.timeout_seconds == 7200  # From test config
        assert config.max_cost_usd == 5.0  # From test config

        # Model config should still be present
        assert config.model is not None
        assert config.model.temperature == 0.5

    def test_load_merged_priority_order(self) -> None:
        """Verify priority: test > model > defaults."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        config = loader.load(test_id="test-001", model_id="test-model")

        # Test overrides should take precedence
        assert config.timeout_seconds == 7200  # test > defaults (300 -> 3600)
        assert config.max_cost_usd == 5.0  # test override

        # Defaults should fill in non-overridden values
        assert config.runs_per_tier == 10  # from defaults
        assert config.output.runs_dir == "runs"  # from defaults

    def test_load_merged_immutable(self) -> None:
        """Merged config is immutable (frozen)."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        config = loader.load(test_id="test-001", model_id="test-model")

        # Attempting to modify should raise an error
        with pytest.raises(Exception):  # Pydantic ValidationError
            config.timeout_seconds = 9999  # type: ignore


class TestConfigLoaderEdgeCases:
    """Edge case and error handling tests."""

    def test_empty_base_path(self) -> None:
        """ConfigLoader with None base_path uses cwd."""
        loader = ConfigLoader(base_path=None)
        assert loader.base_path == Path.cwd()

    def test_string_base_path(self) -> None:
        """ConfigLoader accepts string base_path."""
        loader = ConfigLoader(base_path=str(FIXTURES_PATH))
        assert loader.base_path == FIXTURES_PATH

    def test_tier_invalid_format(self) -> None:
        """Invalid tier format raises validation error."""
        from scylla.config.models import TierConfig

        with pytest.raises(ValueError, match="Tier must be in format"):
            TierConfig(tier="invalid", name="Test")

    def test_tier_out_of_range(self) -> None:
        """Tier number out of range raises validation error."""
        from scylla.config.models import TierConfig

        with pytest.raises(ValueError, match="Tier number must be 0-6"):
            TierConfig(tier="t99", name="Test")

    def test_requirement_defaults(self) -> None:
        """Requirement uses sensible defaults."""
        req = Requirement(id="R001", description="Test requirement")

        assert req.weight == 1.0
        assert req.evaluation == "binary"

    def test_test_case_empty_id_rejected(self) -> None:
        """Empty test ID is rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            EvalCase(
                id="",
                name="Test",
                description="Test",
                source={"repo": "https://example.com", "hash": "abc123"},
                task={"prompt_file": "prompt.md"},
            )


class TestFilenameModelIdValidation:
    """Test validation of filename/model_id consistency."""

    def test_filename_matches_model_id_exact(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test validation passes when filename matches model_id exactly."""
        config_dir = tmp_path / "config" / "models"
        config_dir.mkdir(parents=True)

        config_path = config_dir / "test-model.yaml"
        config_path.write_text("""
model_id: test-model
name: Test Model
provider: openai
adapter: openai_adapter
""")

        loader = ConfigLoader(str(tmp_path))
        with caplog.at_level(logging.WARNING):
            config = loader.load_model("test-model")

        assert config is not None
        assert config.model_id == "test-model"
        assert not caplog.records  # No warnings

    def test_filename_matches_model_id_simplified(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test validation passes with simplified naming (colon to hyphen)."""
        config_dir = tmp_path / "config" / "models"
        config_dir.mkdir(parents=True)

        # Filename uses hyphens, model_id uses colons
        config_path = config_dir / "claude-opus-4.yaml"
        config_path.write_text("""
model_id: claude:opus:4
name: Claude Opus 4
provider: anthropic
adapter: anthropic_adapter
""")

        loader = ConfigLoader(str(tmp_path))
        with caplog.at_level(logging.WARNING):
            config = loader.load_model("claude-opus-4")

        assert config is not None
        assert config.model_id == "claude:opus:4"
        # Simplified pattern should match
        assert not caplog.records  # No warnings

    def test_filename_mismatch_warns(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test validation warns when filename doesn't match model_id."""
        config_dir = tmp_path / "config" / "models"
        config_dir.mkdir(parents=True)

        # Filename says opus-4, but model_id is sonnet-4-5
        config_path = config_dir / "claude-opus-4.yaml"
        config_path.write_text("""
model_id: claude-sonnet-4-5
name: Claude Sonnet 4.5
provider: anthropic
adapter: anthropic_adapter
""")

        loader = ConfigLoader(str(tmp_path))
        with caplog.at_level(logging.WARNING):
            config = loader.load_model("claude-opus-4")

        assert config is not None
        assert config.model_id == "claude-sonnet-4-5"
        # Should have warning about mismatch
        assert len(caplog.records) == 1
        assert "claude-opus-4.yaml" in caplog.text
        assert "claude-sonnet-4-5" in caplog.text
        assert "claude-sonnet-4-5.yaml" in caplog.text

    def test_test_fixtures_skip_validation(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that test fixtures (prefixed with _) skip validation."""
        config_dir = tmp_path / "config" / "models"
        config_dir.mkdir(parents=True)

        # Test fixture with underscore prefix
        config_path = config_dir / "_test-fixture.yaml"
        config_path.write_text("""
model_id: different-model-id
name: Test Fixture
provider: openai
adapter: openai_adapter
""")

        loader = ConfigLoader(str(tmp_path))
        with caplog.at_level(logging.WARNING):
            config = loader.load_model("_test-fixture")

        assert config is not None
        assert config.model_id == "different-model-id"
        assert not caplog.records  # No warnings for test fixtures


class TestFilenameTierConsistency:
    """Test validation of filename/tier consistency."""

    def test_filename_matches_tier_exact(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test validation passes when filename matches tier exactly."""
        config_dir = tmp_path / "config" / "tiers"
        config_dir.mkdir(parents=True)

        config_path = config_dir / "t0.yaml"
        config_path.write_text("""
tier: t0
name: Baseline
""")

        loader = ConfigLoader(str(tmp_path))
        with caplog.at_level(logging.WARNING):
            config = loader.load_tier("t0")

        assert config is not None
        assert config.tier == "t0"
        assert not caplog.records  # No warnings

    def test_filename_mismatch_warns(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test validation warns when filename doesn't match tier."""
        config_dir = tmp_path / "config" / "tiers"
        config_dir.mkdir(parents=True)

        # Filename says t0, but tier field says t1
        config_path = config_dir / "t0.yaml"
        config_path.write_text("""
tier: t1
name: Skills
""")

        loader = ConfigLoader(str(tmp_path))
        with caplog.at_level(logging.WARNING):
            config = loader.load_tier("t0")

        assert config is not None
        assert config.tier == "t1"
        # Should have warning about mismatch
        assert len(caplog.records) == 1
        assert "t0.yaml" in caplog.text
        assert "t1" in caplog.text
        assert "t1.yaml" in caplog.text

    def test_test_fixtures_skip_validation(self, tmp_path: Path) -> None:
        """Test that test fixtures (prefixed with _) skip validation."""
        from scylla.config.validation import validate_filename_tier_consistency

        # Test fixture with underscore prefix - tier field won't match filename
        config_path = tmp_path / "_test-fixture.yaml"
        warnings = validate_filename_tier_consistency(config_path, "t0")

        assert not warnings  # No warnings for test fixtures

    def test_warning_message_format(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Test that warning message contains filename and tier field."""
        config_dir = tmp_path / "config" / "tiers"
        config_dir.mkdir(parents=True)

        config_path = config_dir / "t2.yaml"
        config_path.write_text("""
tier: t3
name: Delegation
""")

        loader = ConfigLoader(str(tmp_path))
        with caplog.at_level(logging.WARNING):
            loader.load_tier("t2")

        assert len(caplog.records) == 1
        warning_text = caplog.records[0].message
        assert "t2.yaml" in warning_text
        assert "t3" in warning_text
        assert "t3.yaml" in warning_text
