"""Experiment filesystem setup collaborator.

Encapsulates directory creation, grading material staging, config saving,
pipeline baseline capture, and PID file management from E2ERunner.
"""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from scylla.e2e.models import ExperimentConfig

if TYPE_CHECKING:
    from scylla.e2e.workspace_manager import WorkspaceManager

logger = logging.getLogger(__name__)


class ExperimentSetupManager:
    """Handles filesystem setup for fresh experiments.

    Encapsulates the cluster of methods from E2ERunner that set up the
    filesystem state for a fresh experiment: directory creation, grading
    material staging, config saving, baseline capture, and PID management.

    Args:
        config: Experiment configuration.
        results_base_dir: Base directory where experiment dirs are created.

    """

    def __init__(self, config: ExperimentConfig, results_base_dir: Path) -> None:
        """Initialize with experiment configuration.

        Args:
            config: Experiment configuration.
            results_base_dir: Base directory where experiment dirs are created.

        """
        self.config = config
        self.results_base_dir = results_base_dir

    def create_experiment_dir(self) -> Path:
        """Create the experiment results directory.

        Creates flattened structure with grading materials at root:
        - prompt.md, criteria.md, rubric.yaml, judge_prompt.md at root
        - Tiers directly under root (T0/, T1/, etc.)

        Returns:
            Path to the experiment directory.

        """
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        experiment_dir = self.results_base_dir / f"{timestamp}-{self.config.experiment_id}"
        experiment_dir.mkdir(parents=True, exist_ok=True)

        # Create config directory
        (experiment_dir / "config").mkdir(exist_ok=True)

        # Copy grading materials to root (uniform across all tiers)
        self.copy_grading_materials(experiment_dir)

        return experiment_dir

    def copy_grading_materials(self, experiment_dir: Path) -> None:
        """Copy grading materials from test config to experiment root.

        Copies prompt.md, criteria.md, rubric.yaml to experiment root since
        they're uniform across all tiers/subtests/runs. Also creates the
        judge_prompt.md template.

        Args:
            experiment_dir: Root experiment directory.

        """
        # Copy task prompt (immutable snapshot for reproducibility)
        prompt_path = experiment_dir / "prompt.md"
        if self.config.task_prompt_file.exists():
            shutil.copy(self.config.task_prompt_file, prompt_path)
            logger.debug(f"Copied task prompt to {prompt_path}")

        # Symlink criteria if exists (look for it relative to prompt file)
        prompt_dir = self.config.task_prompt_file.parent
        criteria_dest = experiment_dir / "criteria.md"
        criteria_file = prompt_dir / "expected" / "criteria.md"
        if criteria_file.exists():
            criteria_dest.symlink_to(criteria_file.resolve())
            logger.debug(f"Symlinked criteria to {criteria_dest}")
            criteria_path: Path | None = criteria_dest
        else:
            criteria_path = None

        # Symlink rubric if exists
        rubric_dest = experiment_dir / "rubric.yaml"
        rubric_file = prompt_dir / "expected" / "rubric.yaml"
        if rubric_file.exists():
            rubric_dest.symlink_to(rubric_file.resolve())
            logger.debug(f"Symlinked rubric to {rubric_dest}")
            rubric_path: Path | None = rubric_dest
        else:
            rubric_path = None

        # Create judge_prompt.md documentation (judge prompts generated dynamically per run)
        # The actual judge evaluation uses JUDGE_SYSTEM_PROMPT_FILE + build_task_prompt()
        judge_doc = [
            "# Judge Evaluation Context",
            "",
            "Judge prompts are generated dynamically per run using:",
            "- **System Prompt**: `config/judge/system_prompt.md` (via --system-prompt-file)",
            "- **Task Prompt**: Generated via `scylla.judge.prompts.build_task_prompt()`",
            "",
            "## Task Prompt References:",
            f"- Agent Task: `{experiment_dir / 'prompt.md'}`",
            f"- Success Criteria: `{criteria_path if criteria_path else 'N/A'}`",
            f"- Rubric: `{rubric_path if rubric_path else 'N/A'}`",
            "",
            "## Per-Run Context (Generated Dynamically):",
            "- Agent Output: `<run_dir>/output.txt`",
            "- Workspace: `<subtest_dir>/workspace/`",
            "- Patchfile: Git diff of workspace changes",
            "- Pipeline Results: Build/lint/test output",
        ]
        judge_prompt_path = experiment_dir / "judge_prompt.md"
        judge_prompt_path.write_text("\n".join(judge_doc))
        logger.debug(f"Created judge prompt documentation at {judge_prompt_path}")

    def save_config(self, experiment_dir: Path) -> None:
        """Save experiment configuration.

        Args:
            experiment_dir: Experiment directory where config is saved.

        """
        self.config.save(experiment_dir / "config" / "experiment.json")

    def capture_baseline(self, experiment_dir: Path, workspace_manager: WorkspaceManager) -> None:
        """Capture pipeline baseline once at experiment level from a clean repo state.

        Creates a temporary worktree from the base repo, runs the build pipeline on it,
        and saves the result to <experiment_dir>/pipeline_baseline.json.

        This is idempotent: if the file already exists (e.g. on resume) it is not
        re-captured.

        Args:
            experiment_dir: Experiment directory where baseline is saved.
            workspace_manager: WorkspaceManager for creating temporary worktrees.

        """
        baseline_path = experiment_dir / "pipeline_baseline.json"
        if baseline_path.exists():
            logger.info("Experiment-level pipeline baseline already captured — skipping")
            return

        from scylla.e2e.llm_judge import _run_build_pipeline
        from scylla.e2e.subtest_executor import _save_pipeline_baseline

        # Create a temporary worktree so the baseline runs on a clean repo state
        worktree_path = experiment_dir / "_baseline_worktree"
        branch_name = f"baseline_{self.config.experiment_id[:8]}"
        try:
            workspace_manager.create_worktree(worktree_path)
            logger.info(f"Capturing experiment-level pipeline baseline at {worktree_path}")
            result = _run_build_pipeline(
                workspace=worktree_path,
                language=self.config.language,
            )
            _save_pipeline_baseline(experiment_dir, result)
            baseline_status = "ALL PASSED ✓" if result.all_passed else "SOME FAILED ✗"
            logger.info(f"Experiment pipeline baseline: {baseline_status}")
        except (
            Exception
        ) as e:  # broad catch: pipeline baseline is non-critical; build/git/IO can all fail
            logger.warning(f"Failed to capture experiment-level baseline: {e}")
        finally:
            try:
                workspace_manager.cleanup_worktree(worktree_path, branch_name)
            except (
                Exception
            ) as cleanup_err:  # broad catch: cleanup must not raise; any error is non-fatal
                logger.debug(f"Baseline worktree cleanup warning: {cleanup_err}")

    def write_pid_file(self, experiment_dir: Path) -> None:
        """Write PID file for status monitoring.

        Location: {experiment_dir}/experiment.pid

        Args:
            experiment_dir: Experiment directory where PID file is written.

        """
        pid_file = experiment_dir / "experiment.pid"
        pid_file.write_text(str(os.getpid()))
        logger.debug(f"PID file written: {pid_file}")

    def cleanup_pid_file(self, experiment_dir: Path) -> None:
        """Remove PID file on completion.

        Args:
            experiment_dir: Experiment directory containing the PID file.

        """
        pid_file = experiment_dir / "experiment.pid"
        if pid_file.exists():
            pid_file.unlink()
            logger.debug(f"PID file removed: {pid_file}")
