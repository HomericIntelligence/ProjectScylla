"""Tests for Pydantic configuration models."""

import pytest
from pydantic import ValidationError

from scylla.config.models import (
    AdaptersConfig,
    CleanupConfig,
    ConfigurationError,
    DefaultsConfig,
    EvalCase,
    EvaluationConfig,
    GradingConfig,
    JudgeConfig,
    LoggingConfig,
    MetricsConfig,
    ModelConfig,
    OutputConfig,
    Requirement,
    Rubric,
    ScyllaConfig,
    SourceConfig,
    TaskConfig,
    TierConfig,
    ValidationConfig,
)

# -----------------------------------------------------------------------------
# Source Configuration Tests
# -----------------------------------------------------------------------------


class TestSourceConfig:
    """Tests for SourceConfig model."""

    def test_valid_source_config(self) -> None:
        """Valid source config should construct successfully."""
        config = SourceConfig(
            repo="https://github.com/example/repo",
            hash="abc123",
        )
        assert config.repo == "https://github.com/example/repo"
        assert config.hash == "abc123"

    def test_missing_required_fields(self) -> None:
        """Missing required fields should raise ValidationError."""
        with pytest.raises(ValidationError):
            SourceConfig()  # type: ignore


# -----------------------------------------------------------------------------
# Task Configuration Tests
# -----------------------------------------------------------------------------


class TestTaskConfig:
    """Tests for TaskConfig model."""

    def test_valid_task_config(self) -> None:
        """Valid task config should construct successfully."""
        config = TaskConfig(prompt_file="prompt.md")
        assert config.prompt_file == "prompt.md"
        assert config.timeout_seconds == 3600  # default

    def test_custom_timeout(self) -> None:
        """Custom timeout should be accepted."""
        config = TaskConfig(prompt_file="prompt.md", timeout_seconds=7200)
        assert config.timeout_seconds == 7200

    @pytest.mark.parametrize("invalid_timeout", [30, 100000])
    def test_invalid_timeout_bounds(self, invalid_timeout: int) -> None:
        """Timeout outside bounds should raise ValidationError."""
        with pytest.raises(ValidationError):
            TaskConfig(prompt_file="prompt.md", timeout_seconds=invalid_timeout)


# -----------------------------------------------------------------------------
# Validation Configuration Tests
# -----------------------------------------------------------------------------


class TestValidationConfig:
    """Tests for ValidationConfig model."""

    def test_default_values(self) -> None:
        """ValidationConfig should use default file paths."""
        config = ValidationConfig()
        assert config.criteria_file == "expected/criteria.md"
        assert config.rubric_file == "expected/rubric.yaml"

    def test_custom_paths(self) -> None:
        """Custom file paths should be accepted."""
        config = ValidationConfig(
            criteria_file="custom/criteria.md",
            rubric_file="custom/rubric.yaml",
        )
        assert config.criteria_file == "custom/criteria.md"
        assert config.rubric_file == "custom/rubric.yaml"


# -----------------------------------------------------------------------------
# EvalCase Tests
# -----------------------------------------------------------------------------


class TestEvalCase:
    """Tests for EvalCase model."""

    def test_valid_eval_case(self) -> None:
        """Valid EvalCase should construct successfully."""
        case = EvalCase(
            id="test-001",
            name="Test Case",
            description="A test case",
            source=SourceConfig(repo="https://github.com/example/repo", hash="abc123"),
            task=TaskConfig(prompt_file="prompt.md"),
            language="python",
        )
        assert case.id == "test-001"
        assert case.name == "Test Case"
        assert case.language == "python"

    def test_default_validation_config(self) -> None:
        """EvalCase should have default ValidationConfig."""
        case = EvalCase(
            id="test-001",
            name="Test Case",
            description="A test case",
            source=SourceConfig(repo="https://github.com/example/repo", hash="abc123"),
            task=TaskConfig(prompt_file="prompt.md"),
            language="python",
        )
        assert case.validation.criteria_file == "expected/criteria.md"

    def test_id_validation_strips_whitespace(self) -> None:
        """ID validation should strip whitespace."""
        case = EvalCase(
            id="  test-001  ",
            name="Test Case",
            description="A test case",
            source=SourceConfig(repo="https://github.com/example/repo", hash="abc123"),
            task=TaskConfig(prompt_file="prompt.md"),
            language="python",
        )
        assert case.id == "test-001"

    def test_empty_id_raises_error(self) -> None:
        """Empty ID should raise ValidationError."""
        with pytest.raises(ValidationError, match="Test ID cannot be empty"):
            EvalCase(
                id="",
                name="Test Case",
                description="A test case",
                source=SourceConfig(repo="https://github.com/example/repo", hash="abc123"),
                task=TaskConfig(prompt_file="prompt.md"),
                language="python",
            )


# -----------------------------------------------------------------------------
# Requirement and Rubric Tests
# -----------------------------------------------------------------------------


class TestRequirement:
    """Tests for Requirement model."""

    def test_valid_requirement(self) -> None:
        """Valid requirement should construct successfully."""
        req = Requirement(
            id="R001",
            description="Test requirement",
            weight=2.0,
            evaluation="scaled",
        )
        assert req.id == "R001"
        assert req.weight == 2.0
        assert req.evaluation == "scaled"

    def test_default_values(self) -> None:
        """Requirement should have sensible defaults."""
        req = Requirement(id="R001", description="Test requirement")
        assert req.weight == 1.0
        assert req.evaluation == "binary"

    @pytest.mark.parametrize("invalid_weight", [-1.0, 11.0])
    def test_weight_bounds(self, invalid_weight: float) -> None:
        """Weight outside bounds should raise ValidationError."""
        with pytest.raises(ValidationError):
            Requirement(id="R001", description="Test", weight=invalid_weight)


class TestGradingConfig:
    """Tests for GradingConfig model."""

    def test_default_pass_threshold(self) -> None:
        """GradingConfig should use DEFAULT_PASS_THRESHOLD."""
        config = GradingConfig()
        assert config.pass_threshold == 0.60

    def test_custom_pass_threshold(self) -> None:
        """Custom pass threshold should be accepted."""
        config = GradingConfig(pass_threshold=0.75)
        assert config.pass_threshold == 0.75

    @pytest.mark.parametrize("invalid_threshold", [-0.1, 1.5])
    def test_threshold_bounds(self, invalid_threshold: float) -> None:
        """Threshold outside [0, 1] should raise ValidationError."""
        with pytest.raises(ValidationError):
            GradingConfig(pass_threshold=invalid_threshold)


class TestRubric:
    """Tests for Rubric model."""

    def test_empty_rubric(self) -> None:
        """Empty rubric should be valid."""
        rubric = Rubric()
        assert len(rubric.requirements) == 0
        assert rubric.total_weight() == 0.0

    def test_total_weight(self) -> None:
        """total_weight should sum all requirement weights."""
        rubric = Rubric(
            requirements=[
                Requirement(id="R001", description="Test 1", weight=1.0),
                Requirement(id="R002", description="Test 2", weight=2.0),
                Requirement(id="R003", description="Test 3", weight=1.5),
            ]
        )
        assert rubric.total_weight() == 4.5

    def test_weighted_score_all_requirements(self) -> None:
        """weighted_score should calculate correctly when all requirements scored."""
        rubric = Rubric(
            requirements=[
                Requirement(id="R001", description="Test 1", weight=2.0),
                Requirement(id="R002", description="Test 2", weight=3.0),
            ]
        )
        scores = {"R001": 1.0, "R002": 0.5}
        # (1.0 * 2.0 + 0.5 * 3.0) / 5.0 = 3.5 / 5.0 = 0.7
        assert rubric.weighted_score(scores) == pytest.approx(0.7)

    def test_weighted_score_partial_requirements(self) -> None:
        """weighted_score should handle missing requirements."""
        rubric = Rubric(
            requirements=[
                Requirement(id="R001", description="Test 1", weight=2.0),
                Requirement(id="R002", description="Test 2", weight=3.0),
            ]
        )
        scores = {"R001": 1.0}  # R002 missing
        # (1.0 * 2.0 + 0.0) / 5.0 = 0.4
        assert rubric.weighted_score(scores) == pytest.approx(0.4)

    def test_weighted_score_zero_weight(self) -> None:
        """weighted_score should return 0.0 for zero total weight."""
        rubric = Rubric(requirements=[])
        scores: dict[str, float] = {}
        assert rubric.weighted_score(scores) == 0.0


# -----------------------------------------------------------------------------
# Model Configuration Tests
# -----------------------------------------------------------------------------


class TestModelConfig:
    """Tests for ModelConfig model."""

    def test_minimal_model_config(self) -> None:
        """Minimal model config with only required fields."""
        config = ModelConfig(model_id="claude-sonnet-4-5-20250929")
        assert config.model_id == "claude-sonnet-4-5-20250929"
        assert config.name == ""
        assert config.adapter == "claude_code"
        assert config.temperature == 0.0
        assert config.max_tokens == 8192

    def test_full_model_config(self) -> None:
        """Full model config with all fields."""
        config = ModelConfig(
            model_id="gpt-4",
            name="GPT-4",
            provider="openai",
            adapter="openai_codex",
            temperature=0.7,
            max_tokens=4096,
            cost_per_1k_input=0.03,
            cost_per_1k_output=0.06,
            timeout_seconds=1800,
            max_cost_usd=5.0,
        )
        assert config.model_id == "gpt-4"
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.timeout_seconds == 1800

    @pytest.mark.parametrize("invalid_temp", [-0.1, 2.5])
    def test_temperature_bounds(self, invalid_temp: float) -> None:
        """Temperature outside [0, 2] should raise ValidationError."""
        with pytest.raises(ValidationError):
            ModelConfig(model_id="test", temperature=invalid_temp)

    @pytest.mark.parametrize("invalid_tokens", [0, 300000])
    def test_max_tokens_bounds(self, invalid_tokens: int) -> None:
        """max_tokens outside [1, 200000] should raise ValidationError."""
        with pytest.raises(ValidationError):
            ModelConfig(model_id="test", max_tokens=invalid_tokens)


# -----------------------------------------------------------------------------
# Tier Configuration Tests
# -----------------------------------------------------------------------------


class TestTierConfig:
    """Tests for TierConfig model."""

    def test_valid_tier_config(self) -> None:
        """Valid tier config should construct successfully."""
        config = TierConfig(
            tier="t0",
            name="Baseline",
            description="No tools or skills",
        )
        assert config.tier == "t0"
        assert config.name == "Baseline"
        assert config.uses_tools is False

    def test_tier_normalization(self) -> None:
        """Tier should be normalized to lowercase."""
        config = TierConfig(tier="T2", name="Test")
        assert config.tier == "t2"

    def test_tier_whitespace_stripped(self) -> None:
        """Tier should have whitespace stripped."""
        config = TierConfig(tier="  t3  ", name="Test")
        assert config.tier == "t3"

    @pytest.mark.parametrize("valid_tier", ["t0", "t1", "t2", "t3", "t4", "t5", "t6"])
    def test_valid_tier_numbers(self, valid_tier: str) -> None:
        """All tier numbers 0-6 should be valid."""
        config = TierConfig(tier=valid_tier, name="Test")
        assert config.tier == valid_tier

    @pytest.mark.parametrize("invalid_tier", ["t7", "t-1", "tier0", "0", "t", "tx"])
    def test_invalid_tier_format(self, invalid_tier: str) -> None:
        """Invalid tier format should raise ValidationError."""
        with pytest.raises(ValidationError):
            TierConfig(tier=invalid_tier, name="Test")

    def test_tier_with_capabilities(self) -> None:
        """Tier with capabilities should set flags correctly."""
        config = TierConfig(
            tier="t4",
            name="Hierarchy",
            uses_tools=True,
            uses_delegation=True,
            uses_hierarchy=True,
        )
        assert config.uses_tools is True
        assert config.uses_delegation is True
        assert config.uses_hierarchy is True


# -----------------------------------------------------------------------------
# Global Configuration Tests
# -----------------------------------------------------------------------------


class TestJudgeConfig:
    """Tests for JudgeConfig model."""

    def test_default_judge_config(self) -> None:
        """JudgeConfig should have sensible defaults."""
        config = JudgeConfig()
        assert config.model == "claude-opus-4-5-20251101"
        assert config.adapter == "claude_code"


class TestAdaptersConfig:
    """Tests for AdaptersConfig model."""

    def test_default_adapters(self) -> None:
        """AdaptersConfig should have default adapters list."""
        config = AdaptersConfig()
        assert config.default == "claude_code"
        assert "claude_code" in config.available
        assert "openai_codex" in config.available


class TestCleanupConfig:
    """Tests for CleanupConfig model."""

    def test_default_cleanup_settings(self) -> None:
        """CleanupConfig should have sensible defaults."""
        config = CleanupConfig()
        assert config.delete_workspace is True
        assert config.keep_logs is True


class TestEvaluationConfig:
    """Tests for EvaluationConfig model."""

    def test_default_evaluation_settings(self) -> None:
        """EvaluationConfig should have sensible defaults."""
        config = EvaluationConfig()
        assert config.runs_per_tier == 10
        assert config.timeout == 300
        assert config.seed is None

    def test_alias_support(self) -> None:
        """EvaluationConfig should support runs_per_eval alias."""
        config = EvaluationConfig(runs_per_eval=20)
        assert config.runs_per_tier == 20

    @pytest.mark.parametrize("invalid_runs", [0, 101])
    def test_runs_bounds(self, invalid_runs: int) -> None:
        """runs_per_tier outside [1, 100] should raise ValidationError."""
        with pytest.raises(ValidationError):
            EvaluationConfig(runs_per_eval=invalid_runs)


class TestMetricsConfig:
    """Tests for MetricsConfig model."""

    def test_default_metrics(self) -> None:
        """MetricsConfig should have default quality and economic metrics."""
        config = MetricsConfig()
        assert "pass_rate" in config.quality
        assert "impl_rate" in config.quality
        assert "cost_of_pass" in config.economic


class TestOutputConfig:
    """Tests for OutputConfig model."""

    def test_default_output_dirs(self) -> None:
        """OutputConfig should have default directory names."""
        config = OutputConfig()
        assert config.runs_dir == "runs"
        assert config.summaries_dir == "summaries"
        assert config.reports_dir == "reports"


class TestLoggingConfig:
    """Tests for LoggingConfig model."""

    def test_default_logging_settings(self) -> None:
        """LoggingConfig should have sensible defaults."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert "%(asctime)s" in config.format


class TestDefaultsConfig:
    """Tests for DefaultsConfig model."""

    def test_defaults_with_all_nested_configs(self) -> None:
        """DefaultsConfig should initialize all nested configs."""
        config = DefaultsConfig()
        assert isinstance(config.evaluation, EvaluationConfig)
        assert isinstance(config.metrics, MetricsConfig)
        assert isinstance(config.output, OutputConfig)
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.judge, JudgeConfig)
        assert isinstance(config.adapters, AdaptersConfig)
        assert isinstance(config.cleanup, CleanupConfig)

    def test_defaults_with_custom_values(self) -> None:
        """DefaultsConfig should accept custom values."""
        config = DefaultsConfig(
            runs_per_tier=25,
            timeout_seconds=7200,
            max_cost_usd=20.0,
        )
        assert config.runs_per_tier == 25
        assert config.timeout_seconds == 7200
        assert config.max_cost_usd == 20.0


# -----------------------------------------------------------------------------
# ScyllaConfig Tests
# -----------------------------------------------------------------------------


class TestScyllaConfig:
    """Tests for ScyllaConfig (merged runtime config)."""

    def test_minimal_scylla_config(self) -> None:
        """Minimal ScyllaConfig with defaults."""
        config = ScyllaConfig()
        assert config.runs_per_tier == 10
        assert config.timeout_seconds == 3600
        assert config.max_cost_usd == 10.0

    def test_scylla_config_with_model(self) -> None:
        """ScyllaConfig with model configuration."""
        model = ModelConfig(model_id="claude-sonnet-4-5-20250929")
        config = ScyllaConfig(model=model, model_id="claude-sonnet-4-5-20250929")
        assert config.model is not None
        assert config.model_id == "claude-sonnet-4-5-20250929"

    def test_scylla_config_with_context(self) -> None:
        """ScyllaConfig with test and model context."""
        config = ScyllaConfig(test_id="test-001", model_id="gpt-4")
        assert config.test_id == "test-001"
        assert config.model_id == "gpt-4"

    def test_scylla_config_is_frozen(self) -> None:
        """ScyllaConfig should be frozen (immutable)."""
        config = ScyllaConfig()
        with pytest.raises(ValidationError):
            config.runs_per_tier = 20

    def test_scylla_config_validation(self) -> None:
        """ScyllaConfig should validate via Pydantic."""
        # Valid config
        config = ScyllaConfig(runs_per_tier=5, timeout_seconds=1800)
        assert config.runs_per_tier == 5

        # Invalid config should raise during construction
        with pytest.raises(ValidationError):
            ScyllaConfig(runs_per_tier=0)


# -----------------------------------------------------------------------------
# ConfigurationError Tests
# -----------------------------------------------------------------------------


class TestConfigurationError:
    """Tests for ConfigurationError exception."""

    def test_configuration_error_is_exception(self) -> None:
        """ConfigurationError should be an Exception."""
        assert issubclass(ConfigurationError, Exception)

    def test_configuration_error_can_be_raised(self) -> None:
        """ConfigurationError should be raisable with message."""
        with pytest.raises(ConfigurationError, match="Test error"):
            raise ConfigurationError("Test error")
