"""Unit tests for E2E LLM judge evaluation."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scylla.e2e.llm_judge import (
    BuildPipelineResult,
    JudgeResult,
    _call_claude_judge,
    _create_mojo_build_script,
    _create_mojo_format_script,
    _create_mojo_scripts,
    _create_mojo_test_script,
    _create_precommit_script,
    _create_python_scripts,
    _create_run_all_script,
    _get_deleted_files,
    _get_patchfile,
    _get_pipeline_env,
    _get_workspace_state,
    _load_reference_patch,
    _parse_judge_response,
    _run_build_pipeline,
    _run_mojo_pipeline,
    _run_python_pipeline,
    _save_judge_logs,
    _save_pipeline_commands,
    _save_pipeline_outputs,
    run_llm_judge,
)


class TestJudgeResult:
    """Tests for JudgeResult dataclass."""

    def test_to_dict_with_all_fields(self) -> None:
        """Test conversion to dictionary with all fields."""
        result = JudgeResult(
            score=0.85,
            passed=True,
            grade="B",
            reasoning="Good implementation",
            is_valid=True,
            criteria_scores={"accuracy": {"score": 0.9, "explanation": "Very accurate"}},
            raw_response='{"score": 0.85}',
        )

        d = result.to_dict()

        assert d["score"] == 0.85
        assert d["passed"] is True
        assert d["grade"] == "B"
        assert d["reasoning"] == "Good implementation"
        assert d["is_valid"] is True
        assert d["criteria_scores"]["accuracy"]["score"] == 0.9
        assert "raw_response" not in d  # raw_response is excluded from dict

    def test_to_dict_with_defaults(self) -> None:
        """Test conversion with default values."""
        result = JudgeResult(
            score=0.5,
            passed=False,
            grade="C",
            reasoning="Needs improvement",
        )

        d = result.to_dict()

        assert d["score"] == 0.5
        assert d["is_valid"] is True  # Default value
        assert d["criteria_scores"] is None  # Default value

    def test_invalid_result(self) -> None:
        """Test invalid result (e.g., agent error)."""
        result = JudgeResult(
            score=0.0,
            passed=False,
            grade="N/A",
            reasoning="Agent failed to complete task",
            is_valid=False,
        )

        assert result.is_valid is False
        assert result.score == 0.0
        assert result.to_dict()["is_valid"] is False


class TestBuildPipelineResult:
    """Tests for BuildPipelineResult dataclass."""

    def test_get_failure_summary_no_failures(self) -> None:
        """Test failure summary when all steps pass."""
        result = BuildPipelineResult(
            language="python",
            build_passed=True,
            build_output="OK",
            format_passed=True,
            format_output="OK",
            test_passed=True,
            test_output="OK",
            precommit_passed=True,
            precommit_output="OK",
            all_passed=True,
        )

        assert result.get_failure_summary() == "none"

    def test_get_failure_summary_with_failures(self) -> None:
        """Test failure summary with multiple failures."""
        result = BuildPipelineResult(
            language="python",
            build_passed=False,
            build_output="Error",
            format_passed=True,
            format_output="OK",
            test_passed=False,
            test_output="Error",
            precommit_passed=True,
            precommit_output="OK",
            all_passed=False,
        )

        summary = result.get_failure_summary()
        assert "python-build" in summary
        assert "python-test" in summary
        assert "python-format" not in summary

    def test_get_failure_summary_ignores_na(self) -> None:
        """Test that N/A items are not included in failure summary."""
        result = BuildPipelineResult(
            language="mojo",
            build_passed=False,
            build_output="Error",
            format_passed=False,
            format_output="Not available",
            format_na=True,
            test_passed=False,
            test_output="Not available",
            test_na=True,
            precommit_passed=True,
            precommit_output="OK",
            all_passed=False,
        )

        summary = result.get_failure_summary()
        assert "mojo-build" in summary
        assert "mojo-format" not in summary  # N/A, should be ignored
        assert "mojo-test" not in summary  # N/A, should be ignored

    def test_has_na_items(self) -> None:
        """Test detection of N/A items."""
        result_with_na = BuildPipelineResult(
            language="python",
            build_passed=True,
            build_output="OK",
            test_passed=True,
            test_na=True,
            test_output="No tests",
        )

        result_without_na = BuildPipelineResult(
            language="python",
            build_passed=True,
            build_output="OK",
        )

        assert result_with_na.has_na_items() is True
        assert result_without_na.has_na_items() is False

    def test_get_status_summary(self) -> None:
        """Test status summary with emojis."""
        result = BuildPipelineResult(
            language="python",
            build_passed=True,
            build_output="OK",
            format_passed=False,
            format_output="Error",
            test_passed=True,
            test_na=True,
            test_output="No tests",
            precommit_passed=True,
            precommit_output="OK",
        )

        summary = result.get_status_summary()
        assert "python-build(✅)" in summary
        assert "python-format(❌)" in summary
        assert "python-test(🏳️)" in summary  # N/A
        assert "pre-commit(✅)" in summary

    def test_to_context_string(self) -> None:
        """Test formatting for judge context."""
        result = BuildPipelineResult(
            language="python",
            build_passed=True,
            build_output="All files OK",
            format_passed=False,
            format_output="Style issues",
            test_passed=True,
            test_output="5 passed",
            precommit_passed=True,
            precommit_output="OK",
        )

        context = result.to_context_string()
        assert "### Python Build (PASSED)" in context
        assert "### Python Format Check (FAILED)" in context
        assert "All files OK" in context
        assert "Style issues" in context

    def test_to_context_string_truncates_long_output(self) -> None:
        """Test that output is truncated to 2000 chars."""
        long_output = "x" * 3000
        result = BuildPipelineResult(
            language="mojo",
            build_passed=True,
            build_output=long_output,
        )

        context = result.to_context_string()
        # Should contain truncated output (2000 chars max)
        assert len(context) < len(long_output)


class TestGetPipelineEnv:
    """Tests for _get_pipeline_env helper."""

    def test_sets_pycache_prefix(self) -> None:
        """Test that PYTHONPYCACHEPREFIX is set under tempfile.gettempdir()."""
        env = _get_pipeline_env()

        assert "PYTHONPYCACHEPREFIX" in env
        assert env["PYTHONPYCACHEPREFIX"].startswith(tempfile.gettempdir())

    def test_pycache_prefix_uses_scylla_subdir(self) -> None:
        """Test that PYTHONPYCACHEPREFIX ends with scylla_pycache subdir."""
        env = _get_pipeline_env()

        assert env["PYTHONPYCACHEPREFIX"].endswith("scylla_pycache")

    def test_inherits_os_environ(self) -> None:
        """_get_pipeline_env returns a copy of os.environ with additions."""
        env = _get_pipeline_env()

        # Should inherit PATH from os.environ
        assert "PATH" in env or len(env) > 1
        # Should not be the same object as os.environ
        assert env is not os.environ


class TestRunPythonPipeline:
    """Tests for _run_python_pipeline."""

    def test_successful_python_pipeline(self, tmp_path: Path) -> None:
        """Test successful Python pipeline execution."""
        # Mock all subprocess calls to succeed
        success_result = MagicMock()
        success_result.returncode = 0
        success_result.stdout = "OK"
        success_result.stderr = ""

        with patch("subprocess.run", return_value=success_result):
            result = _run_python_pipeline(tmp_path)

        assert result.language == "python"
        assert result.build_passed is True
        assert result.format_passed is True
        assert result.test_passed is True
        assert result.precommit_passed is True
        assert result.all_passed is True

    def test_python_syntax_check_failure(self, tmp_path: Path) -> None:
        """Test Python syntax check failure."""
        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stdout = ""
        fail_result.stderr = "SyntaxError: invalid syntax"

        success_result = MagicMock()
        success_result.returncode = 0
        success_result.stdout = "OK"
        success_result.stderr = ""

        with patch(
            "subprocess.run",
            side_effect=[fail_result, success_result, success_result, success_result],
        ):
            result = _run_python_pipeline(tmp_path)

        assert result.build_passed is False
        assert "SyntaxError" in result.build_output
        assert result.all_passed is False

    def test_python_pytest_no_tests(self, tmp_path: Path) -> None:
        """Test pytest with no tests collected (exit code 5)."""
        success_result = MagicMock()
        success_result.returncode = 0
        success_result.stdout = "OK"
        success_result.stderr = ""

        no_tests_result = MagicMock()
        no_tests_result.returncode = 5
        no_tests_result.stdout = "no tests ran"
        no_tests_result.stderr = ""

        with patch(
            "subprocess.run",
            side_effect=[success_result, success_result, no_tests_result, success_result],
        ):
            result = _run_python_pipeline(tmp_path)

        assert result.test_passed is True
        assert result.test_na is True

    def test_python_ruff_not_found(self, tmp_path: Path) -> None:
        """Test when ruff is not installed."""
        success_result = MagicMock()
        success_result.returncode = 0
        success_result.stdout = "OK"
        success_result.stderr = ""

        with patch(
            "subprocess.run",
            side_effect=[success_result, FileNotFoundError(), success_result, success_result],
        ):
            result = _run_python_pipeline(tmp_path)

        assert result.format_passed is True
        assert result.format_na is True
        assert "ruff not available" in result.format_output

    def test_python_precommit_not_found(self, tmp_path: Path) -> None:
        """Test when pre-commit is not installed."""
        success_result = MagicMock()
        success_result.returncode = 0
        success_result.stdout = "OK"
        success_result.stderr = ""

        with patch(
            "subprocess.run",
            side_effect=[success_result, success_result, success_result, FileNotFoundError()],
        ):
            result = _run_python_pipeline(tmp_path)

        assert result.precommit_passed is True
        assert result.precommit_na is True


class TestRunMojoPipeline:
    """Tests for _run_mojo_pipeline."""

    def test_successful_mojo_pipeline_standalone(self, tmp_path: Path) -> None:
        """Test successful Mojo pipeline in standalone repo."""
        success_result = MagicMock()
        success_result.returncode = 0
        success_result.stdout = "OK"
        success_result.stderr = ""

        with patch("subprocess.run", return_value=success_result):
            result = _run_mojo_pipeline(tmp_path)

        assert result.language == "mojo"
        assert result.build_passed is True
        assert result.format_passed is True
        assert result.test_passed is True
        assert result.all_passed is True

    def test_mojo_pipeline_modular_repo(self, tmp_path: Path) -> None:
        """Test Mojo pipeline in modular monorepo."""
        # Create modular repo structure
        (tmp_path / "bazelw").touch()
        (tmp_path / "mojo").mkdir()

        success_result = MagicMock()
        success_result.returncode = 0
        success_result.stdout = "OK"
        success_result.stderr = ""

        with patch("subprocess.run", return_value=success_result):
            result = _run_mojo_pipeline(tmp_path)

        assert result.language == "mojo"
        assert result.all_passed is True

    def test_mojo_build_timeout(self, tmp_path: Path) -> None:
        """Test Mojo build timeout."""
        success_result = MagicMock()
        success_result.returncode = 0
        success_result.stdout = "OK"
        success_result.stderr = ""

        timeout_exc = subprocess.TimeoutExpired(cmd=["mojo", "build"], timeout=300)

        with patch(
            "subprocess.run",
            side_effect=[timeout_exc, success_result, success_result, success_result],
        ):
            result = _run_mojo_pipeline(tmp_path)

        assert result.build_passed is False
        assert "timed out" in result.build_output

    def test_mojo_test_no_tests(self, tmp_path: Path) -> None:
        """Test Mojo test with no tests found."""
        success_result = MagicMock()
        success_result.returncode = 0
        success_result.stdout = "OK"
        success_result.stderr = ""

        no_tests_result = MagicMock()
        no_tests_result.returncode = 5
        no_tests_result.stdout = "No tests found"
        no_tests_result.stderr = ""

        with patch(
            "subprocess.run",
            side_effect=[success_result, success_result, no_tests_result, success_result],
        ):
            result = _run_mojo_pipeline(tmp_path)

        assert result.test_passed is True
        assert result.test_na is True


class TestRunBuildPipeline:
    """Tests for _run_build_pipeline router."""

    def test_routes_to_python(self, tmp_path: Path) -> None:
        """Test routing to Python pipeline."""
        with patch("scylla.e2e.llm_judge._run_python_pipeline") as mock_python:
            mock_python.return_value = BuildPipelineResult(
                language="python", build_passed=True, build_output="OK"
            )
            _run_build_pipeline(tmp_path, language="python")
            mock_python.assert_called_once_with(tmp_path)

    def test_routes_to_mojo(self, tmp_path: Path) -> None:
        """Test routing to Mojo pipeline."""
        with patch("scylla.e2e.llm_judge._run_mojo_pipeline") as mock_mojo:
            mock_mojo.return_value = BuildPipelineResult(
                language="mojo", build_passed=True, build_output="OK"
            )
            _run_build_pipeline(tmp_path, language="mojo")
            mock_mojo.assert_called_once_with(tmp_path)


class TestGetWorkspaceState:
    """Tests for _get_workspace_state."""

    def test_workspace_state_with_changes(self, tmp_path: Path) -> None:
        """Test getting workspace state with changes."""
        # Mock git status output
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = " M file1.py\n A file2.py\n?? file3.py\n D old.py\n"

        with patch("subprocess.run", return_value=mock_result):
            state = _get_workspace_state(tmp_path)

        assert "file1.py` (modified)" in state
        assert "file2.py` (added)" in state
        assert "file3.py` (created)" in state
        assert "old.py` (deleted)" in state

    def test_workspace_state_no_changes(self, tmp_path: Path) -> None:
        """Test workspace state with no changes."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            state = _get_workspace_state(tmp_path)

        assert "(no changes detected)" in state

    def test_workspace_state_excludes_test_config(self, tmp_path: Path) -> None:
        """Test that test config files are excluded."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = " M CLAUDE.md\n M .claude/agents/test.md\n M real_file.py\n"

        with patch("subprocess.run", return_value=mock_result):
            state = _get_workspace_state(tmp_path)

        assert "CLAUDE.md" not in state
        assert ".claude/agents" not in state
        assert "real_file.py" in state

    def test_workspace_state_git_error(self, tmp_path: Path) -> None:
        """Test error handling when git status fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            state = _get_workspace_state(tmp_path)

        assert "(unable to get workspace state)" in state


class TestGetPatchfile:
    """Tests for _get_patchfile."""

    def test_patchfile_with_changes(self, tmp_path: Path) -> None:
        """Test generating patchfile with changes."""
        mock_unstaged = MagicMock()
        mock_unstaged.returncode = 0
        mock_unstaged.stdout = "diff --git a/file.py\n+new line"

        mock_staged = MagicMock()
        mock_staged.returncode = 0
        mock_staged.stdout = "diff --git b/other.py\n-old line"

        with patch("subprocess.run", side_effect=[mock_unstaged, mock_staged]):
            patch_str = _get_patchfile(tmp_path)

        assert "## Unstaged Changes" in patch_str
        assert "## Staged Changes" in patch_str
        assert "+new line" in patch_str
        assert "-old line" in patch_str

    def test_patchfile_no_changes(self, tmp_path: Path) -> None:
        """Test patchfile with no changes."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            patch_str = _get_patchfile(tmp_path)

        assert "(no changes detected)" in patch_str

    def test_patchfile_truncates_long_diff(self, tmp_path: Path) -> None:
        """Test that very long diffs are truncated."""
        # Create a diff with 600 lines
        long_diff = "\n".join([f"line {i}" for i in range(600)])
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = long_diff

        with patch("subprocess.run", return_value=mock_result):
            patch_str = _get_patchfile(tmp_path)

        assert "... (truncated)" in patch_str

    def test_patchfile_timeout(self, tmp_path: Path) -> None:
        """Test timeout handling."""
        with patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["git"], timeout=30)
        ):
            patch_str = _get_patchfile(tmp_path)

        assert "(git diff timed out)" in patch_str


class TestGetDeletedFiles:
    """Tests for _get_deleted_files."""

    def test_get_deleted_files(self, tmp_path: Path) -> None:
        """Test getting list of deleted files."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "deleted1.py\ndeleted2.py\n"

        with patch("subprocess.run", return_value=mock_result):
            deleted = _get_deleted_files(tmp_path)

        assert deleted == ["deleted1.py", "deleted2.py"]

    def test_get_deleted_files_none(self, tmp_path: Path) -> None:
        """Test when no files are deleted."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            deleted = _get_deleted_files(tmp_path)

        assert deleted == []

    def test_get_deleted_files_error(self, tmp_path: Path) -> None:
        """Test error handling."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            deleted = _get_deleted_files(tmp_path)

        assert deleted == []


class TestLoadReferencePatch:
    """Tests for _load_reference_patch."""

    def test_load_existing_patch(self, tmp_path: Path) -> None:
        """Test loading an existing reference patch."""
        patch_file = tmp_path / "reference.patch"
        patch_file.write_text("diff --git a/file.py\n+changes")

        content = _load_reference_patch(patch_file)

        assert content == "diff --git a/file.py\n+changes"

    def test_load_nonexistent_patch(self, tmp_path: Path) -> None:
        """Test loading a nonexistent patch."""
        patch_file = tmp_path / "nonexistent.patch"

        content = _load_reference_patch(patch_file)

        assert content is None

    def test_load_patch_read_error(self, tmp_path: Path) -> None:
        """Test error handling when reading patch."""
        patch_file = tmp_path / "patch.txt"
        patch_file.write_text("content")

        with patch("pathlib.Path.read_text", side_effect=PermissionError()):
            content = _load_reference_patch(patch_file)

        assert content is None


class TestParseJudgeResponse:
    """Tests for _parse_judge_response."""

    def test_parse_valid_response(self) -> None:
        """Test parsing a valid JSON response."""
        response = '{"score": 0.85, "passed": true, "reasoning": "Good work"}'

        result = _parse_judge_response(response)

        assert result.score == 0.85
        assert result.passed is True
        assert result.reasoning == "Good work"
        assert result.grade == "A"  # 0.85 should map to A (>= 0.80)

    def test_parse_response_with_criteria_scores(self) -> None:
        """Test parsing response with criteria scores."""
        response = json.dumps(
            {
                "score": 0.9,
                "passed": True,
                "reasoning": "Excellent",
                "categories": {
                    "accuracy": {"score": 0.95, "explanation": "Very accurate"},
                    "completeness": {"score": 0.85, "explanation": "Mostly complete"},
                },
            }
        )

        result = _parse_judge_response(response)

        assert result.criteria_scores is not None
        assert result.criteria_scores["accuracy"]["score"] == 0.95

    def test_parse_response_with_old_format(self) -> None:
        """Test parsing old format with criteria_scores instead of categories."""
        response = json.dumps(
            {
                "score": 0.8,
                "passed": True,
                "reasoning": "Good",
                "criteria_scores": {"quality": {"score": 0.8, "explanation": "Good quality"}},
            }
        )

        result = _parse_judge_response(response)

        assert result.criteria_scores is not None
        assert result.criteria_scores["quality"]["score"] == 0.8

    def test_parse_response_clamps_score(self) -> None:
        """Test that score is clamped to [0, 1] range."""
        response_high = '{"score": 1.5, "passed": true, "reasoning": "Too high"}'
        response_low = '{"score": -0.2, "passed": false, "reasoning": "Too low"}'

        result_high = _parse_judge_response(response_high)
        result_low = _parse_judge_response(response_low)

        assert result_high.score == 1.0
        assert result_low.score == 0.0

    def test_parse_response_missing_json(self) -> None:
        """Test error when response has no JSON."""
        response = "This is not JSON"

        with pytest.raises(ValueError, match="does not contain valid JSON"):
            _parse_judge_response(response)

    def test_parse_response_missing_score(self) -> None:
        """Test error when response missing score field."""
        response = '{"passed": true, "reasoning": "No score"}'

        with pytest.raises(ValueError, match="missing required 'score' field"):
            _parse_judge_response(response)

    def test_parse_response_with_markdown_wrapper(self) -> None:
        """Test parsing JSON wrapped in markdown code block."""
        response = """Here's the evaluation:

```json
{
    "score": 0.7,
    "passed": true,
    "reasoning": "Acceptable work"
}
```

That's my assessment."""

        result = _parse_judge_response(response)

        assert result.score == 0.7
        assert result.passed is True


class TestCallClaudeJudge:
    """Tests for _call_claude_judge."""

    def test_successful_judge_call(self, tmp_path: Path) -> None:
        """Test successful Claude judge call."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"score": 0.9, "passed": true, "reasoning": "Excellent"}'
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            stdout, _stderr, response = _call_claude_judge(
                "Evaluate this task", "claude-opus-4-5-20251101", tmp_path
            )

        assert '{"score": 0.9' in stdout
        assert response == stdout

    def test_judge_call_with_json_error(self, tmp_path: Path) -> None:
        """Test handling of JSON error response."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = json.dumps({"is_error": True, "error": "Rate limit exceeded"})
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="Rate limit exceeded"):
                _call_claude_judge("Evaluate", "claude-opus-4-5-20251101", tmp_path)

    def test_judge_call_with_rate_limit(self, tmp_path: Path) -> None:
        """Test rate limit detection."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Error: rate_limit_error"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            with patch("scylla.e2e.rate_limit.detect_rate_limit") as mock_detect:
                mock_detect.return_value = {"type": "rate_limit"}

                with pytest.raises(Exception):  # RateLimitError
                    _call_claude_judge("Evaluate", "claude-opus-4-5-20251101", tmp_path)


class TestSavePipelineOutputs:
    """Tests for _save_pipeline_outputs."""

    def test_save_python_outputs(self, tmp_path: Path) -> None:
        """Test saving Python pipeline outputs."""
        result = BuildPipelineResult(
            language="python",
            build_passed=True,
            build_output="Build OK",
            format_passed=False,
            format_output="Format issues",
            test_passed=True,
            test_output="Tests passed",
            precommit_passed=True,
            precommit_output="Pre-commit OK",
        )

        _save_pipeline_outputs(tmp_path, result, language="python")

        assert (tmp_path / "commands" / "python_build_output.log").read_text() == "Build OK"
        assert (tmp_path / "commands" / "python_format_output.log").read_text() == "Format issues"
        assert (tmp_path / "commands" / "python_test_output.log").read_text() == "Tests passed"
        assert (tmp_path / "commands" / "precommit_output.log").read_text() == "Pre-commit OK"

    def test_save_mojo_outputs(self, tmp_path: Path) -> None:
        """Test saving Mojo pipeline outputs."""
        result = BuildPipelineResult(
            language="mojo",
            build_passed=True,
            build_output="Build OK",
        )

        _save_pipeline_outputs(tmp_path, result, language="mojo")

        assert (tmp_path / "commands" / "mojo_build_output.log").read_text() == "Build OK"


class TestSavePipelineCommands:
    """Tests for _save_pipeline_commands."""

    def test_save_python_commands(self, tmp_path: Path) -> None:
        """Test saving Python pipeline commands."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _save_pipeline_commands(tmp_path, workspace, language="python")

        # Check that scripts are created
        assert (tmp_path / "commands" / "python_check.sh").exists()
        assert (tmp_path / "commands" / "python_format.sh").exists()
        assert (tmp_path / "commands" / "python_test.sh").exists()
        assert (tmp_path / "commands" / "precommit.sh").exists()
        assert (tmp_path / "commands" / "run_all.sh").exists()

        # Check that scripts are executable
        assert (tmp_path / "commands" / "python_check.sh").stat().st_mode & 0o100

    def test_save_mojo_commands_standalone(self, tmp_path: Path) -> None:
        """Test saving Mojo commands for standalone repo."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _save_pipeline_commands(tmp_path, workspace, language="mojo")

        # Check scripts exist
        assert (tmp_path / "commands" / "mojo_build.sh").exists()
        assert (tmp_path / "commands" / "mojo_format.sh").exists()

        # Check content uses pixi
        build_script = (tmp_path / "commands" / "mojo_build.sh").read_text()
        assert "pixi run mojo build" in build_script

    def test_save_mojo_commands_modular(self, tmp_path: Path) -> None:
        """Test saving Mojo commands for modular repo."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "bazelw").touch()
        (workspace / "mojo").mkdir()

        _save_pipeline_commands(tmp_path, workspace, language="mojo")

        # Check content uses bazelw
        build_script = (tmp_path / "commands" / "mojo_build.sh").read_text()
        assert "./bazelw build //mojo/..." in build_script


class TestSaveJudgeLogs:
    """Tests for _save_judge_logs."""

    def test_save_judge_logs(self, tmp_path: Path) -> None:
        """Test saving judge logs."""
        judge_dir = tmp_path / "run_01" / "judge" / "judge_01"
        result = JudgeResult(
            score=0.8,
            passed=True,
            grade="B",
            reasoning="Good work",
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "1.0.0"

            _save_judge_logs(
                judge_dir,
                "Task prompt",
                '{"score": 0.8}',
                result,
                "claude-opus-4-5-20251101",
                tmp_path / "workspace",
                raw_stdout="stdout content",
                raw_stderr="stderr content",
            )

        # Check files created
        assert (tmp_path / "run_01" / "judge_prompt.md").exists()
        assert (judge_dir / "response.txt").exists()
        assert (judge_dir / "judgment.json").exists()
        assert (judge_dir / "stdout.log").exists()
        assert (judge_dir / "stderr.log").exists()
        assert (judge_dir / "MODEL.md").exists()
        assert (judge_dir / "replay.sh").exists()

        # Check replay script is executable
        assert (judge_dir / "replay.sh").stat().st_mode & 0o100

        # Check judgment.json content
        judgment = json.loads((judge_dir / "judgment.json").read_text())
        assert judgment["score"] == 0.8
        assert judgment["passed"] is True


class TestRunLlmJudge:
    """Tests for run_llm_judge main function."""

    def test_run_llm_judge_basic(self, tmp_path: Path) -> None:
        """Test basic LLM judge execution."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Mock pipeline
        mock_pipeline_result = BuildPipelineResult(
            language="python",
            build_passed=True,
            build_output="OK",
            all_passed=True,
        )

        with (
            patch(
                "scylla.e2e.llm_judge._get_workspace_state",
                return_value="Files modified/created by agent:\n(no changes detected)",
            ),
            patch("scylla.e2e.llm_judge._get_patchfile", return_value="(no changes detected)"),
        ):
            with patch("scylla.e2e.llm_judge._get_deleted_files", return_value=[]):
                with patch(
                    "scylla.e2e.llm_judge._run_build_pipeline",
                    return_value=mock_pipeline_result,
                ):
                    with patch("scylla.e2e.llm_judge._call_claude_judge") as mock_judge:
                        mock_judge.return_value = (
                            '{"score": 0.9, "passed": true, "reasoning": "Excellent work"}',
                            "",
                            '{"score": 0.9, "passed": true, "reasoning": "Excellent work"}',
                        )

                        result = run_llm_judge(
                            workspace=workspace,
                            task_prompt="Complete the task",
                            agent_output="Task completed",
                            model="claude-opus-4-5-20251101",
                        )

        assert result.score == 0.9
        assert result.passed is True
        assert result.grade == "A"

    def test_run_llm_judge_without_pipeline(self, tmp_path: Path) -> None:
        """Test judge without build pipeline."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        with patch("scylla.e2e.llm_judge._get_workspace_state", return_value="(no changes)"):
            with patch("scylla.e2e.llm_judge._get_patchfile", return_value="(no changes)"):
                with patch("scylla.e2e.llm_judge._get_deleted_files", return_value=[]):
                    with patch("scylla.e2e.llm_judge._call_claude_judge") as mock_judge:
                        mock_judge.return_value = (
                            '{"score": 0.7, "passed": true, "reasoning": "Good"}',
                            "",
                            '{"score": 0.7, "passed": true, "reasoning": "Good"}',
                        )

                        result = run_llm_judge(
                            workspace=workspace,
                            task_prompt="Task",
                            agent_output="Output",
                            run_build_pipeline=False,
                        )

        assert result.score == 0.7

    def test_run_llm_judge_with_judge_dir(self, tmp_path: Path) -> None:
        """Test judge with output directory."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        judge_dir = tmp_path / "judge"

        mock_pipeline_result = BuildPipelineResult(
            language="python",
            build_passed=True,
            build_output="OK",
            all_passed=True,
        )

        with patch("scylla.e2e.llm_judge._get_workspace_state", return_value="(no changes)"):
            with patch("scylla.e2e.llm_judge._get_patchfile", return_value="(no changes)"):
                with patch("scylla.e2e.llm_judge._get_deleted_files", return_value=[]):
                    with patch(
                        "scylla.e2e.llm_judge._run_build_pipeline",
                        return_value=mock_pipeline_result,
                    ):
                        with patch("scylla.e2e.llm_judge._call_claude_judge") as mock_judge:
                            mock_judge.return_value = (
                                '{"score": 0.8, "passed": true, "reasoning": "Good"}',
                                "",
                                '{"score": 0.8, "passed": true, "reasoning": "Good"}',
                            )

                            result = run_llm_judge(
                                workspace=workspace,
                                task_prompt="Task",
                                agent_output="Output",
                                judge_dir=judge_dir,
                            )

        # Check that judge directory was created
        assert (judge_dir / "judge_01").exists()
        assert (judge_dir / "judge_01" / "judgment.json").exists()
        assert result.score == 0.8


class TestPipelineCommandGeneration:
    """Tests for pipeline command script generation helper functions."""

    def test_create_python_scripts(self, tmp_path: Path) -> None:
        """Test Python script generation."""
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _create_python_scripts(commands_dir, workspace)

        # Verify scripts created
        assert (commands_dir / "python_check.sh").exists()
        assert (commands_dir / "python_format.sh").exists()
        assert (commands_dir / "python_test.sh").exists()

        # Verify executable permissions
        assert (commands_dir / "python_check.sh").stat().st_mode & 0o111
        assert (commands_dir / "python_format.sh").stat().st_mode & 0o111
        assert (commands_dir / "python_test.sh").stat().st_mode & 0o111

        # Verify content
        check_content = (commands_dir / "python_check.sh").read_text()
        assert "python -m compileall" in check_content
        assert str(workspace) in check_content

        format_content = (commands_dir / "python_format.sh").read_text()
        assert "ruff check" in format_content
        assert str(workspace) in format_content

        test_content = (commands_dir / "python_test.sh").read_text()
        assert "pytest -v" in test_content
        assert str(workspace) in test_content

    def test_create_mojo_build_script_modular(self, tmp_path: Path) -> None:
        """Test Mojo build script generation for modular repo."""
        build_script = tmp_path / "mojo_build.sh"
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _create_mojo_build_script(build_script, workspace, is_modular=True)

        assert build_script.exists()
        assert build_script.stat().st_mode & 0o111  # Executable

        content = build_script.read_text()
        assert "./bazelw build //mojo/..." in content
        assert str(workspace) in content
        assert "modular repo" in content

    def test_create_mojo_build_script_standalone(self, tmp_path: Path) -> None:
        """Test Mojo build script generation for standalone repo."""
        build_script = tmp_path / "mojo_build.sh"
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _create_mojo_build_script(build_script, workspace, is_modular=False)

        assert build_script.exists()
        content = build_script.read_text()
        assert "pixi run mojo build" in content
        assert str(workspace) in content

    def test_create_mojo_format_script_modular(self, tmp_path: Path) -> None:
        """Test Mojo format script generation for modular repo."""
        format_script = tmp_path / "mojo_format.sh"
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _create_mojo_format_script(format_script, workspace, is_modular=True)

        assert format_script.exists()
        assert format_script.stat().st_mode & 0o111  # Executable

        content = format_script.read_text()
        assert "./bazelw run format" in content
        assert str(workspace) in content

    def test_create_mojo_format_script_standalone_with_mojo_dir(self, tmp_path: Path) -> None:
        """Test Mojo format script with mojo/ subdirectory."""
        format_script = tmp_path / "mojo_format.sh"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        mojo_dir = workspace / "mojo"
        mojo_dir.mkdir()

        _create_mojo_format_script(format_script, workspace, is_modular=False)

        assert format_script.exists()
        content = format_script.read_text()
        assert 'cd "$WORKSPACE/mojo"' in content
        assert "pixi run mojo format" in content

    def test_create_mojo_format_script_standalone_no_mojo_dir(self, tmp_path: Path) -> None:
        """Test Mojo format script without mojo/ subdirectory."""
        format_script = tmp_path / "mojo_format.sh"
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _create_mojo_format_script(format_script, workspace, is_modular=False)

        assert format_script.exists()
        content = format_script.read_text()
        assert 'cd "$WORKSPACE"' in content
        assert "pixi run mojo format" in content

    def test_create_mojo_test_script_modular(self, tmp_path: Path) -> None:
        """Test Mojo test script generation for modular repo."""
        test_script = tmp_path / "mojo_test.sh"
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _create_mojo_test_script(test_script, workspace, is_modular=True)

        assert test_script.exists()
        assert test_script.stat().st_mode & 0o111  # Executable

        content = test_script.read_text()
        assert 'cd "$WORKSPACE/mojo"' in content
        assert "pixi run tests" in content

    def test_create_mojo_test_script_standalone(self, tmp_path: Path) -> None:
        """Test Mojo test script generation for standalone repo."""
        test_script = tmp_path / "mojo_test.sh"
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _create_mojo_test_script(test_script, workspace, is_modular=False)

        assert test_script.exists()
        content = test_script.read_text()
        assert "pixi run mojo test" in content
        assert str(workspace) in content

    def test_create_mojo_scripts(self, tmp_path: Path) -> None:
        """Test Mojo scripts orchestrator."""
        # Clear cache before test to ensure fresh call
        from scylla.e2e.repo_detection import is_modular_repo

        is_modular_repo.cache_clear()

        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _create_mojo_scripts(commands_dir, workspace)

        # Verify all Mojo scripts created
        assert (commands_dir / "mojo_build.sh").exists()
        assert (commands_dir / "mojo_format.sh").exists()
        assert (commands_dir / "mojo_test.sh").exists()

    def test_create_precommit_script(self, tmp_path: Path) -> None:
        """Test pre-commit script generation."""
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _create_precommit_script(commands_dir, workspace)

        precommit_script = commands_dir / "precommit.sh"
        assert precommit_script.exists()
        assert precommit_script.stat().st_mode & 0o111  # Executable

        content = precommit_script.read_text()
        assert "pre-commit run --all-files" in content
        assert str(workspace) in content

    def test_create_run_all_script_python(self, tmp_path: Path) -> None:
        """Test run_all.sh generation for Python."""
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()

        _create_run_all_script(commands_dir, language="python")

        run_all_script = commands_dir / "run_all.sh"
        assert run_all_script.exists()
        assert run_all_script.stat().st_mode & 0o111  # Executable

        content = run_all_script.read_text()
        assert "python_check.sh" in content
        assert "python_format.sh" in content
        assert "python_test.sh" in content
        assert "precommit.sh" in content
        assert "All checks completed" in content

    def test_create_run_all_script_mojo(self, tmp_path: Path) -> None:
        """Test run_all.sh generation for Mojo."""
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()

        _create_run_all_script(commands_dir, language="mojo")

        run_all_script = commands_dir / "run_all.sh"
        assert run_all_script.exists()
        assert run_all_script.stat().st_mode & 0o111  # Executable

        content = run_all_script.read_text()
        assert "mojo_build.sh" in content
        assert "mojo_format.sh" in content
        assert "mojo_test.sh" in content
        assert "precommit.sh" in content
        assert "All checks completed" in content

    def test_save_pipeline_commands_python_integration(self, tmp_path: Path) -> None:
        """Test end-to-end pipeline command generation for Python."""
        run_dir = tmp_path / "run_01"
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _save_pipeline_commands(run_dir, workspace, language="python")

        commands_dir = run_dir / "commands"
        assert commands_dir.exists()

        # Verify all Python scripts created
        assert (commands_dir / "python_check.sh").exists()
        assert (commands_dir / "python_format.sh").exists()
        assert (commands_dir / "python_test.sh").exists()
        assert (commands_dir / "precommit.sh").exists()
        assert (commands_dir / "run_all.sh").exists()

        # Verify run_all.sh references Python scripts
        run_all_content = (commands_dir / "run_all.sh").read_text()
        assert "python_check.sh" in run_all_content

    def test_save_pipeline_commands_mojo_integration(self, tmp_path: Path) -> None:
        """Test end-to-end pipeline command generation for Mojo."""
        # Clear cache before test to ensure fresh call
        from scylla.e2e.repo_detection import is_modular_repo

        is_modular_repo.cache_clear()

        run_dir = tmp_path / "run_01"
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _save_pipeline_commands(run_dir, workspace, language="mojo")

        commands_dir = run_dir / "commands"
        assert commands_dir.exists()

        # Verify all Mojo scripts created
        assert (commands_dir / "mojo_build.sh").exists()
        assert (commands_dir / "mojo_format.sh").exists()
        assert (commands_dir / "mojo_test.sh").exists()
        assert (commands_dir / "precommit.sh").exists()
        assert (commands_dir / "run_all.sh").exists()

        # Verify run_all.sh references Mojo scripts
        run_all_content = (commands_dir / "run_all.sh").read_text()
        assert "mojo_build.sh" in run_all_content
