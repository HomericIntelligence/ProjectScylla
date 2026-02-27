"""Stage functions and RunContext for the state machine-driven E2E runner.

Each stage function corresponds to a RunState transition, extracting logic
from the original monolithic _execute_single_run() and run_subtest() methods.

Stage functions mutate a shared RunContext dataclass, passing results from
earlier stages to later ones without complex argument threading.

build_actions_dict() assembles the {RunState -> Callable} map expected by
StateMachine.advance_to_completion().

16-stage pipeline (15 explicit stage functions + 1 implicit auto-transition):
  PENDING              -> stage_create_dir_structure()
  DIR_STRUCTURE_CREATED -> stage_create_worktree()
  WORKTREE_CREATED     -> stage_apply_symlinks()
  SYMLINKS_APPLIED     -> stage_commit_config()
  CONFIG_COMMITTED     -> stage_capture_baseline()
  BASELINE_CAPTURED    -> stage_write_prompt()
  PROMPT_WRITTEN       -> stage_generate_replay()
  REPLAY_GENERATED     -> stage_execute_agent()
  AGENT_COMPLETE       -> stage_capture_diff()
  DIFF_CAPTURED        -> stage_run_judge_pipeline()
  JUDGE_PIPELINE_RUN   -> stage_build_judge_prompt()
  JUDGE_PROMPT_BUILT   -> stage_execute_judge()
  JUDGE_COMPLETE       -> stage_finalize_run()
  RUN_FINALIZED        -> stage_write_report()
  REPORT_WRITTEN       -> (no-op: StateMachine auto-saves checkpoint after every transition,
                           so no explicit stage_save_checkpoint function is needed here)
  CHECKPOINTED         -> stage_cleanup_worktree()
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from scylla.e2e.models import (
    E2ERunResult,
    ExperimentConfig,
    RunState,
    SubTestConfig,
    TierBaseline,
    TierConfig,
    TierID,
)
from scylla.e2e.paths import get_agent_dir, get_judge_dir
from scylla.e2e.state_machine import TRANSITION_REGISTRY

if TYPE_CHECKING:
    from scylla.adapters.base import AdapterConfig, AdapterResult
    from scylla.adapters.claude_code import ClaudeCodeAdapter
    from scylla.e2e.checkpoint import E2ECheckpoint
    from scylla.e2e.llm_judge import BuildPipelineResult
    from scylla.e2e.models import JudgeResultSummary
    from scylla.e2e.parallel_executor import RateLimitCoordinator
    from scylla.e2e.scheduler import ParallelismScheduler
    from scylla.e2e.tier_manager import TierManager
    from scylla.e2e.workspace_manager import WorkspaceManager

logger = logging.getLogger(__name__)


@dataclass
class RunContext:
    """All state needed by stage functions for a single run.

    Immutable config fields are set at construction time. Mutable fields
    (agent_result, judgment, etc.) are populated by stage functions and
    consumed by later stages.

    Attributes:
        config: Experiment configuration
        tier_id: Tier identifier
        tier_config: Tier configuration
        subtest: SubTestConfig for this run
        baseline: Previous tier's best baseline (if any)
        run_number: 1-based run number

        run_dir: Directory for this run's outputs (e.g., T0/00/run_01/)
        workspace: Workspace directory for this run (run_dir/workspace/)
        experiment_dir: Root experiment directory (for T5 inheritance, prompts)

        tier_manager: Tier configuration manager (reconstructed in child process)
        workspace_manager: Workspace manager (reconstructed in child process)
        adapter: Claude Code adapter for building commands

        pipeline_baseline: Build pipeline baseline captured before first run
        task_prompt: Task prompt text (loaded once by SubTestExecutor)

        agent_result: Result from agent execution (set by stage_execute_agent)
        agent_duration: Agent execution duration in seconds
        agent_ran: True if agent was actually executed (False if resumed)
        diff_result: Workspace diff captured after agent (set by stage_capture_diff)
        judge_pipeline_result: Build pipeline result on agent workspace (stage_run_judge_pipeline)
        judge_prompt: Assembled judge prompt text (set by stage_build_judge_prompt)
        judgment: Judge consensus dict (set by stage_execute_judge)
        judges: Individual judge result summaries
        judge_duration: Judge execution duration in seconds
        run_result: Final E2ERunResult (set by stage_finalize_run)

        coordinator: Rate limit coordinator for cross-process pause/resume
        checkpoint: Experiment checkpoint (mutated by StateMachine)
        checkpoint_path: Path to checkpoint file

    """

    # Immutable config
    config: ExperimentConfig
    tier_id: TierID
    tier_config: TierConfig
    subtest: SubTestConfig
    baseline: TierBaseline | None
    run_number: int

    # Paths
    run_dir: Path
    workspace: Path
    experiment_dir: Path | None

    # Managers (reconstructed in child process, not serialized)
    tier_manager: TierManager
    workspace_manager: WorkspaceManager
    adapter: ClaudeCodeAdapter

    # Shared per-subtest state
    pipeline_baseline: BuildPipelineResult | None = None
    task_prompt: str = ""

    # Per-run mutable state (populated by stages, consumed by later stages)
    agent_result: AdapterResult | None = None
    agent_duration: float = 0.0
    agent_ran: bool = False
    diff_result: dict[str, Any] | None = None  # {workspace_state, patchfile, deleted_files}
    judge_pipeline_result: BuildPipelineResult | None = None
    judge_prompt: str = ""
    judgment: dict[str, Any] | None = None
    judges: list[JudgeResultSummary] = field(default_factory=list)
    judge_duration: float = 0.0
    run_result: E2ERunResult | None = None

    # Adapter config passed between stage_generate_replay and stage_execute_agent
    adapter_config: AdapterConfig | None = None

    # Cross-process coordination
    coordinator: RateLimitCoordinator | None = None
    checkpoint: E2ECheckpoint | None = None
    checkpoint_path: Path | None = None


# ---------------------------------------------------------------------------
# Stage functions
# ---------------------------------------------------------------------------


def stage_create_dir_structure(ctx: RunContext) -> None:
    """PENDING -> DIR_STRUCTURE_CREATED: Create run directory structure.

    Creates run_dir, agent/, and judge/ subdirectories. Does NOT create
    the git worktree (that is the next stage).

    Args:
        ctx: Run context

    """
    ctx.run_dir.mkdir(parents=True, exist_ok=True)
    ctx.workspace.mkdir(parents=True, exist_ok=True)

    agent_dir = get_agent_dir(ctx.run_dir)
    agent_dir.mkdir(parents=True, exist_ok=True)
    agent_dir.chmod(0o777)

    judge_dir = get_judge_dir(ctx.run_dir)
    judge_dir.mkdir(parents=True, exist_ok=True)
    judge_dir.chmod(0o777)


def stage_create_worktree(ctx: RunContext) -> None:
    """DIR_STRUCTURE_CREATED -> WORKTREE_CREATED: Create git worktree for this run.

    Sets up the git worktree in ctx.workspace. Preserves existing workspace
    if run already passed (checkpoint resume).

    Args:
        ctx: Run context

    """
    from scylla.e2e.command_logger import CommandLogger
    from scylla.e2e.workspace_setup import _setup_workspace

    # Check if run already passed and workspace exists - preserve it
    run_status = None
    if ctx.checkpoint:
        run_status = ctx.checkpoint.get_run_status(
            ctx.tier_id.value, ctx.subtest.id, ctx.run_number
        )

    if run_status == "passed" and ctx.workspace.exists():
        logger.info(
            f"Run {ctx.run_number} already passed (checkpoint), preserving existing workspace"
        )
        return

    _setup_workspace(
        workspace=ctx.workspace,
        command_logger=CommandLogger(log_dir=ctx.run_dir),
        tier_id=ctx.tier_id,
        subtest_id=ctx.subtest.id,
        run_number=ctx.run_number,
        base_repo=ctx.workspace_manager.base_repo,
        task_commit=ctx.config.task_commit,
        experiment_id=ctx.config.experiment_id,
    )


def stage_apply_symlinks(ctx: RunContext) -> None:
    """WORKTREE_CREATED -> SYMLINKS_APPLIED: Apply tier resource symlinks to workspace.

    Calls tier_manager.prepare_workspace() to symlink tier resources
    (CLAUDE.md blocks, agents, skills) into the workspace. For T5 subtests
    with inherit_best_from, builds a merged baseline from lower tiers.

    Args:
        ctx: Run context

    """
    # Build merged resources for T5 subtests with inherit_best_from
    merged_resources = None
    if ctx.tier_id == TierID.T5 and ctx.subtest.inherit_best_from and ctx.experiment_dir:
        try:
            merged_resources = ctx.tier_manager.build_merged_baseline(
                ctx.subtest.inherit_best_from,
                ctx.experiment_dir,
            )
        except ValueError as e:
            logger.error(f"Failed to build merged baseline for T5/{ctx.subtest.id}: {e}")
            raise

    thinking_enabled = ctx.config.thinking_mode is not None and ctx.config.thinking_mode != "None"
    ctx.tier_manager.prepare_workspace(
        workspace=ctx.workspace,
        tier_id=ctx.tier_id,
        subtest_id=ctx.subtest.id,
        baseline=ctx.baseline,
        merged_resources=merged_resources,
        thinking_enabled=thinking_enabled,
    )


def stage_commit_config(ctx: RunContext) -> None:
    """SYMLINKS_APPLIED -> CONFIG_COMMITTED: Commit test config to workspace.

    Runs git add CLAUDE.md .claude/ and git commit to initialize
    the test configuration in the workspace's git history.

    Args:
        ctx: Run context

    """
    from scylla.e2e.workspace_setup import _commit_test_config

    _commit_test_config(ctx.workspace)


def stage_capture_baseline(ctx: RunContext) -> None:
    """CONFIG_COMMITTED -> BASELINE_CAPTURED: Capture pipeline baseline.

    Loads from checkpoint if already captured, otherwise runs build pipeline.
    Only meaningful for the first run; subsequent runs reuse ctx.pipeline_baseline
    which is shared across runs in SubTestExecutor.

    Args:
        ctx: Run context (mutates ctx.pipeline_baseline)

    """
    from scylla.e2e.subtest_executor import _load_pipeline_baseline, _save_pipeline_baseline

    if ctx.pipeline_baseline is not None:
        # Already captured by a previous run in this subtest — skip
        return

    # results_dir is run_dir.parent (subtest dir)
    results_dir = ctx.run_dir.parent

    # Try to load from checkpoint first
    ctx.pipeline_baseline = _load_pipeline_baseline(results_dir)

    if ctx.pipeline_baseline is None:
        from scylla.e2e.llm_judge import _run_build_pipeline

        logger.info("Capturing pipeline baseline before agent runs")
        ctx.pipeline_baseline = _run_build_pipeline(
            workspace=ctx.workspace,
            language=ctx.config.language,
        )
        _save_pipeline_baseline(results_dir, ctx.pipeline_baseline)

        baseline_status = "ALL PASSED ✓" if ctx.pipeline_baseline.all_passed else "SOME FAILED ✗"
        logger.info(f"Pipeline baseline: {baseline_status}")


def stage_write_prompt(ctx: RunContext) -> None:
    """BASELINE_CAPTURED -> PROMPT_WRITTEN: Write task prompt to disk.

    Writes task_prompt.md (as symlink to experiment prompt or direct file),
    injects thinking keyword if configured.

    Args:
        ctx: Run context

    """
    # Write task_prompt.md
    prompt_file = ctx.run_dir / "task_prompt.md"
    if prompt_file.exists() or prompt_file.is_symlink():
        prompt_file.unlink()

    if ctx.experiment_dir is not None:
        experiment_prompt = ctx.experiment_dir / "prompt.md"
        if experiment_prompt.exists():
            prompt_file.symlink_to(experiment_prompt.resolve())
        else:
            prompt_file.write_text(ctx.task_prompt)
    else:
        prompt_file.write_text(ctx.task_prompt)


def stage_generate_replay(ctx: RunContext) -> None:
    """PROMPT_WRITTEN -> REPLAY_GENERATED: Build adapter command and generate replay.sh.

    If a valid agent result already exists (checkpoint resume), loads it into
    ctx.agent_result so stage_execute_agent becomes a no-op.

    Args:
        ctx: Run context (mutates ctx.agent_result if resuming)

    """
    from scylla.adapters.base import AdapterConfig
    from scylla.e2e.agent_runner import _has_valid_agent_result, _load_agent_result
    from scylla.e2e.command_logger import CommandLogger

    agent_dir = get_agent_dir(ctx.run_dir)

    # Check for valid agent result (resume case)
    if _has_valid_agent_result(ctx.run_dir):
        from scylla.e2e.paths import get_agent_result_file

        agent_result_file = get_agent_result_file(ctx.run_dir)
        logger.info(f"[SKIP] Agent already completed: {agent_result_file}")
        ctx.agent_result = _load_agent_result(agent_dir)
        # Load persisted timing
        agent_timing_file = agent_dir / "timing.json"
        if agent_timing_file.exists():
            timing_data = json.loads(agent_timing_file.read_text())
            ctx.agent_duration = timing_data.get("agent_duration_seconds", 0.0)
        ctx.agent_ran = False
        return

    # Inject thinking keyword if configured
    final_prompt = ctx.task_prompt
    if ctx.config.thinking_mode and ctx.config.thinking_mode != "None":
        thinking_keywords = {
            "Low": "think",
            "High": "think hard",
            "UltraThink": "ultrathink",
        }
        keyword = thinking_keywords.get(ctx.config.thinking_mode, "")
        if keyword:
            final_prompt = f"{keyword}\n\n{ctx.task_prompt}"

    agent_prompt_file = agent_dir / "prompt.md"
    agent_prompt_file.write_text(final_prompt)

    # Build extra args for adapter
    extra_args: list[str] = []
    if ctx.config.max_turns is not None:
        extra_args.extend(["--max-turns", str(ctx.config.max_turns)])

    # Extract agent name for T3/T4 delegation tiers
    agent_name = None
    if ctx.subtest.resources and "agents" in ctx.subtest.resources:
        agents_spec = ctx.subtest.resources["agents"]
        agent_names_list = agents_spec.get("names", [])
        if agent_names_list:
            agent_name = agent_names_list[0].replace(".md", "")
            logger.info(f"Using agent: {agent_name}")

    prompt_file = ctx.run_dir / "task_prompt.md"
    adapter_config = AdapterConfig(
        model=ctx.config.models[0],
        prompt_file=prompt_file,
        workspace=ctx.workspace,
        output_dir=agent_dir,
        timeout=ctx.config.timeout_seconds,
        extra_args=extra_args,
    )

    cmd = ctx.adapter._build_command(
        adapter_config,
        str(agent_prompt_file.resolve()),
        None,
        ctx.subtest.system_prompt_mode,
        agent_name,
    )

    command_logger = CommandLogger(log_dir=agent_dir)
    command_logger.log_command(
        cmd=cmd,
        stdout="",
        stderr="",
        exit_code=0,
        duration=0.0,
        cwd=str(ctx.workspace.resolve()),
    )
    command_logger.save()
    command_logger.save_replay_script()
    # Store adapter_config for use in stage_execute_agent
    ctx.adapter_config = adapter_config


def stage_execute_agent(ctx: RunContext) -> None:
    """REPLAY_GENERATED -> AGENT_COMPLETE: Execute agent and save outputs.

    If ctx.agent_result is already set (resume), this is a no-op.
    Otherwise, runs via replay.sh and saves all agent artifacts.

    Args:
        ctx: Run context (mutates ctx.agent_result, ctx.agent_duration, ctx.agent_ran)

    """
    if ctx.agent_result is not None:
        # Resumed — agent result already loaded by stage_generate_replay
        logger.debug(f"Skipping agent execution for run {ctx.run_number} (resumed)")
        return

    import subprocess

    from scylla.adapters.base import AdapterResult
    from scylla.e2e.agent_runner import (
        _create_agent_model_md,
        _save_agent_result,
    )
    from scylla.e2e.command_logger import CommandLogger

    agent_dir = get_agent_dir(ctx.run_dir)
    adapter_config = ctx.adapter_config
    if adapter_config is None:
        raise RuntimeError("adapter_config must be set before writing replay script")
    replay_script = agent_dir / "replay.sh"

    logger.info(f"[AGENT] Running agent with model[{ctx.config.models[0]}]")

    agent_start = datetime.now(timezone.utc)
    try:
        result = subprocess.run(
            ["bash", str(replay_script.resolve())],
            capture_output=True,
            text=True,
            timeout=adapter_config.timeout,
            cwd=ctx.workspace.resolve(),
        )
        stdout = result.stdout
        stderr = result.stderr

        token_stats = ctx.adapter._parse_token_stats(stdout, stderr)
        api_calls = ctx.adapter._parse_api_calls(stdout, stderr)
        cost = ctx.adapter._parse_cost(stdout)

        if cost == 0.0 and (token_stats.input_tokens > 0 or token_stats.output_tokens > 0):
            total_input = token_stats.input_tokens + token_stats.cache_read_tokens
            cost = ctx.adapter.calculate_cost(
                total_input, token_stats.output_tokens, adapter_config.model
            )

        ctx.adapter.write_logs(agent_dir, stdout, stderr)

        agent_result = AdapterResult(
            exit_code=result.returncode,
            stdout=stdout,
            stderr=stderr,
            token_stats=token_stats,
            cost_usd=cost,
            api_calls=api_calls,
        )
    except Exception as e:
        from scylla.adapters.base import AdapterResult, AdapterTokenStats

        agent_result = AdapterResult(
            exit_code=-1,
            stdout="",
            stderr=str(e),
            token_stats=AdapterTokenStats(),
            cost_usd=0.0,
            api_calls=0,
        )

    ctx.agent_duration = (datetime.now(timezone.utc) - agent_start).total_seconds()
    ctx.agent_result = agent_result
    ctx.agent_ran = True

    # Update command logger with actual results
    command_log_path = agent_dir / "command_log.json"
    if command_log_path.exists():
        command_logger = CommandLogger.load(agent_dir)
    else:
        command_logger = CommandLogger(log_dir=agent_dir)
    if command_logger.commands:
        command_logger.update_last_command(
            stdout=agent_result.stdout,
            stderr=agent_result.stderr,
            exit_code=agent_result.exit_code,
            duration=ctx.agent_duration,
        )
        command_logger.save()

    # Persist timing for resume capability
    agent_timing_file = agent_dir / "timing.json"
    with open(agent_timing_file, "w") as f:
        json.dump(
            {
                "agent_duration_seconds": ctx.agent_duration,
                "measured_at": datetime.now(timezone.utc).isoformat(),
            },
            f,
            indent=2,
        )

    # Save output and result
    (agent_dir / "output.txt").write_text(agent_result.stdout or "")
    _save_agent_result(agent_dir, agent_result)
    _create_agent_model_md(agent_dir, ctx.config.models[0])

    logger.info(f"[AGENT] Complete ({ctx.agent_duration:.1f}s)")


def stage_capture_diff(ctx: RunContext) -> None:
    """AGENT_COMPLETE -> DIFF_CAPTURED: Capture workspace diff and state.

    Runs git diff/status to capture changes made by the agent.
    Saves diff data to ctx.diff_result for use by later stages.

    If judge result can be reused (resume case), also loads existing
    judgment to make subsequent judge stages no-ops.

    Args:
        ctx: Run context (mutates ctx.diff_result, optionally ctx.judgment)

    """
    from scylla.e2e.judge_runner import _has_valid_judge_result, _load_judge_result
    from scylla.e2e.llm_judge import _get_deleted_files, _get_patchfile, _get_workspace_state

    judge_dir = get_judge_dir(ctx.run_dir)

    # Only reuse judge result if agent was also reused (not re-run)
    if not ctx.agent_ran and _has_valid_judge_result(ctx.run_dir):
        from scylla.e2e.paths import get_judge_result_file

        judge_result_file = get_judge_result_file(ctx.run_dir)
        logger.info(f"[SKIP] Judge already completed: {judge_result_file}")
        ctx.judgment = _load_judge_result(judge_dir)
        # Load persisted timing
        judge_timing_file = judge_dir / "timing.json"
        if judge_timing_file.exists():
            timing_data = json.loads(judge_timing_file.read_text())
            ctx.judge_duration = timing_data.get("judge_duration_seconds", 0.0)
        # diff_result not needed since judge is already done
        ctx.diff_result = {}
        return

    # Capture workspace diff
    workspace_state = _get_workspace_state(ctx.workspace)
    patchfile = _get_patchfile(ctx.workspace)
    deleted_files = _get_deleted_files(ctx.workspace)

    ctx.diff_result = {
        "workspace_state": workspace_state,
        "patchfile": patchfile,
        "deleted_files": deleted_files,
    }


def stage_run_judge_pipeline(ctx: RunContext) -> None:
    """DIFF_CAPTURED -> JUDGE_PIPELINE_RUN: Run build pipeline on agent workspace.

    Runs the language-appropriate build pipeline (compileall, ruff, pytest,
    pre-commit for Python; Mojo pipeline for Mojo) on the agent-modified workspace.
    Saves pipeline results to ctx.judge_pipeline_result.

    If judgment already loaded (resume), this is a no-op.

    Args:
        ctx: Run context (mutates ctx.judge_pipeline_result)

    """
    if ctx.judgment is not None:
        # Resumed — judge result already loaded in stage_capture_diff
        return

    from scylla.e2e.llm_judge import _run_build_pipeline, _save_pipeline_commands

    logger.info(f"Running {ctx.config.language} build pipeline for judge evaluation")
    ctx.judge_pipeline_result = _run_build_pipeline(
        workspace=ctx.workspace,
        language=ctx.config.language,
    )

    # Save pipeline commands for debugging
    _save_pipeline_commands(ctx.run_dir, ctx.workspace, language=ctx.config.language)

    # Save pipeline outputs
    from scylla.e2e.llm_judge import _save_pipeline_outputs

    _save_pipeline_outputs(ctx.run_dir, ctx.judge_pipeline_result, language=ctx.config.language)

    status = "ALL PASSED ✓" if ctx.judge_pipeline_result.all_passed else "SOME FAILED ✗"
    logger.info(f"Judge pipeline: {status}")


def stage_build_judge_prompt(ctx: RunContext) -> None:
    """JUDGE_PIPELINE_RUN -> JUDGE_PROMPT_BUILT: Assemble full judge prompt.

    Combines task prompt, agent output, workspace state, diff, pipeline results,
    rubric, and criteria into the complete judge evaluation prompt.
    Saves prompt to judge/prompt.md for debugging and resume.

    If judgment already loaded (resume), this is a no-op.

    Args:
        ctx: Run context (mutates ctx.judge_prompt)

    """
    if ctx.judgment is not None:
        # Resumed — judge result already loaded in stage_capture_diff
        return

    from scylla.judge.prompts import build_task_prompt

    # Find rubric path (symlinked at experiment root)
    experiment_dir_calc = ctx.run_dir.parent.parent.parent
    rubric_path = experiment_dir_calc / "rubric.yaml"

    rubric_content = None
    if rubric_path.exists():
        try:
            rubric_content = rubric_path.read_text()
        except Exception as e:
            logger.warning(f"Failed to load rubric from {rubric_path}: {e}")

    # Format pipeline result strings
    pipeline_result_str = None
    if ctx.judge_pipeline_result:
        overall_status = "ALL PASSED ✓" if ctx.judge_pipeline_result.all_passed else "SOME FAILED ✗"
        pipeline_result_str = (
            f"**Overall Status**: {overall_status}\n\n"
            f"{ctx.judge_pipeline_result.to_context_string()}"
        )

    baseline_pipeline_str = None
    if ctx.pipeline_baseline:
        baseline_status = "ALL PASSED ✓" if ctx.pipeline_baseline.all_passed else "SOME FAILED ✗"
        baseline_pipeline_str = (
            f"**Overall Status**: {baseline_status}\n\n{ctx.pipeline_baseline.to_context_string()}"
        )

    diff_data = ctx.diff_result or {}
    ctx.judge_prompt = build_task_prompt(
        task_prompt=ctx.task_prompt,
        agent_output=ctx.agent_result.stdout if ctx.agent_result else "",
        workspace_state=diff_data.get("workspace_state", ""),
        patchfile=diff_data.get("patchfile"),
        deleted_files=diff_data.get("deleted_files"),
        reference_patch=None,
        pipeline_result_str=pipeline_result_str,
        rubric_content=rubric_content,
        baseline_pipeline_str=baseline_pipeline_str,
    )

    # Save assembled judge prompt to disk for debugging and resume
    judge_prompt_path = ctx.run_dir / "judge_prompt.md"
    if not judge_prompt_path.exists():
        judge_prompt_path.write_text(ctx.judge_prompt)


def stage_execute_judge(ctx: RunContext) -> None:
    """JUDGE_PROMPT_BUILT -> JUDGE_COMPLETE: Execute judge(s) and save results.

    If ctx.judgment is already set (resume), this is a no-op.
    Otherwise, calls Claude CLI judge(s) with pre-built prompt and
    computes consensus.

    Args:
        ctx: Run context (mutates ctx.judgment, ctx.judges, ctx.judge_duration)

    """
    if ctx.judgment is not None:
        # Resumed — judge result already loaded by stage_capture_diff
        logger.debug(f"Skipping judge execution for run {ctx.run_number} (resumed)")
        return

    from scylla.e2e.judge_runner import _compute_judge_consensus, _save_judge_result
    from scylla.e2e.llm_judge import (
        JudgeResult,
        _call_claude_judge,
        _parse_judge_response,
        _save_judge_logs,
    )
    from scylla.e2e.models import JudgeResultSummary
    from scylla.e2e.rate_limit import RateLimitError

    judge_dir = get_judge_dir(ctx.run_dir)
    if not ctx.config.judge_models:
        raise ValueError("judge_models is required")

    judges = []
    judge_start = datetime.now(timezone.utc)

    for judge_num, model in enumerate(ctx.config.judge_models, start=1):
        logger.info(
            f"[JUDGE] Running judge {judge_num}/{len(ctx.config.judge_models)} with model[{model}]"
        )

        try:
            actual_judge_dir = judge_dir / f"judge_{judge_num:02d}"
            actual_judge_dir.mkdir(parents=True, exist_ok=True)

            stdout, stderr, result = _call_claude_judge(ctx.judge_prompt, model, ctx.workspace)
            judge_result = _parse_judge_response(result)

            _save_judge_logs(
                actual_judge_dir,
                ctx.judge_prompt,
                result,
                judge_result,
                model,
                ctx.workspace,
                raw_stdout=stdout,
                raw_stderr=stderr,
                language=ctx.config.language,
            )

            judge_duration_single = (datetime.now(timezone.utc) - judge_start).total_seconds()
            timing_file = actual_judge_dir / "timing.json"
            with open(timing_file, "w") as f:
                json.dump(
                    {
                        "judge_duration_seconds": judge_duration_single,
                        "measured_at": datetime.now(timezone.utc).isoformat(),
                    },
                    f,
                    indent=2,
                )

            judge_summary = JudgeResultSummary(
                model=model,
                score=judge_result.score,
                passed=judge_result.passed,
                grade=judge_result.grade,
                reasoning=judge_result.reasoning,
                judge_number=judge_num,
                is_valid=judge_result.is_valid,
                criteria_scores=judge_result.criteria_scores,
            )
            judges.append(judge_summary)

        except RateLimitError:
            raise

        except Exception as e:
            logger.error(
                f"Judge {judge_num} failed with model {model}: {e}",
                exc_info=True,
            )

            judge_specific_dir = judge_dir / f"judge_{judge_num:02d}"
            judge_specific_dir.mkdir(parents=True, exist_ok=True)

            timing_file = judge_specific_dir / "timing.json"
            with open(timing_file, "w") as f:
                json.dump(
                    {
                        "judge_duration_seconds": 0.0,
                        "measured_at": datetime.now(timezone.utc).isoformat(),
                        "failed": True,
                        "error": str(e),
                    },
                    f,
                    indent=2,
                )
            (judge_specific_dir / "error.log").write_text(f"Judge failed: {e}\n")

            failed_summary = JudgeResultSummary(
                model=model,
                score=0.0,
                passed=False,
                grade="F",
                reasoning=f"Judge failed: {e}",
                judge_number=judge_num,
                is_valid=False,
                criteria_scores={},
            )
            judges.append(failed_summary)

    ctx.judge_duration = (datetime.now(timezone.utc) - judge_start).total_seconds()

    # Compute consensus
    consensus_score, consensus_passed, consensus_grade = _compute_judge_consensus(judges)

    judgment: dict[str, Any]
    if consensus_score is None:
        logger.warning("All judges failed to produce valid results; returning zero-score consensus")
        judgment = {
            "score": 0.0,
            "passed": False,
            "grade": "F",
            "reasoning": "All judges failed to produce valid results",
            "is_valid": False,
            "criteria_scores": {},
        }
    else:
        closest_judge = min(
            (j for j in judges if j.score is not None),
            key=lambda j: abs((j.score if j.score is not None else 0.0) - consensus_score),
        )
        consensus_is_valid = all(j.is_valid for j in judges)
        judgment = {
            "score": consensus_score,
            "passed": consensus_passed,
            "grade": consensus_grade,
            "reasoning": closest_judge.reasoning,
            "is_valid": consensus_is_valid,
            "criteria_scores": closest_judge.criteria_scores or {},
        }

    # Persist timing for resume capability
    judge_timing_file = judge_dir / "timing.json"
    with open(judge_timing_file, "w") as f:
        json.dump(
            {
                "judge_duration_seconds": ctx.judge_duration,
                "measured_at": datetime.now(timezone.utc).isoformat(),
            },
            f,
            indent=2,
        )

    # Save judge result for future resume
    judge_result_obj = JudgeResult(
        score=judgment["score"],
        passed=judgment["passed"],
        grade=judgment["grade"],
        reasoning=judgment["reasoning"],
        is_valid=judgment.get("is_valid", True),
    )
    _save_judge_result(judge_dir, judge_result_obj)

    ctx.judgment = judgment
    ctx.judges = judges

    logger.info(f"[JUDGE] Complete ({ctx.judge_duration:.1f}s)")


def stage_finalize_run(ctx: RunContext) -> None:
    """JUDGE_COMPLETE -> RUN_FINALIZED: Build RunResult and save run_result.json.

    Checks for rate limit, builds E2ERunResult, saves run_result.json,
    and calls mark_run_completed() for v2.0 backward compat.
    Report generation is handled by the next stage (stage_write_report).

    Args:
        ctx: Run context (mutates ctx.run_result)

    """
    from scylla.e2e.rate_limit import RateLimitError, detect_rate_limit

    if ctx.agent_result is None:
        raise RuntimeError("agent_result must be set before finalize_run")
    if ctx.judgment is None:
        raise RuntimeError("judgment must be set before finalize_run")

    agent_dir = get_agent_dir(ctx.run_dir)

    # Check for rate limit in run artifacts BEFORE considering complete
    stderr_content = ctx.agent_result.stderr or ""
    stdout_content = ctx.agent_result.stdout or ""
    rate_limit_info = detect_rate_limit(stdout_content, stderr_content, source="agent")

    if rate_limit_info:
        raise RateLimitError(rate_limit_info)

    # Also check for "invalid" judge output with exit_code=-1
    if ctx.agent_result.exit_code == -1 and ctx.judgment.get("reasoning", "").startswith(
        "Invalid:"
    ):
        rate_limit_info = detect_rate_limit(stdout_content, stderr_content, source="agent")
        if rate_limit_info:
            raise RateLimitError(rate_limit_info)

    # Convert adapter token stats to E2E token stats
    token_stats = ctx.agent_result.token_stats.to_token_stats()

    # Convert baseline to summary dict if available
    baseline_summary = None
    if ctx.pipeline_baseline:
        baseline_summary = {
            "all_passed": ctx.pipeline_baseline.all_passed,
            "build_passed": ctx.pipeline_baseline.build_passed,
            "format_passed": ctx.pipeline_baseline.format_passed,
            "test_passed": ctx.pipeline_baseline.test_passed,
        }

    run_result = E2ERunResult(
        run_number=ctx.run_number,
        exit_code=ctx.agent_result.exit_code,
        token_stats=token_stats,
        cost_usd=ctx.agent_result.cost_usd,
        duration_seconds=ctx.agent_duration + ctx.judge_duration,
        agent_duration_seconds=ctx.agent_duration,
        judge_duration_seconds=ctx.judge_duration,
        judge_score=ctx.judgment["score"],
        judge_passed=ctx.judgment["passed"],
        judge_grade=ctx.judgment["grade"],
        judge_reasoning=ctx.judgment["reasoning"],
        judges=ctx.judges,
        workspace_path=ctx.workspace,
        logs_path=agent_dir,
        command_log_path=agent_dir / "command_log.json",
        criteria_scores=ctx.judgment.get("criteria_scores") or {},
        baseline_pipeline_summary=baseline_summary,
    )

    # Save full E2ERunResult for checkpoint resume
    with open(ctx.run_dir / "run_result.json", "w") as f:
        json.dump(run_result.to_dict(), f, indent=2)

    # Pre-seed completed_runs with the correct pass/fail status so that the
    # backward-compat sync in set_run_state("run_finalized") picks it up.
    if ctx.checkpoint:
        status = "passed" if run_result.judge_passed else "failed"
        ctx.checkpoint.mark_run_completed(
            ctx.tier_id.value, ctx.subtest.id, ctx.run_number, status=status
        )
        # Do NOT save here — StateMachine.advance() saves after set_run_state.

    ctx.run_result = run_result


def stage_write_report(ctx: RunContext) -> None:
    """RUN_FINALIZED -> REPORT_WRITTEN: Generate per-run reports.

    Generates report.md and report.json for this run.

    Args:
        ctx: Run context (ctx.run_result must be set)

    """
    from scylla.e2e.run_report import save_run_report, save_run_report_json

    if ctx.run_result is None:
        raise RuntimeError("run_result must be set before write_report")
    if ctx.agent_result is None:
        raise RuntimeError("agent_result must be set before write_report")
    if ctx.judgment is None:
        raise RuntimeError("judgment must be set before write_report")

    token_stats = ctx.run_result.token_stats

    save_run_report(
        output_path=ctx.run_dir / "report.md",
        tier_id=ctx.tier_id.value,
        subtest_id=ctx.subtest.id,
        run_number=ctx.run_number,
        score=ctx.judgment["score"],
        grade=ctx.judgment["grade"],
        passed=ctx.judgment["passed"],
        reasoning=ctx.judgment["reasoning"],
        judges=ctx.judges,
        cost_usd=ctx.agent_result.cost_usd,
        duration_seconds=ctx.agent_duration + ctx.judge_duration,
        tokens_input=ctx.run_result.tokens_input,
        tokens_output=ctx.run_result.tokens_output,
        exit_code=ctx.agent_result.exit_code,
        task_prompt=ctx.task_prompt,
        workspace_path=ctx.workspace,
        criteria_scores=ctx.judgment.get("criteria_scores"),
        agent_output=ctx.agent_result.stdout[:2000] if ctx.agent_result.stdout else None,
        token_stats=token_stats.to_dict(),
        agent_duration_seconds=ctx.agent_duration,
        judge_duration_seconds=ctx.judge_duration,
    )

    save_run_report_json(
        run_dir=ctx.run_dir,
        run_number=ctx.run_number,
        score=ctx.judgment["score"],
        grade=ctx.judgment["grade"],
        passed=ctx.judgment["passed"],
        cost_usd=ctx.agent_result.cost_usd,
        duration_seconds=ctx.agent_duration + ctx.judge_duration,
    )


def stage_cleanup_worktree(ctx: RunContext) -> None:
    """CHECKPOINTED -> WORKTREE_CLEANED: Remove git worktree for passed runs.

    For passed runs, removes the git worktree to free disk space.
    For failed runs, preserves the workspace for debugging.

    Args:
        ctx: Run context

    """
    # Only clean up if the run passed (preserve failed workspaces for debugging)
    run_passed = ctx.run_result is not None and ctx.run_result.judge_passed
    if not run_passed and ctx.checkpoint:
        run_status = ctx.checkpoint.get_run_status(
            ctx.tier_id.value, ctx.subtest.id, ctx.run_number
        )
        run_passed = run_status == "passed"

    if run_passed and ctx.workspace.exists():
        try:
            ctx.workspace_manager.cleanup_worktree(ctx.workspace)
            logger.info(
                f"Cleaned up worktree for passed run {ctx.tier_id.value}/{ctx.subtest.id}"
                f"/run_{ctx.run_number:02d}"
            )
        except Exception as e:
            # Cleanup failure is non-fatal - log and continue
            logger.warning(
                f"Failed to clean up worktree for "
                f"{ctx.tier_id.value}/{ctx.subtest.id}/run_{ctx.run_number:02d}: {e}"
            )
    else:
        logger.debug(
            f"Preserving workspace for failed/unresolved run "
            f"{ctx.tier_id.value}/{ctx.subtest.id}/run_{ctx.run_number:02d}"
        )


# ---------------------------------------------------------------------------
# Stage map builder
# ---------------------------------------------------------------------------


def _make_scheduled_action(
    scheduler: ParallelismScheduler,
    memory_class: str,
    action: Callable[..., Any],
) -> Callable[..., Any]:
    """Wrap a stage action with semaphore acquire/release for the given memory class.

    Args:
        scheduler: ParallelismScheduler with per-class semaphores
        memory_class: "low", "med", or "high"
        action: Stage callable to wrap

    Returns:
        Wrapped callable that acquires/releases the semaphore around action()

    """

    def wrapped() -> None:
        with scheduler.acquire(memory_class):
            action()

    return wrapped


def build_actions_dict(
    ctx: RunContext,
    scheduler: ParallelismScheduler | None = None,
) -> dict[RunState, Callable[..., Any]]:
    """Build the {RunState -> Callable} map for StateMachine.advance_to_completion().

    Each entry maps from_state -> callable that performs the work for the
    transition starting at that state. If a scheduler is provided, the action
    is wrapped with the appropriate semaphore for that transition's memory class.

    Args:
        ctx: Run context holding all state for this run
        scheduler: Optional ParallelismScheduler; if None, no semaphore wrapping

    Returns:
        Dict mapping RunState to callable stage function

    """
    # Build lookup: from_state -> memory_class from the global registry
    memory_class_by_state = {t.from_state: t.memory_class for t in TRANSITION_REGISTRY}

    raw_actions: dict[RunState, Callable[..., Any]] = {
        RunState.PENDING: lambda: stage_create_dir_structure(ctx),
        RunState.DIR_STRUCTURE_CREATED: lambda: stage_create_worktree(ctx),
        RunState.WORKTREE_CREATED: lambda: stage_apply_symlinks(ctx),
        RunState.SYMLINKS_APPLIED: lambda: stage_commit_config(ctx),
        RunState.CONFIG_COMMITTED: lambda: stage_capture_baseline(ctx),
        RunState.BASELINE_CAPTURED: lambda: stage_write_prompt(ctx),
        RunState.PROMPT_WRITTEN: lambda: stage_generate_replay(ctx),
        RunState.REPLAY_GENERATED: lambda: stage_execute_agent(ctx),
        RunState.AGENT_COMPLETE: lambda: stage_capture_diff(ctx),
        RunState.DIFF_CAPTURED: lambda: stage_run_judge_pipeline(ctx),
        RunState.JUDGE_PIPELINE_RUN: lambda: stage_build_judge_prompt(ctx),
        RunState.JUDGE_PROMPT_BUILT: lambda: stage_execute_judge(ctx),
        RunState.JUDGE_COMPLETE: lambda: stage_finalize_run(ctx),
        RunState.RUN_FINALIZED: lambda: stage_write_report(ctx),
        RunState.CHECKPOINTED: lambda: stage_cleanup_worktree(ctx),
    }

    if scheduler is None:
        return raw_actions

    # Wrap each action with its memory-class semaphore
    scheduled_actions: dict[RunState, Callable[..., Any]] = {}
    for state, action in raw_actions.items():
        memory_class = memory_class_by_state.get(state, "low")
        scheduled_actions[state] = _make_scheduled_action(scheduler, memory_class, action)

    return scheduled_actions
