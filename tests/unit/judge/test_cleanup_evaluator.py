"""Tests for cleanup script evaluation.

Python justification: Required for pytest testing framework.
"""

from pathlib import Path

from scylla.judge.cleanup_evaluator import (
    CleanupEvaluation,
    CleanupEvaluator,
)


class TestCleanupEvaluation:
    """Tests for CleanupEvaluation dataclass."""

    def test_create_evaluation(self) -> None:
        evaluation = CleanupEvaluation(
            script_exists=True,
            script_path=Path("/workspace/cleanup.sh"),
            execution_success=True,
            execution_output="Cleaned up",
            cleanup_complete=True,
            artifacts_remaining=[],
            score=1.0,
            notes="Cleanup successful",
        )
        assert evaluation.script_exists is True
        assert evaluation.score == 1.0

    def test_no_script_evaluation(self) -> None:
        evaluation = CleanupEvaluation(
            script_exists=False,
            script_path=None,
            execution_success=False,
            execution_output="",
            cleanup_complete=False,
            score=0.0,
            notes="No cleanup script found",
        )
        assert evaluation.script_exists is False
        assert evaluation.score == 0.0


class TestCleanupEvaluatorFindScript:
    """Tests for find_cleanup_script method."""

    def test_finds_cleanup_sh(self, tmp_path: Path) -> None:
        (tmp_path / "cleanup.sh").write_text("#!/bin/bash\necho 'clean'")
        evaluator = CleanupEvaluator(tmp_path)
        script = evaluator.find_cleanup_script()
        assert script is not None
        assert script.name == "cleanup.sh"

    def test_finds_scripts_cleanup_sh(self, tmp_path: Path) -> None:
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "cleanup.sh").write_text("#!/bin/bash\necho 'clean'")
        evaluator = CleanupEvaluator(tmp_path)
        script = evaluator.find_cleanup_script()
        assert script is not None
        assert str(script).endswith("scripts/cleanup.sh")

    def test_finds_makefile_with_clean(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("clean:\n\trm -rf build\n")
        evaluator = CleanupEvaluator(tmp_path)
        script = evaluator.find_cleanup_script()
        assert script is not None
        assert script.name == "Makefile"

    def test_ignores_makefile_without_clean(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("build:\n\techo 'building'\n")
        evaluator = CleanupEvaluator(tmp_path)
        script = evaluator.find_cleanup_script()
        assert script is None

    def test_no_script_found(self, tmp_path: Path) -> None:
        evaluator = CleanupEvaluator(tmp_path)
        script = evaluator.find_cleanup_script()
        assert script is None

    def test_priority_order(self, tmp_path: Path) -> None:
        """cleanup.sh should be found before Makefile."""
        (tmp_path / "cleanup.sh").write_text("#!/bin/bash\necho 'clean'")
        (tmp_path / "Makefile").write_text("clean:\n\trm -rf build\n")
        evaluator = CleanupEvaluator(tmp_path)
        script = evaluator.find_cleanup_script()
        assert script is not None
        assert script.name == "cleanup.sh"


class TestCleanupEvaluatorMakefileHasClean:
    """Tests for _makefile_has_clean method."""

    def test_clean_target(self, tmp_path: Path) -> None:
        makefile = tmp_path / "Makefile"
        makefile.write_text("clean:\n\trm -rf build\n")
        evaluator = CleanupEvaluator(tmp_path)
        assert evaluator._makefile_has_clean(makefile) is True

    def test_clean_target_with_space(self, tmp_path: Path) -> None:
        makefile = tmp_path / "Makefile"
        makefile.write_text("clean :\n\trm -rf build\n")
        evaluator = CleanupEvaluator(tmp_path)
        assert evaluator._makefile_has_clean(makefile) is True

    def test_no_clean_target(self, tmp_path: Path) -> None:
        makefile = tmp_path / "Makefile"
        makefile.write_text("build:\n\techo 'building'\n")
        evaluator = CleanupEvaluator(tmp_path)
        assert evaluator._makefile_has_clean(makefile) is False


class TestCleanupEvaluatorRunCleanup:
    """Tests for run_cleanup method."""

    def test_successful_script(self, tmp_path: Path) -> None:
        script = tmp_path / "cleanup.sh"
        script.write_text("#!/bin/bash\necho 'cleaned'\nexit 0\n")
        evaluator = CleanupEvaluator(tmp_path)
        success, output = evaluator.run_cleanup(script)
        assert success is True
        assert "cleaned" in output

    def test_failing_script(self, tmp_path: Path) -> None:
        script = tmp_path / "cleanup.sh"
        script.write_text("#!/bin/bash\nexit 1\n")
        evaluator = CleanupEvaluator(tmp_path)
        success, output = evaluator.run_cleanup(script)
        assert success is False

    def test_makefile_clean(self, tmp_path: Path) -> None:
        makefile = tmp_path / "Makefile"
        makefile.write_text(".PHONY: clean\nclean:\n\t@echo 'cleaned'\n")
        evaluator = CleanupEvaluator(tmp_path)
        success, output = evaluator.run_cleanup(makefile)
        assert success is True
        assert "cleaned" in output


class TestCleanupEvaluatorCaptureState:
    """Tests for state capture and verification."""

    def test_capture_initial_state(self, tmp_path: Path) -> None:
        (tmp_path / "file1.txt").write_text("content")
        evaluator = CleanupEvaluator(tmp_path)
        evaluator.capture_initial_state()
        assert evaluator.initial_state is not None
        assert "file1.txt" in evaluator.initial_state

    def test_verify_cleanup_no_artifacts(self, tmp_path: Path) -> None:
        evaluator = CleanupEvaluator(tmp_path)
        evaluator.capture_initial_state()
        # No new files, cleanup complete
        complete, artifacts = evaluator.verify_cleanup()
        assert complete is True
        assert artifacts == []

    def test_verify_cleanup_with_artifacts(self, tmp_path: Path) -> None:
        evaluator = CleanupEvaluator(tmp_path)
        evaluator.capture_initial_state()
        # Create build artifact
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        (build_dir / "output.o").write_text("binary")
        complete, artifacts = evaluator.verify_cleanup()
        assert complete is False
        assert len(artifacts) > 0

    def test_verify_cleanup_no_initial_state(self, tmp_path: Path) -> None:
        evaluator = CleanupEvaluator(tmp_path)
        # No initial state captured
        complete, artifacts = evaluator.verify_cleanup()
        assert complete is True
        assert artifacts == []


class TestCleanupEvaluatorIsBuildArtifact:
    """Tests for _is_build_artifact method."""

    def test_build_directory(self, tmp_path: Path) -> None:
        evaluator = CleanupEvaluator(tmp_path)
        assert evaluator._is_build_artifact("build/output.txt") is True
        assert evaluator._is_build_artifact("dist/package.tar.gz") is True

    def test_pycache(self, tmp_path: Path) -> None:
        evaluator = CleanupEvaluator(tmp_path)
        assert evaluator._is_build_artifact("__pycache__/module.cpython-311.pyc") is True

    def test_object_files(self, tmp_path: Path) -> None:
        evaluator = CleanupEvaluator(tmp_path)
        assert evaluator._is_build_artifact("main.o") is True
        assert evaluator._is_build_artifact("module.pyc") is True

    def test_not_artifact(self, tmp_path: Path) -> None:
        evaluator = CleanupEvaluator(tmp_path)
        assert evaluator._is_build_artifact("src/main.py") is False
        assert evaluator._is_build_artifact("README.md") is False


class TestCleanupEvaluatorEvaluate:
    """Tests for the full evaluate method."""

    def test_no_script(self, tmp_path: Path) -> None:
        evaluator = CleanupEvaluator(tmp_path)
        result = evaluator.evaluate()
        assert result.script_exists is False
        assert result.score == CleanupEvaluator.SCORE_NO_SCRIPT
        assert "No cleanup script" in result.notes

    def test_successful_full_cleanup(self, tmp_path: Path) -> None:
        script = tmp_path / "cleanup.sh"
        script.write_text("#!/bin/bash\necho 'cleaned'\n")
        evaluator = CleanupEvaluator(tmp_path)
        evaluator.capture_initial_state()
        result = evaluator.evaluate()
        assert result.script_exists is True
        assert result.execution_success is True
        assert result.cleanup_complete is True
        assert result.score == CleanupEvaluator.SCORE_FULL_CLEANUP

    def test_script_fails(self, tmp_path: Path) -> None:
        script = tmp_path / "cleanup.sh"
        script.write_text("#!/bin/bash\nexit 1\n")
        evaluator = CleanupEvaluator(tmp_path)
        result = evaluator.evaluate()
        assert result.script_exists is True
        assert result.execution_success is False
        assert result.score == CleanupEvaluator.SCORE_SCRIPT_FAILED

    def test_partial_cleanup(self, tmp_path: Path) -> None:
        # Create cleanup script that doesn't remove all artifacts
        script = tmp_path / "cleanup.sh"
        script.write_text("#!/bin/bash\necho 'partial cleanup'\n")

        evaluator = CleanupEvaluator(tmp_path)
        evaluator.capture_initial_state()

        # Add build artifact after initial state
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        (build_dir / "output.o").write_text("binary")

        result = evaluator.evaluate()
        assert result.script_exists is True
        assert result.execution_success is True
        assert result.cleanup_complete is False
        assert result.score == CleanupEvaluator.SCORE_PARTIAL_CLEANUP
        assert len(result.artifacts_remaining) > 0
