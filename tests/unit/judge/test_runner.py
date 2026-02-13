"""Tests for judge runner CLI module.

Python justification: Required for pytest testing framework.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scylla.judge.evaluator import JudgeScore, JudgeSummary, Judgment
from scylla.judge.runner import (
    RunnerError,
    RunnerValidationError,
    collect_workspace_state,
    load_task_prompt,
    main,
    parse_args,
    run_evaluation,
    validate_arguments,
    write_output,
)


class TestParseArgs:
    """Tests for argument parsing."""

    def test_parse_args_all_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test parsing all required arguments."""
        monkeypatch.setattr(
            "sys.argv",
            [
                "runner.py",
                "--workspace",
                "/workspace",
                "--output",
                "/output",
                "--model",
                "claude-opus-4-5-20251101",
                "--prompt",
                "/prompt/task.md",
            ],
        )

        args = parse_args()
        assert args.workspace == Path("/workspace")
        assert args.output == Path("/output")
        assert args.model == "claude-opus-4-5-20251101"
        assert args.prompt == Path("/prompt/task.md")
        assert args.timeout == 300  # default
        assert args.verbose is False

    def test_parse_args_with_optional(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test parsing with optional arguments."""
        monkeypatch.setattr(
            "sys.argv",
            [
                "runner.py",
                "--workspace",
                "/workspace",
                "--output",
                "/output",
                "--model",
                "claude-sonnet-4-5-20250929",
                "--prompt",
                "/prompt/task.md",
                "--timeout",
                "600",
                "--verbose",
            ],
        )

        args = parse_args()
        assert args.timeout == 600
        assert args.verbose is True

    def test_parse_args_missing_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test parsing fails when required arguments are missing."""
        monkeypatch.setattr("sys.argv", ["runner.py"])

        with pytest.raises(SystemExit):
            parse_args()


class TestValidateArguments:
    """Tests for argument validation."""

    def test_validate_valid_arguments(self, tmp_path: Path) -> None:
        """Test validation with valid arguments."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        output = tmp_path / "output"
        output.mkdir()

        prompt = tmp_path / "prompt.md"
        prompt.write_text("Test task prompt")

        args = MagicMock()
        args.workspace = workspace
        args.output = output
        args.prompt = prompt
        args.timeout = 300

        # Should not raise
        validate_arguments(args)

    def test_validate_creates_output_dir(self, tmp_path: Path) -> None:
        """Test validation creates output directory if missing."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        output = tmp_path / "output"
        # Don't create output directory

        prompt = tmp_path / "prompt.md"
        prompt.write_text("Test task prompt")

        args = MagicMock()
        args.workspace = workspace
        args.output = output
        args.prompt = prompt
        args.timeout = 300

        validate_arguments(args)

        # Output directory should now exist
        assert output.exists()
        assert output.is_dir()

    def test_validate_workspace_not_exists(self, tmp_path: Path) -> None:
        """Test validation fails if workspace doesn't exist."""
        workspace = tmp_path / "nonexistent"
        output = tmp_path / "output"
        prompt = tmp_path / "prompt.md"

        args = MagicMock()
        args.workspace = workspace
        args.output = output
        args.prompt = prompt
        args.timeout = 300

        with pytest.raises(RunnerValidationError, match="Workspace does not exist"):
            validate_arguments(args)

    def test_validate_workspace_not_directory(self, tmp_path: Path) -> None:
        """Test validation fails if workspace is not a directory."""
        workspace = tmp_path / "workspace_file"
        workspace.write_text("not a directory")

        output = tmp_path / "output"
        prompt = tmp_path / "prompt.md"

        args = MagicMock()
        args.workspace = workspace
        args.output = output
        args.prompt = prompt
        args.timeout = 300

        with pytest.raises(RunnerValidationError, match="Workspace is not a directory"):
            validate_arguments(args)

    def test_validate_prompt_not_exists(self, tmp_path: Path) -> None:
        """Test validation fails if prompt file doesn't exist."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        output = tmp_path / "output"
        output.mkdir()

        prompt = tmp_path / "nonexistent.md"

        args = MagicMock()
        args.workspace = workspace
        args.output = output
        args.prompt = prompt
        args.timeout = 300

        with pytest.raises(RunnerValidationError, match="Prompt file does not exist"):
            validate_arguments(args)

    def test_validate_prompt_not_file(self, tmp_path: Path) -> None:
        """Test validation fails if prompt is not a file."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        output = tmp_path / "output"
        output.mkdir()

        prompt = tmp_path / "prompt_dir"
        prompt.mkdir()

        args = MagicMock()
        args.workspace = workspace
        args.output = output
        args.prompt = prompt
        args.timeout = 300

        with pytest.raises(RunnerValidationError, match="Prompt is not a file"):
            validate_arguments(args)

    def test_validate_negative_timeout(self, tmp_path: Path) -> None:
        """Test validation fails with negative timeout."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        output = tmp_path / "output"
        output.mkdir()

        prompt = tmp_path / "prompt.md"
        prompt.write_text("Test prompt")

        args = MagicMock()
        args.workspace = workspace
        args.output = output
        args.prompt = prompt
        args.timeout = -10

        with pytest.raises(RunnerValidationError, match="Timeout must be positive"):
            validate_arguments(args)


class TestLoadTaskPrompt:
    """Tests for loading task prompts."""

    def test_load_task_prompt_success(self, tmp_path: Path) -> None:
        """Test loading task prompt successfully."""
        prompt_file = tmp_path / "task.md"
        prompt_content = "# Task\n\nConvert Justfile to Makefile"
        prompt_file.write_text(prompt_content)

        result = load_task_prompt(prompt_file)
        assert result == prompt_content

    def test_load_task_prompt_file_not_found(self, tmp_path: Path) -> None:
        """Test loading non-existent prompt file."""
        prompt_file = tmp_path / "nonexistent.md"

        with pytest.raises(RunnerError, match="Failed to load prompt file"):
            load_task_prompt(prompt_file)


class TestCollectWorkspaceState:
    """Tests for collecting workspace state."""

    def test_collect_empty_workspace(self, tmp_path: Path) -> None:
        """Test collecting state from empty workspace."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        result = collect_workspace_state(workspace)
        assert result == "Workspace is empty"

    def test_collect_workspace_with_files(self, tmp_path: Path) -> None:
        """Test collecting state from workspace with files."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        (workspace / "file1.txt").write_text("content1")
        (workspace / "file2.py").write_text("content2")
        (workspace / "subdir").mkdir()

        result = collect_workspace_state(workspace)
        assert "Workspace contents:" in result
        assert "- file1.txt" in result
        assert "- file2.py" in result
        assert "- subdir/ (directory)" in result

    def test_collect_workspace_nonexistent(self, tmp_path: Path) -> None:
        """Test collecting state from non-existent workspace."""
        workspace = tmp_path / "nonexistent"

        result = collect_workspace_state(workspace)
        assert "Error listing workspace:" in result


class TestRunEvaluation:
    """Tests for running evaluation."""

    def test_run_evaluation_basic(self, tmp_path: Path) -> None:
        """Test basic evaluation run."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        prompt = "Convert Justfile to Makefile"
        model = "claude-opus-4-5-20251101"
        timeout = 300

        judgment = run_evaluation(workspace, prompt, model, timeout)

        assert isinstance(judgment, Judgment)
        assert prompt[:50] in judgment.qualitative_feedback
        assert model in judgment.qualitative_feedback


class TestWriteOutput:
    """Tests for writing output."""

    def test_write_output_basic_judgment(self, tmp_path: Path) -> None:
        """Test writing basic judgment output."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        judgment = Judgment()
        judgment.qualitative_feedback = "Test feedback"

        write_output(judgment, output_dir)

        output_file = output_dir / "judgment.json"
        assert output_file.exists()

        data = json.loads(output_file.read_text())
        assert data["qualitative_feedback"] == "Test feedback"
        assert data["requirements"] == {}
        assert data["categories"] == {}
        assert data["summary"] is None
        assert data["exploratory_testing"] is None

    def test_write_output_complete_judgment(self, tmp_path: Path) -> None:
        """Test writing complete judgment with all fields."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        judgment = Judgment()
        judgment.requirements["R1"] = JudgeScore(score=0.8, confidence=0.9, notes="Good")
        judgment.categories["completeness"] = JudgeScore(score=0.7, confidence=0.8, notes="OK")
        judgment.summary = JudgeSummary(
            weighted_score=0.75,
            passed=True,
            letter_grade="B",
            overall_confidence=0.85,
            strengths=["Clear code"],
            weaknesses=["Missing tests"],
        )
        judgment.qualitative_feedback = "Overall good work"

        write_output(judgment, output_dir)

        output_file = output_dir / "judgment.json"
        data = json.loads(output_file.read_text())

        assert data["requirements"]["R1"]["score"] == 0.8
        assert data["requirements"]["R1"]["confidence"] == 0.9
        assert data["categories"]["completeness"]["score"] == 0.7
        assert data["summary"]["weighted_score"] == 0.75
        assert data["summary"]["passed"] is True
        assert data["summary"]["letter_grade"] == "B"
        assert data["summary"]["strengths"] == ["Clear code"]

    def test_write_output_nonexistent_directory(self, tmp_path: Path) -> None:
        """Test writing to non-existent directory fails."""
        output_dir = tmp_path / "nonexistent"

        judgment = Judgment()

        with pytest.raises(RunnerError, match="Failed to write output"):
            write_output(judgment, output_dir)


class TestMain:
    """Tests for main entry point."""

    def test_main_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test successful main execution."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "test.txt").write_text("test content")

        output = tmp_path / "output"

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("# Task\nTest task")

        monkeypatch.setattr(
            "sys.argv",
            [
                "runner.py",
                "--workspace",
                str(workspace),
                "--output",
                str(output),
                "--model",
                "claude-opus-4-5-20251101",
                "--prompt",
                str(prompt_file),
            ],
        )

        exit_code = main()

        assert exit_code == 0
        assert (output / "judgment.json").exists()

    def test_main_validation_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test main with validation error."""
        workspace = tmp_path / "nonexistent"
        output = tmp_path / "output"
        prompt_file = tmp_path / "prompt.md"

        monkeypatch.setattr(
            "sys.argv",
            [
                "runner.py",
                "--workspace",
                str(workspace),
                "--output",
                str(output),
                "--model",
                "claude-opus-4-5-20251101",
                "--prompt",
                str(prompt_file),
            ],
        )

        exit_code = main()

        assert exit_code == 1

    def test_main_missing_arguments(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test main with missing arguments."""
        monkeypatch.setattr("sys.argv", ["runner.py"])

        exit_code = main()

        assert exit_code == 1

    def test_main_verbose_mode(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test main with verbose logging enabled."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        output = tmp_path / "output"

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("# Task\nTest task")

        monkeypatch.setattr(
            "sys.argv",
            [
                "runner.py",
                "--workspace",
                str(workspace),
                "--output",
                str(output),
                "--model",
                "claude-opus-4-5-20251101",
                "--prompt",
                str(prompt_file),
                "--verbose",
            ],
        )

        exit_code = main()

        assert exit_code == 0
