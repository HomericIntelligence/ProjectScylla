"""Bulk issue planning using Claude Code.

Provides:
- Parallel issue planning
- Duplicate plan detection
- Rate limit handling
- Plan posting to GitHub issues
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Any

from .git_utils import get_repo_root
from .github_api import (
    _gh_call,
    gh_issue_comment,
    gh_issue_json,
    prefetch_issue_states,
)
from .models import PlannerOptions, PlanResult
from .prompts import get_advise_prompt, get_plan_prompt
from .rate_limit import detect_rate_limit, wait_until
from .status_tracker import StatusTracker

logger = logging.getLogger(__name__)


class Planner:
    """Plans GitHub issues using Claude Code.

    Supports parallel planning with rate limit handling and
    duplicate detection.
    """

    def __init__(self, options: PlannerOptions):
        """Initialize planner.

        Args:
            options: Planner configuration options

        """
        self.options = options
        self.status_tracker = StatusTracker(options.parallel)
        self.results: dict[int, PlanResult] = {}
        self.lock = threading.Lock()

    def run(self) -> dict[int, PlanResult]:
        """Run the planner on all issues.

        Returns:
            Dictionary mapping issue number to PlanResult

        """
        logger.info(
            f"Planning {len(self.options.issues)} issues "
            f"with {self.options.parallel} parallel workers"
        )

        # Filter closed issues if requested
        issues_to_plan = self._filter_issues()

        if not issues_to_plan:
            logger.warning("No issues to plan")
            return {}

        # Plan issues in parallel
        with ThreadPoolExecutor(max_workers=self.options.parallel) as executor:
            futures: dict[Future[Any], int] = {}

            for issue_num in issues_to_plan:
                future = executor.submit(self._plan_issue, issue_num)
                futures[future] = issue_num

            # Collect results
            for future in as_completed(futures):
                issue_num = futures[future]
                try:
                    result = future.result()
                    with self.lock:
                        self.results[issue_num] = result
                except Exception as e:
                    logger.error(f"Failed to plan issue #{issue_num}: {e}")
                    with self.lock:
                        self.results[issue_num] = PlanResult(
                            issue_number=issue_num,
                            success=False,
                            error=str(e),
                        )

        self._print_summary()
        return self.results

    def _filter_issues(self) -> list[int]:
        """Filter issues based on options.

        Returns:
            List of issue numbers to plan

        """
        issues_to_plan = []

        # Batch fetch issue states if we need to check for closed issues
        cached_states = {}
        if self.options.skip_closed:
            cached_states = prefetch_issue_states(self.options.issues)

        for issue_num in self.options.issues:
            # Check if already planned (unless force)
            if not self.options.force and self._has_existing_plan(issue_num):
                logger.info(f"Issue #{issue_num} already has a plan, skipping")
                with self.lock:
                    self.results[issue_num] = PlanResult(
                        issue_number=issue_num,
                        success=True,
                        plan_already_exists=True,
                    )
                continue

            # Check if closed (using cached states)
            if self.options.skip_closed:
                state = cached_states.get(issue_num)
                if state and state.value == "CLOSED":
                    logger.info(f"Issue #{issue_num} is closed, skipping")
                    continue

            issues_to_plan.append(issue_num)

        return issues_to_plan

    def _has_existing_plan(self, issue_number: int) -> bool:
        """Check if an issue already has a plan in comments.

        Args:
            issue_number: Issue number to check

        Returns:
            True if plan exists

        """
        try:
            result = _gh_call(
                [
                    "issue",
                    "view",
                    str(issue_number),
                    "--comments",
                    "--json",
                    "comments",
                ],
            )

            data = json.loads(result.stdout)
            comments = data.get("comments", [])

            # Look for plan markers in comments
            plan_markers = [
                "# Implementation Plan",
                "## Implementation Plan",
                "# Plan",
                "## Plan",
                "## Objective",
            ]

            for comment in comments:
                body = comment.get("body", "")
                if any(marker in body for marker in plan_markers):
                    logger.debug(f"Found existing plan for issue #{issue_number}")
                    return True

            return False

        except Exception as e:
            logger.warning(f"Failed to check for existing plan on issue #{issue_number}: {e}")
            return False

    def _plan_issue(self, issue_number: int) -> PlanResult:
        """Plan a single issue.

        Args:
            issue_number: Issue number to plan

        Returns:
            PlanResult

        """
        slot_id = self.status_tracker.acquire_slot()
        if slot_id is None:
            return PlanResult(
                issue_number=issue_number,
                success=False,
                error="Failed to acquire worker slot",
            )

        try:
            self.status_tracker.update_slot(slot_id, f"Planning issue #{issue_number}")

            if self.options.dry_run:
                logger.info(f"[DRY RUN] Would plan issue #{issue_number}")
                return PlanResult(issue_number=issue_number, success=True)

            # Generate plan using Claude Code
            plan = self._generate_plan(issue_number)

            # Post plan to issue
            self._post_plan(issue_number, plan)

            self.status_tracker.update_slot(slot_id, f"Completed issue #{issue_number}")
            return PlanResult(issue_number=issue_number, success=True)

        except Exception as e:
            logger.error(f"Failed to plan issue #{issue_number}: {e}")
            return PlanResult(
                issue_number=issue_number,
                success=False,
                error=str(e),
            )
        finally:
            self.status_tracker.release_slot(slot_id)

    def _call_claude(
        self,
        prompt: str,
        *,
        max_retries: int = 3,
        timeout: int = 300,
        extra_args: list[str] | None = None,
    ) -> str:
        """Call Claude CLI with retry logic for rate limits.

        Args:
            prompt: The prompt to send to Claude
            max_retries: Maximum retry attempts for rate limits
            timeout: Timeout in seconds
            extra_args: Additional CLI arguments

        Returns:
            Claude's response text

        Raises:
            RuntimeError: If Claude call fails

        """
        # Build command
        cmd = [
            "claude",
            "--print",
            prompt,
            "--output-format",
            "text",
        ]

        # Add system prompt if configured
        if self.options.system_prompt_file and self.options.system_prompt_file.exists():
            cmd.extend(["--system-prompt", str(self.options.system_prompt_file)])

        # Add extra args
        if extra_args:
            cmd.extend(extra_args)

        # Invoke Claude
        try:
            # Preserve existing environment and set CLAUDECODE
            env = os.environ.copy()
            env["CLAUDECODE"] = ""

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=timeout,
                env=env,  # Avoid nested-session guard
                stdin=subprocess.DEVNULL,
            )

            response = result.stdout.strip()

            if not response:
                raise RuntimeError("Claude returned empty response")

            return response

        except subprocess.CalledProcessError as e:
            stderr = e.stderr if e.stderr else ""

            # Check for rate limit
            is_rate_limited, reset_epoch = detect_rate_limit(stderr)
            if is_rate_limited and max_retries > 0:
                if reset_epoch > 0:
                    wait_until(reset_epoch, "Claude API rate limit")
                else:
                    # No reset time, wait a bit
                    import time

                    time.sleep(5)
                # Retry with decremented counter
                return self._call_claude(
                    prompt,
                    max_retries=max_retries - 1,
                    timeout=timeout,
                    extra_args=extra_args,
                )

            raise RuntimeError(f"Claude failed: {stderr}") from e

        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"Claude timed out after {timeout}s") from e

    def _run_advise(self, issue_number: int, issue_title: str, issue_body: str) -> str:
        """Search team knowledge base for relevant prior learnings.

        Args:
            issue_number: Issue number
            issue_title: Issue title
            issue_body: Issue body/description

        Returns:
            Advise findings text, or empty string if advise fails

        """
        try:
            # Locate ProjectMnemosyne
            repo_root = get_repo_root()
            mnemosyne_root = repo_root / "build" / "ProjectMnemosyne"

            if not mnemosyne_root.exists():
                logger.warning(
                    "ProjectMnemosyne not found at build/ProjectMnemosyne, skipping advise step"
                )
                return ""

            marketplace_path = mnemosyne_root / ".claude-plugin" / "marketplace.json"
            if not marketplace_path.exists():
                logger.warning(
                    f"Marketplace file not found at {marketplace_path}, skipping advise step"
                )
                return ""

            # Build advise prompt
            advise_prompt = get_advise_prompt(
                issue_number=issue_number,
                issue_title=issue_title,
                issue_body=issue_body,
                marketplace_path=str(marketplace_path),
            )

            # Call Claude with shorter timeout
            logger.info(f"Running advise for issue #{issue_number}...")
            findings = self._call_claude(advise_prompt, timeout=180)

            return findings

        except Exception as e:
            logger.warning(f"Advise step failed for issue #{issue_number}: {e}")
            return ""

    def _generate_plan(self, issue_number: int, max_retries: int = 3) -> str:
        """Generate implementation plan using Claude Code.

        Args:
            issue_number: Issue number to plan
            max_retries: Maximum retry attempts for rate limits

        Returns:
            Generated plan text

        Raises:
            RuntimeError: If plan generation fails

        """
        # Fetch issue data
        issue_data = gh_issue_json(issue_number)
        issue_title = issue_data.get("title", f"Issue #{issue_number}")
        issue_body = issue_data.get("body", "")

        # Run advise step if enabled
        advise_findings = ""
        if self.options.enable_advise:
            advise_findings = self._run_advise(issue_number, issue_title, issue_body)

        # Build prompt
        prompt = get_plan_prompt(issue_number)

        # Add issue context
        context_parts = [f"# Issue #{issue_number}: {issue_title}", "", issue_body]

        # Inject advise findings if available
        if advise_findings:
            context_parts.extend(
                [
                    "",
                    "---",
                    "",
                    "## Prior Learnings from Team Knowledge Base",
                    "",
                    advise_findings,
                ]
            )

        context_parts.extend(["", "---", "", prompt])

        context = "\n".join(context_parts)

        # Call Claude to generate plan
        plan = self._call_claude(context, timeout=300)

        return plan

    def _post_plan(self, issue_number: int, plan: str) -> None:
        """Post plan to issue as a comment.

        Args:
            issue_number: Issue number
            plan: Plan text

        """
        # Add header
        comment_body = f"""# Implementation Plan

{plan}

---
*Generated by Claude Code Planner*
"""

        gh_issue_comment(issue_number, comment_body)
        logger.info(f"Posted plan to issue #{issue_number}")

    def _print_summary(self) -> None:
        """Print summary of planning results."""
        total = len(self.results)
        successful = sum(1 for r in self.results.values() if r.success)
        already_planned = sum(1 for r in self.results.values() if r.plan_already_exists)
        failed = total - successful

        logger.info("=" * 60)
        logger.info("Planning Summary")
        logger.info("=" * 60)
        logger.info(f"Total issues: {total}")
        logger.info(f"Successfully planned: {successful - already_planned}")
        logger.info(f"Already planned: {already_planned}")
        logger.info(f"Failed: {failed}")

        if failed > 0:
            logger.info("\nFailed issues:")
            for issue_num, result in self.results.items():
                if not result.success:
                    logger.info(f"  #{issue_num}: {result.error}")
