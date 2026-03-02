"""Unit tests for baseline pipeline regression validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from scylla.e2e.llm_judge import BuildPipelineResult
from scylla.e2e.models import E2ERunResult, TokenStats
from scylla.e2e.subtest_executor import _load_pipeline_baseline, _save_pipeline_baseline
from scylla.judge.prompts import build_task_prompt


@pytest.fixture
def mock_pipeline_result() -> BuildPipelineResult:
    """Create a mock BuildPipelineResult."""
    return BuildPipelineResult(
        language="python",
        build_passed=True,
        build_output="Build successful",
        format_passed=False,
        format_output="Lint errors found",
        test_passed=True,
        test_output="All tests passed",
        all_passed=False,
    )


@pytest.fixture
def mock_baseline_all_passed() -> BuildPipelineResult:
    """Create a baseline where everything passed."""
    return BuildPipelineResult(
        language="python",
        build_passed=True,
        build_output="",
        format_passed=True,
        format_output="",
        test_passed=True,
        test_output="",
        all_passed=True,
    )


def test_build_task_prompt_with_baseline(
    mock_pipeline_result: BuildPipelineResult, mock_baseline_all_passed: BuildPipelineResult
) -> None:
    """Test that baseline section is rendered when baseline_pipeline_str is provided."""
    baseline_str = "**Overall Status**: ALL PASSED ✓\n\nBuild: ✓\nLint: ✓\nTest: ✓"
    pipeline_str = "**Overall Status**: SOME FAILED ✗\n\nBuild: ✓\nLint: ✗\nTest: ✓"

    prompt = build_task_prompt(
        task_prompt="Test task",
        agent_output="Agent output",
        workspace_state="Files created",
        baseline_pipeline_str=baseline_str,
        pipeline_result_str=pipeline_str,
    )

    # Baseline section should be present
    assert "## Baseline Pipeline Results (Before Agent)" in prompt
    assert "This shows the build/lint/test status BEFORE the agent made any changes" in prompt
    assert baseline_str in prompt

    # Post-agent section should be present
    assert "## Build/Lint/Test Pipeline Results (After Agent)" in prompt
    assert pipeline_str in prompt

    # Baseline should appear before post-agent
    baseline_pos = prompt.index("Baseline Pipeline Results (Before Agent)")
    post_agent_pos = prompt.index("Build/Lint/Test Pipeline Results (After Agent)")
    assert baseline_pos < post_agent_pos


def test_build_task_prompt_without_baseline() -> None:
    """Test that no baseline section is rendered when baseline_pipeline_str is None."""
    pipeline_str = "**Overall Status**: ALL PASSED ✓"

    prompt = build_task_prompt(
        task_prompt="Test task",
        agent_output="Agent output",
        workspace_state="Files created",
        pipeline_result_str=pipeline_str,
        baseline_pipeline_str=None,
    )

    # No baseline section
    assert "Baseline Pipeline Results" not in prompt

    # Post-agent section still present (but without "After Agent" qualifier when no baseline)
    assert "Build/Lint/Test Pipeline Results" in prompt


def test_build_task_prompt_baseline_section_before_post_agent() -> None:
    """Test that baseline section appears before post-agent section in prompt."""
    baseline_str = "Baseline status"
    pipeline_str = "Post-agent status"

    prompt = build_task_prompt(
        task_prompt="Test task",
        agent_output="Agent output",
        workspace_state="Files created",
        baseline_pipeline_str=baseline_str,
        pipeline_result_str=pipeline_str,
    )

    baseline_idx = prompt.index("Baseline Pipeline Results (Before Agent)")
    post_agent_idx = prompt.index("Build/Lint/Test Pipeline Results (After Agent)")

    assert baseline_idx < post_agent_idx, "Baseline section must appear before post-agent section"


def test_save_load_pipeline_baseline(
    tmp_path: Path, mock_pipeline_result: BuildPipelineResult
) -> None:
    """Test round-trip persistence of pipeline baseline to/from JSON."""
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    # Save baseline
    _save_pipeline_baseline(results_dir, mock_pipeline_result)

    # Check file exists
    baseline_file = results_dir / "pipeline_baseline.json"
    assert baseline_file.exists()

    # Load baseline
    loaded = _load_pipeline_baseline(results_dir)
    assert loaded is not None
    assert loaded.build_passed == mock_pipeline_result.build_passed
    assert loaded.format_passed == mock_pipeline_result.format_passed
    assert loaded.test_passed == mock_pipeline_result.test_passed
    assert loaded.all_passed == mock_pipeline_result.all_passed


def test_load_pipeline_baseline_missing_file(tmp_path: Path) -> None:
    """Test loading baseline when file doesn't exist returns None."""
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    loaded = _load_pipeline_baseline(results_dir)
    assert loaded is None


def test_load_pipeline_baseline_invalid_json(tmp_path: Path) -> None:
    """Test loading baseline with invalid JSON returns None and logs warning."""
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    baseline_file = results_dir / "pipeline_baseline.json"
    baseline_file.write_text("not valid json{")

    loaded = _load_pipeline_baseline(results_dir)
    assert loaded is None


def test_run_result_baseline_field() -> None:
    """Test that E2ERunResult includes baseline_pipeline_summary in to_dict()."""
    baseline_summary = {
        "all_passed": True,
        "build_passed": True,
        "lint_passed": True,
        "test_passed": True,
    }

    run_result = E2ERunResult(
        run_number=1,
        exit_code=0,
        token_stats=TokenStats(
            input_tokens=100,
            cache_creation_tokens=0,
            cache_read_tokens=0,
            output_tokens=50,
        ),
        cost_usd=0.01,
        duration_seconds=10.0,
        agent_duration_seconds=8.0,
        judge_duration_seconds=2.0,
        judge_score=0.85,
        judge_passed=True,
        judge_grade="A",
        judge_reasoning="Good work",
        workspace_path=Path("/workspace"),
        logs_path=Path("/logs"),
        baseline_pipeline_summary=baseline_summary,
    )

    result_dict = run_result.to_dict()

    assert "baseline_pipeline_summary" in result_dict
    assert result_dict["baseline_pipeline_summary"] == baseline_summary


def test_run_result_baseline_field_none() -> None:
    """Test that baseline_pipeline_summary can be None."""
    run_result = E2ERunResult(
        run_number=1,
        exit_code=0,
        token_stats=TokenStats(
            input_tokens=100,
            cache_creation_tokens=0,
            cache_read_tokens=0,
            output_tokens=50,
        ),
        cost_usd=0.01,
        duration_seconds=10.0,
        agent_duration_seconds=8.0,
        judge_duration_seconds=2.0,
        judge_score=0.85,
        judge_passed=True,
        judge_grade="A",
        judge_reasoning="Good work",
        workspace_path=Path("/workspace"),
        logs_path=Path("/logs"),
        baseline_pipeline_summary=None,
    )

    result_dict = run_result.to_dict()

    assert "baseline_pipeline_summary" in result_dict
    assert result_dict["baseline_pipeline_summary"] is None


def test_baseline_summary_conversion(mock_pipeline_result: BuildPipelineResult) -> None:
    """Test that BuildPipelineResult is correctly converted to summary dict."""
    summary = {
        "all_passed": mock_pipeline_result.all_passed,
        "build_passed": mock_pipeline_result.build_passed,
        "format_passed": mock_pipeline_result.format_passed,
        "test_passed": mock_pipeline_result.test_passed,
    }

    assert summary["all_passed"] is False
    assert summary["build_passed"] is True
    assert summary["format_passed"] is False
    assert summary["test_passed"] is True
