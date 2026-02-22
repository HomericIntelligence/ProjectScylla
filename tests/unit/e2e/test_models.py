"""Unit tests for E2E data models."""

from __future__ import annotations

import tempfile
from pathlib import Path

from scylla.e2e.models import (
    E2ERunResult,
    ExperimentConfig,
    JudgeResultSummary,
    ResourceManifest,
    SubTestConfig,
    SubTestResult,
    TierBaseline,
    TierConfig,
    TierID,
)


class TestTierID:
    """Tests for TierID enum."""

    def test_from_string_uppercase(self) -> None:
        """Test creating TierID from uppercase string."""
        assert TierID.from_string("T0") == TierID.T0
        assert TierID.from_string("T3") == TierID.T3

    def test_from_string_lowercase(self) -> None:
        """Test creating TierID from lowercase string."""
        assert TierID.from_string("t0") == TierID.T0
        assert TierID.from_string("t6") == TierID.T6

    def test_tier_ordering(self) -> None:
        """Test that tiers can be sorted."""
        assert TierID.T0 < TierID.T1
        assert TierID.T1 < TierID.T6
        assert not TierID.T3 < TierID.T2


class TestSubTestConfig:
    """Tests for SubTestConfig."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        config = SubTestConfig(
            id="01",
            name="Minimal",
            description="Minimal CLAUDE.md",
            claude_md_path=Path("/path/to/CLAUDE.md"),
        )

        result = config.to_dict()

        assert result["id"] == "01"
        assert result["name"] == "Minimal"
        assert result["claude_md_path"] == "/path/to/CLAUDE.md"
        assert result["extends_previous"] is True

    def test_to_dict_with_none_paths(self) -> None:
        """Test conversion with None paths."""
        config = SubTestConfig(
            id="baseline",
            name="Baseline",
            description="No customization",
        )

        result = config.to_dict()

        assert result["claude_md_path"] is None
        assert result["claude_dir_path"] is None

    def test_system_prompt_mode(self) -> None:
        """Test that system_prompt_mode is correctly stored and serialized."""
        # Test default value
        config_default = SubTestConfig(
            id="01",
            name="Default",
            description="Default system prompt mode",
        )
        assert config_default.system_prompt_mode == "custom"
        assert config_default.to_dict()["system_prompt_mode"] == "custom"

        # Test explicit "none" mode (for T0/00 subtest)
        config_none = SubTestConfig(
            id="00",
            name="Empty",
            description="No system prompt",
            system_prompt_mode="none",
        )
        assert config_none.system_prompt_mode == "none"
        assert config_none.to_dict()["system_prompt_mode"] == "none"

        # Test "default" mode
        config_default_mode = SubTestConfig(
            id="01",
            name="Default Mode",
            description="Use Claude Code default",
            system_prompt_mode="default",
        )
        assert config_default_mode.system_prompt_mode == "default"
        assert config_default_mode.to_dict()["system_prompt_mode"] == "default"


class TestTierConfig:
    """Tests for TierConfig."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        config = TierConfig(
            tier_id=TierID.T2,
            subtests=[
                SubTestConfig(id="01", name="First", description="First subtest"),
                SubTestConfig(id="02", name="Second", description="Second subtest"),
            ],
        )

        result = config.to_dict()

        assert result["tier_id"] == "T2"
        assert len(result["subtests"]) == 2
        # system_prompt_mode is per-subtest, not per-tier
        assert "system_prompt_mode" not in result


class TestJudgeResultSummary:
    """Tests for JudgeResultSummary."""

    def test_to_dict_with_valid_result(self) -> None:
        """Test that is_valid=True serializes correctly."""
        summary = JudgeResultSummary(
            model="claude-sonnet-4-5",
            score=0.8,
            passed=True,
            grade="B",
            reasoning="Good work",
            judge_number=1,
            is_valid=True,
            criteria_scores={"accuracy": {"score": 0.9, "explanation": "Very accurate"}},
        )

        result = summary.to_dict()

        assert result["model"] == "claude-sonnet-4-5"
        assert result["score"] == 0.8
        assert result["is_valid"] is True
        assert result["criteria_scores"]["accuracy"]["score"] == 0.9

    def test_to_dict_with_invalid_result(self) -> None:
        """Test that is_valid=False serializes correctly (heuristic fallback)."""
        summary = JudgeResultSummary(
            model="claude-haiku-4-5",
            score=0.0,
            passed=False,
            grade="F",
            reasoning="Heuristic fallback: agent failed",
            judge_number=2,
            is_valid=False,
            criteria_scores=None,
        )

        result = summary.to_dict()

        assert result["is_valid"] is False
        assert result["criteria_scores"] is None
        assert result["score"] == 0.0

    def test_default_is_valid_true(self) -> None:
        """Test that is_valid defaults to True for backward compatibility."""
        summary = JudgeResultSummary(
            model="claude-opus-4-6",
            score=0.95,
            passed=True,
            grade="A",
            reasoning="Excellent",
            judge_number=1,
        )

        assert summary.is_valid is True
        result = summary.to_dict()
        assert result["is_valid"] is True


class TestE2ERunResult:
    """Tests for E2ERunResult."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        from scylla.e2e.models import TokenStats

        result = E2ERunResult(
            run_number=1,
            exit_code=0,
            token_stats=TokenStats(input_tokens=1000, output_tokens=200),
            cost_usd=0.05,
            duration_seconds=15.5,
            agent_duration_seconds=12.0,
            judge_duration_seconds=3.5,
            judge_score=0.8,
            judge_passed=True,
            judge_grade="B",
            judge_reasoning="Good work",
            workspace_path=Path("/workspace"),
            logs_path=Path("/logs"),
        )

        d = result.to_dict()

        assert d["run_number"] == 1
        assert d["exit_code"] == 0
        assert d["cost_usd"] == 0.05
        assert d["duration_seconds"] == 15.5
        assert d["agent_duration_seconds"] == 12.0
        assert d["judge_duration_seconds"] == 3.5
        assert d["judge_score"] == 0.8
        assert d["workspace_path"] == "/workspace"
        # Legacy properties should still work
        assert result.tokens_input == 1000
        assert result.tokens_output == 200

    def test_criteria_scores_coerces_none_to_empty_dict(self) -> None:
        """Test that criteria_scores=None is coerced to {} by the Pydantic validator."""
        from scylla.e2e.models import TokenStats

        result = E2ERunResult(
            run_number=1,
            exit_code=0,
            token_stats=TokenStats(input_tokens=0, output_tokens=0),
            cost_usd=0.0,
            duration_seconds=0.0,
            agent_duration_seconds=0.0,
            judge_duration_seconds=0.0,
            judge_score=0.0,
            judge_passed=False,
            judge_grade="F",
            judge_reasoning="",
            workspace_path=Path("/workspace"),
            logs_path=Path("/logs"),
            criteria_scores=None,  # type: ignore[arg-type]
        )

        assert result.criteria_scores == {}

    def test_criteria_scores_accepts_empty_dict(self) -> None:
        """Test that criteria_scores={} is accepted without modification."""
        from scylla.e2e.models import TokenStats

        result = E2ERunResult(
            run_number=1,
            exit_code=0,
            token_stats=TokenStats(input_tokens=0, output_tokens=0),
            cost_usd=0.0,
            duration_seconds=0.0,
            agent_duration_seconds=0.0,
            judge_duration_seconds=0.0,
            judge_score=0.0,
            judge_passed=False,
            judge_grade="F",
            judge_reasoning="",
            workspace_path=Path("/workspace"),
            logs_path=Path("/logs"),
            criteria_scores={},
        )

        assert result.criteria_scores == {}

    def test_criteria_scores_accepts_populated_dict(self) -> None:
        """Test that a populated criteria_scores dict is preserved."""
        from scylla.e2e.models import TokenStats

        scores = {"accuracy": {"score": 0.9, "explanation": "Good"}}
        result = E2ERunResult(
            run_number=1,
            exit_code=0,
            token_stats=TokenStats(input_tokens=0, output_tokens=0),
            cost_usd=0.0,
            duration_seconds=0.0,
            agent_duration_seconds=0.0,
            judge_duration_seconds=0.0,
            judge_score=0.9,
            judge_passed=True,
            judge_grade="A",
            judge_reasoning="Good work",
            workspace_path=Path("/workspace"),
            logs_path=Path("/logs"),
            criteria_scores=scores,
        )

        assert result.criteria_scores == scores


class TestSubTestResult:
    """Tests for SubTestResult."""

    def test_aggregated_metrics(self) -> None:
        """Test that aggregated metrics work."""
        result = SubTestResult(
            subtest_id="01",
            tier_id=TierID.T2,
            runs=[],
            pass_rate=0.8,
            mean_score=0.75,
            median_score=0.77,
            std_dev_score=0.05,
            mean_cost=0.10,
            total_cost=1.00,
            consistency=0.93,
        )

        d = result.to_dict()

        assert d["pass_rate"] == 0.8
        assert d["median_score"] == 0.77
        assert d["consistency"] == 0.93


class TestTierBaseline:
    """Tests for TierBaseline."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        baseline = TierBaseline(
            tier_id=TierID.T2,
            subtest_id="01",
            claude_md_path=Path("/config/CLAUDE.md"),
            claude_dir_path=Path("/config/.claude"),
        )

        d = baseline.to_dict()

        assert d["tier_id"] == "T2"
        assert d["subtest_id"] == "01"
        assert d["claude_md_path"] == "/config/CLAUDE.md"


class TestResourceManifest:
    """Tests for ResourceManifest."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        manifest = ResourceManifest(
            tier_id="T2",
            subtest_id="03",
            fixture_config_path="/fixtures/test-001/t2/03-full/config.yaml",
            resources={"claude_md": {"blocks": ["B01", "B02", "B03"]}},
            composed_at="2026-01-03T12:00:00+00:00",
            claude_md_hash="abc123def456",
            inherited_from={"claude_md": {"blocks": ["B01"]}},
        )

        d = manifest.to_dict()

        assert d["tier_id"] == "T2"
        assert d["subtest_id"] == "03"
        assert d["resources"]["claude_md"]["blocks"] == ["B01", "B02", "B03"]
        assert d["claude_md_hash"] == "abc123def456"
        assert d["inherited_from"]["claude_md"]["blocks"] == ["B01"]

    def test_save_and_load(self) -> None:
        """Test saving and loading manifest."""
        manifest = ResourceManifest(
            tier_id="T0",
            subtest_id="05",
            fixture_config_path="/fixtures/test-001/t0/05-core/config.yaml",
            resources={
                "claude_md": {"blocks": ["B02", "B05", "B07"]},
                "skills": {"categories": ["github"]},
            },
            composed_at="2026-01-03T14:30:00+00:00",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config_manifest.json"
            manifest.save(path)

            loaded = ResourceManifest.load(path)

            assert loaded.tier_id == "T0"
            assert loaded.subtest_id == "05"
            assert loaded.resources["claude_md"]["blocks"] == ["B02", "B05", "B07"]
            assert loaded.resources["skills"]["categories"] == ["github"]
            assert loaded.claude_md_hash is None
            assert loaded.inherited_from is None


class TestExperimentConfig:
    """Tests for ExperimentConfig."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        config = ExperimentConfig(
            experiment_id="test-001",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("prompt.md"),
            language="mojo",
            tiers_to_run=[TierID.T0, TierID.T1],
        )

        d = config.to_dict()

        assert d["experiment_id"] == "test-001"
        assert d["task_repo"] == "https://github.com/test/repo"
        assert d["tiers_to_run"] == ["T0", "T1"]

    def test_save_and_load(self) -> None:
        """Test saving and loading configuration."""
        config = ExperimentConfig(
            experiment_id="test-002",
            task_repo="https://github.com/test/repo",
            task_commit="def456",
            task_prompt_file=Path("prompt.md"),
            language="python",
            runs_per_subtest=5,
            tiers_to_run=[TierID.T0, TierID.T1, TierID.T2],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            config.save(path)

            loaded = ExperimentConfig.load(path)

            assert loaded.experiment_id == "test-002"
            assert loaded.runs_per_subtest == 5
            assert loaded.tiers_to_run == [TierID.T0, TierID.T1, TierID.T2]


class TestExperimentConfigDefaults:
    """Tests verifying ExperimentConfig defaults use the published constants."""

    def test_default_models_use_constant(self) -> None:
        """ExperimentConfig().models defaults to [DEFAULT_AGENT_MODEL]."""
        from scylla.config.constants import DEFAULT_AGENT_MODEL

        config = ExperimentConfig(
            experiment_id="test-defaults",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("prompt.md"),
            language="python",
        )
        assert config.models == [DEFAULT_AGENT_MODEL]

    def test_default_judge_models_use_constant(self) -> None:
        """ExperimentConfig().judge_models defaults to [DEFAULT_JUDGE_MODEL]."""
        from scylla.config.constants import DEFAULT_JUDGE_MODEL

        config = ExperimentConfig(
            experiment_id="test-defaults",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("prompt.md"),
            language="python",
        )
        assert config.judge_models == [DEFAULT_JUDGE_MODEL]
