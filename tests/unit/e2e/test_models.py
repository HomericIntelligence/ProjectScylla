"""Unit tests for E2E data models."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from scylla.e2e.models import (
    ExperimentConfig,
    ResourceManifest,
    RunResult,
    SubTestConfig,
    SubTestResult,
    TierBaseline,
    TierConfig,
    TierID,
    TierResult,
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
            system_prompt_mode="custom",
        )

        result = config.to_dict()

        assert result["tier_id"] == "T2"
        assert len(result["subtests"]) == 2
        assert result["system_prompt_mode"] == "custom"


class TestRunResult:
    """Tests for RunResult."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        from scylla.e2e.models import TokenStats

        result = RunResult(
            run_number=1,
            exit_code=0,
            token_stats=TokenStats(input_tokens=1000, output_tokens=200),
            cost_usd=0.05,
            duration_seconds=15.5,
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
        assert d["judge_score"] == 0.8
        assert d["workspace_path"] == "/workspace"
        # Legacy properties should still work
        assert result.tokens_input == 1000
        assert result.tokens_output == 200


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
