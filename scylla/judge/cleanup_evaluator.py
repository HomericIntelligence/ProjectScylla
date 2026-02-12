"""Cleanup script evaluation for test scoring.

This module evaluates agent-created cleanup scripts as part of the
quality scoring system. Tests require agents to create cleanup scripts
that return the environment to a clean state.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CleanupEvaluation:
    """Result of cleanup script evaluation.

    Attributes:
        script_exists: Whether a cleanup script was found.
        script_path: Path to the cleanup script if found.
        execution_success: Whether the script ran without errors.
        execution_output: Output from running the script.
        cleanup_complete: Whether the environment is fully clean.
        artifacts_remaining: List of artifacts that weren't cleaned up.
        score: Evaluation score (0.0 to 1.0).
        notes: Human-readable notes about the evaluation.

    """

    script_exists: bool
    script_path: Path | None
    execution_success: bool
    execution_output: str
    cleanup_complete: bool
    artifacts_remaining: list[str] = field(default_factory=list)
    score: float = 0.0
    notes: str = ""


class CleanupEvaluator:
    """Evaluator for agent-created cleanup scripts.

    Evaluates whether agents create proper cleanup scripts that return
    the workspace environment to a clean state.
    """

    # Known cleanup script locations in priority order
    CLEANUP_LOCATIONS = [
        "cleanup.sh",
        "scripts/cleanup.sh",
        "Makefile",
    ]

    # Common build artifact patterns that should be cleaned
    BUILD_PATTERNS = [
        "build/",
        "dist/",
        "__pycache__/",
        "*.o",
        "*.pyc",
        "node_modules/",
        "target/",
        ".cache/",
        "*.egg-info/",
        ".eggs/",
        "*.so",
        "*.dylib",
    ]

    # Scoring thresholds
    SCORE_FULL_CLEANUP = 1.0
    SCORE_PARTIAL_CLEANUP = 0.7
    SCORE_SCRIPT_FAILED = 0.4
    SCORE_NO_SCRIPT = 0.0

    # Execution timeout in seconds
    EXECUTION_TIMEOUT = 60

    def __init__(self, workspace: Path) -> None:
        """Initialize the evaluator.

        Args:
            workspace: Path to the workspace to evaluate.

        """
        self.workspace = workspace
        self.initial_state: set[str] | None = None

    def capture_initial_state(self) -> None:
        """Capture workspace state before agent runs.

        Call this before the agent modifies the workspace to establish
        a baseline for cleanup verification.
        """
        self.initial_state = self._get_workspace_state()

    def _get_workspace_state(self) -> set[str]:
        """Get set of files in workspace.

        Returns:
            Set of relative file paths in the workspace.

        """
        return set(
            str(p.relative_to(self.workspace)) for p in self.workspace.rglob("*") if p.is_file()
        )

    def find_cleanup_script(self) -> Path | None:
        """Find cleanup script in workspace.

        Returns:
            Path to cleanup script if found, None otherwise.

        """
        for location in self.CLEANUP_LOCATIONS:
            path = self.workspace / location
            if path.exists():
                if location == "Makefile":
                    if self._makefile_has_clean(path):
                        return path
                else:
                    return path
        return None

    def _makefile_has_clean(self, makefile: Path) -> bool:
        """Check if Makefile has a clean target.

        Args:
            makefile: Path to the Makefile.

        Returns:
            True if Makefile has a clean target.

        """
        try:
            content = makefile.read_text()
            return "clean:" in content or "clean :" in content
        except OSError:
            return False

    def run_cleanup(self, script_path: Path) -> tuple[bool, str]:
        """Execute cleanup script and capture result.

        Args:
            script_path: Path to the cleanup script.

        Returns:
            Tuple of (success, output).

        """
        try:
            if script_path.name == "Makefile":
                result = subprocess.run(
                    ["make", "clean"],
                    cwd=self.workspace,
                    capture_output=True,
                    text=True,
                    timeout=self.EXECUTION_TIMEOUT,
                )
            else:
                # Make script executable
                script_path.chmod(0o755)
                result = subprocess.run(
                    [str(script_path)],
                    cwd=self.workspace,
                    capture_output=True,
                    text=True,
                    timeout=self.EXECUTION_TIMEOUT,
                )

            success = result.returncode == 0
            output = result.stdout + result.stderr
            return success, output
        except subprocess.TimeoutExpired:
            return False, "Cleanup script timed out"
        except OSError as e:
            return False, str(e)

    def verify_cleanup(self) -> tuple[bool, list[str]]:
        """Verify workspace is clean after cleanup.

        Returns:
            Tuple of (cleanup_complete, artifacts_remaining).

        """
        if self.initial_state is None:
            # No initial state captured, assume clean
            return True, []

        current_state = self._get_workspace_state()

        # Files that appeared during agent run
        new_files = current_state - self.initial_state

        # Check for build artifacts that should have been cleaned
        artifacts_remaining = []
        for f in new_files:
            if self._is_build_artifact(f):
                artifacts_remaining.append(f)

        cleanup_complete = len(artifacts_remaining) == 0
        return cleanup_complete, artifacts_remaining

    def _is_build_artifact(self, filepath: str) -> bool:
        """Check if a file matches build artifact patterns.

        Args:
            filepath: Relative path to the file.

        Returns:
            True if the file is a build artifact.

        """
        for pattern in self.BUILD_PATTERNS:
            if pattern.endswith("/"):
                # Directory pattern
                if filepath.startswith(pattern.rstrip("/")):
                    return True
            elif pattern.startswith("*"):
                # Extension pattern
                if filepath.endswith(pattern.lstrip("*")):
                    return True
            else:
                # Exact match
                if filepath == pattern:
                    return True
        return False

    def evaluate(self) -> CleanupEvaluation:
        """Perform full cleanup script evaluation.

        Returns:
            CleanupEvaluation with score and details.

        """
        script_path = self.find_cleanup_script()

        if script_path is None:
            return CleanupEvaluation(
                script_exists=False,
                script_path=None,
                execution_success=False,
                execution_output="",
                cleanup_complete=False,
                artifacts_remaining=[],
                score=self.SCORE_NO_SCRIPT,
                notes="No cleanup script found",
            )

        execution_success, output = self.run_cleanup(script_path)

        if not execution_success:
            return CleanupEvaluation(
                script_exists=True,
                script_path=script_path,
                execution_success=False,
                execution_output=output,
                cleanup_complete=False,
                artifacts_remaining=[],
                score=self.SCORE_SCRIPT_FAILED,
                notes=f"Cleanup script failed: {output[:200]}",
            )

        cleanup_complete, artifacts = self.verify_cleanup()

        if cleanup_complete:
            score = self.SCORE_FULL_CLEANUP
            notes = "Cleanup successful, environment restored"
        else:
            score = self.SCORE_PARTIAL_CLEANUP
            notes = f"Partial cleanup, {len(artifacts)} artifacts remaining"

        return CleanupEvaluation(
            script_exists=True,
            script_path=script_path,
            execution_success=True,
            execution_output=output,
            cleanup_complete=cleanup_complete,
            artifacts_remaining=artifacts,
            score=score,
            notes=notes,
        )
