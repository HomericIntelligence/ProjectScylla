"""Finalization stage functions extracted from stages.py.

Contains the four stages that run after the judge pipeline:
- stage_execute_judge: calls LLM judge(s) and computes consensus
- stage_finalize_run: builds and persists E2ERunResult
- stage_write_report: generates per-run markdown and JSON reports
- stage_cleanup_worktree: removes workspace for passing runs
"""

from __future__ import annotations

import dataclasses
import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from scylla.e2e.models import E2ERunResult
from scylla.e2e.paths import get_agent_dir, get_judge_dir
from scylla.e2e.stage_process_metrics import (
    _finalize_change_results,
    _finalize_progress_steps,
    _load_process_metrics_from_run_result,
)
from scylla.metrics.process import ProcessMetrics, ProgressTracker, calculate_process_metrics

if TYPE_CHECKING:
    from scylla.e2e.stages import RunContext

logger = logging.getLogger(__name__)


class _JudgeParseError(ValueError):
    """Judge parse failure with captured outputs for diagnostics."""

    def __init__(self, original: ValueError, stdout: str, stderr: str) -> None:
        super().__init__(str(original))
        self.stdout = stdout
        self.stderr = stderr


def _call_judge_with_retry(
    judge_prompt: str,
    model: str,
    workspace: Any,
    judge_num: int,
) -> tuple[str, str, str, Any]:
    """Call the LLM judge with one retry on parse failure.

    Args:
        judge_prompt: The full judge prompt text.
        model: Model identifier to use for judging.
        workspace: Workspace path passed to the judge runner.
        judge_num: Judge index (1-based), used in log messages.

    Returns:
        Tuple of (stdout, stderr, raw_result, parsed_judge_result).

    Raises:
        _JudgeParseError: If both attempts fail to produce valid JSON
            (wraps ValueError with captured stdout/stderr).

    """
    from scylla.e2e.llm_judge import _call_claude_judge, _parse_judge_response

    json_reminder = "\n\nIMPORTANT: Respond with ONLY a valid JSON object."
    last_parse_error: ValueError | None = None
    stdout = stderr = result = ""
    judge_result: Any = None
    for attempt in range(2):
        prompt = judge_prompt if attempt == 0 else judge_prompt + json_reminder
        stdout, stderr, result = _call_claude_judge(prompt, model, workspace)
        try:
            judge_result = _parse_judge_response(result)
            last_parse_error = None
            break
        except ValueError as e:
            last_parse_error = e
            if attempt == 0:
                logger.warning(
                    f"Judge {judge_num} parse failed (attempt {attempt + 1}), retrying... "
                    f"stdout_len={len(stdout)}, stderr_len={len(stderr)}"
                )
    if last_parse_error:
        raise _JudgeParseError(last_parse_error, stdout=stdout, stderr=stderr)
    return stdout, stderr, result, judge_result


def _save_judge_failure(judge_dir: Any, judge_num: int, error: Exception) -> None:
    """Save diagnostics for a failed judge invocation."""
    judge_specific_dir = judge_dir / f"judge_{judge_num:02d}"
    judge_specific_dir.mkdir(parents=True, exist_ok=True)

    timing_file = judge_specific_dir / "timing.json"
    with open(timing_file, "w") as f:
        json.dump(
            {
                "judge_duration_seconds": 0.0,
                "measured_at": datetime.now(timezone.utc).isoformat(),
                "failed": True,
                "error": str(error),
            },
            f,
            indent=2,
        )
    (judge_specific_dir / "error.log").write_text(f"Judge failed: {error}\n")

    # Save raw outputs for debugging (available from _JudgeParseError and
    # subprocess.TimeoutExpired — the latter stores bytes, not str).
    for attr, filename in (("stdout", "stdout.log"), ("stderr", "stderr.log")):
        data = getattr(error, attr, None)
        if data:
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="replace")
            (judge_specific_dir / filename).write_text(data)


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
    from scylla.e2e.llm_judge import JudgeResult, _save_judge_logs
    from scylla.e2e.models import JudgeResultSummary
    from scylla.e2e.rate_limit import RateLimitError

    judge_dir = get_judge_dir(ctx.run_dir)
    if not ctx.config.judge_models:
        raise ValueError("judge_models is required")

    if not ctx.judge_prompt:
        saved_prompt = ctx.run_dir / "judge_prompt.md"
        if saved_prompt.exists():
            ctx.judge_prompt = saved_prompt.read_text()
            logger.info("Reloaded judge_prompt from disk in stage_execute_judge")
        else:
            raise ValueError(
                f"judge_prompt is empty and no judge_prompt.md found at {saved_prompt}. "
                f"Cannot execute judge without a prompt."
            )

    judges = []
    judge_start = datetime.now(timezone.utc)

    for judge_num, model in enumerate(ctx.config.judge_models, start=1):
        logger.info(
            f"[JUDGE] Running judge {judge_num}/{len(ctx.config.judge_models)} with model[{model}]"
        )

        try:
            actual_judge_dir = judge_dir / f"judge_{judge_num:02d}"
            actual_judge_dir.mkdir(parents=True, exist_ok=True)

            stdout, stderr, result, judge_result = _call_judge_with_retry(
                ctx.judge_prompt, model, ctx.workspace, judge_num
            )

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
            _save_judge_failure(judge_dir, judge_num, e)

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


def _check_agent_rate_limit(ctx: RunContext) -> None:
    """Raise RateLimitError if rate limit is detected in agent output.

    Also handles the special case of invalid judge output with exit_code=-1.

    Args:
        ctx: Run context with agent_result and judgment populated.

    Raises:
        RateLimitError: If a rate limit is detected.

    """
    from scylla.e2e.rate_limit import RateLimitError, detect_rate_limit

    assert ctx.agent_result is not None  # noqa: S101 — guarded by caller
    assert ctx.judgment is not None  # noqa: S101 — guarded by caller

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


def stage_finalize_run(ctx: RunContext) -> None:
    """JUDGE_COMPLETE -> RUN_FINALIZED: Build RunResult and save run_result.json.

    Checks for rate limit, builds E2ERunResult, saves run_result.json,
    and calls mark_run_completed() for v2.0 backward compat.
    Report generation is handled by the next stage (stage_write_report).

    Args:
        ctx: Run context (mutates ctx.run_result)

    """
    if ctx.agent_result is None:
        logger.error(
            "stage_finalize_run: agent_result is None for %s/%s/run_%02d "
            "(run_dir=%s). Invalid agent result not caught by _reset_invalid_runs().",
            ctx.tier_id.value,
            ctx.subtest.id,
            ctx.run_number,
            ctx.run_dir,
        )
        raise RuntimeError(
            f"agent_result is None for {ctx.tier_id.value}/{ctx.subtest.id}"
            f"/run_{ctx.run_number:02d} — cannot finalize"
        )
    if ctx.judgment is None:
        logger.error(
            "stage_finalize_run: judgment is None for %s/%s/run_%02d (run_dir=%s).",
            ctx.tier_id.value,
            ctx.subtest.id,
            ctx.run_number,
            ctx.run_dir,
        )
        raise RuntimeError(
            f"judgment is None for {ctx.tier_id.value}/{ctx.subtest.id}"
            f"/run_{ctx.run_number:02d} — cannot finalize"
        )

    # Resume guard: if progress_steps/change_results were not populated this
    # session (e.g., crash between DIFF_CAPTURED and JUDGE_COMPLETE skipped
    # stage_capture_diff), try to reload from a previously-saved run_result.json.
    if ctx.progress_steps is None or ctx.change_results is None:
        loaded_steps, loaded_changes = _load_process_metrics_from_run_result(ctx.run_dir)
        if ctx.progress_steps is None:
            ctx.progress_steps = loaded_steps
        if ctx.change_results is None:
            ctx.change_results = loaded_changes

    agent_dir = get_agent_dir(ctx.run_dir)

    _check_agent_rate_limit(ctx)

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

    # Finalize process metrics with actual judge outcome
    judge_passed = run_result.judge_passed
    judge_score = run_result.judge_score
    pipeline_passed = (
        ctx.judge_pipeline_result.all_passed if ctx.judge_pipeline_result is not None else True
    )
    final_change_results = _finalize_change_results(
        ctx.change_results or [],
        judge_passed=judge_passed,
        pipeline_passed=pipeline_passed,
    )
    final_progress_steps = _finalize_progress_steps(
        ctx.progress_steps or [], judge_score=judge_score
    )
    tracker = ProgressTracker(
        expected_steps=final_progress_steps,
        achieved_steps=[s for s in final_progress_steps if s.completed],
    )
    pm: ProcessMetrics = calculate_process_metrics(tracker=tracker, changes=final_change_results)

    # Build extended result dict with process_metrics, progress_tracking, and changes blocks
    result_dict = run_result.to_dict()
    result_dict["process_metrics"] = {
        "r_prog": pm.r_prog,
        "strategic_drift": pm.strategic_drift,
        "cfp": pm.cfp,
        "pr_revert_rate": pm.pr_revert_rate,
    }
    result_dict["progress_tracking"] = [dataclasses.asdict(s) for s in final_progress_steps]
    result_dict["changes"] = [dataclasses.asdict(c) for c in final_change_results]

    # Save full E2ERunResult (with process_metrics) for checkpoint resume
    with open(ctx.run_dir / "run_result.json", "w") as f:
        json.dump(result_dict, f, indent=2)

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
        logger.error(
            "stage_write_report: agent_result is None for %s/%s/run_%02d (run_dir=%s).",
            ctx.tier_id.value,
            ctx.subtest.id,
            ctx.run_number,
            ctx.run_dir,
        )
        raise RuntimeError(
            f"agent_result is None for {ctx.tier_id.value}/{ctx.subtest.id}"
            f"/run_{ctx.run_number:02d} — cannot write report"
        )
    if ctx.judgment is None:
        logger.error(
            "stage_write_report: judgment is None for %s/%s/run_%02d (run_dir=%s).",
            ctx.tier_id.value,
            ctx.subtest.id,
            ctx.run_number,
            ctx.run_dir,
        )
        raise RuntimeError(
            f"judgment is None for {ctx.tier_id.value}/{ctx.subtest.id}"
            f"/run_{ctx.run_number:02d} — cannot write report"
        )

    token_stats = ctx.run_result.token_stats

    # Read process_metrics from run_result.json written by stage_finalize_run
    process_metrics: dict[str, Any] | None = None
    try:
        with open(ctx.run_dir / "run_result.json") as f:
            run_result_data = json.load(f)
        process_metrics = run_result_data.get("process_metrics")
    except (OSError, json.JSONDecodeError, KeyError):
        pass

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
        process_metrics=process_metrics,
    )

    save_run_report_json(
        run_dir=ctx.run_dir,
        run_number=ctx.run_number,
        score=ctx.judgment["score"],
        grade=ctx.judgment["grade"],
        passed=ctx.judgment["passed"],
        cost_usd=ctx.agent_result.cost_usd,
        duration_seconds=ctx.agent_duration + ctx.judge_duration,
        process_metrics=process_metrics,
    )


def stage_cleanup_worktree(ctx: RunContext) -> None:
    """CHECKPOINTED -> WORKTREE_CLEANED: Remove git worktree to free disk space.

    By default, cleans up ALL workspaces (passed and failed) since the diff,
    pipeline results, and judge prompt are already saved. Use
    --keep-failed-workspaces to preserve failed run workspaces for debugging.

    Note: Workspace semaphore acquire/release is handled by the caller
    (SubtestExecutor) via ResourceManager.workspace_slot() context manager,
    not by individual stage functions.

    Args:
        ctx: Run context

    """
    # Determine if we should preserve this workspace
    keep_failed = ctx.config.keep_failed_workspaces
    run_passed = ctx.run_result is not None and ctx.run_result.judge_passed
    if not run_passed and ctx.checkpoint:
        run_status = ctx.checkpoint.get_run_status(
            ctx.tier_id.value, ctx.subtest.id, ctx.run_number
        )
        run_passed = run_status == "passed"

    should_cleanup = run_passed or not keep_failed

    if should_cleanup and ctx.workspace.exists():
        try:
            ctx.workspace_manager.cleanup_worktree(ctx.workspace)
            status = "passed" if run_passed else "failed"
            logger.info(
                f"Cleaned up worktree for {status} run {ctx.tier_id.value}/{ctx.subtest.id}"
                f"/run_{ctx.run_number:02d}"
            )
        except Exception as e:
            # Cleanup failure is non-fatal - log and continue
            logger.warning(
                f"Failed to clean up worktree for "
                f"{ctx.tier_id.value}/{ctx.subtest.id}/run_{ctx.run_number:02d}: {e}"
            )
    elif not should_cleanup:
        logger.debug(
            f"Preserving workspace for failed run (--keep-failed-workspaces) "
            f"{ctx.tier_id.value}/{ctx.subtest.id}/run_{ctx.run_number:02d}"
        )
