"""PR review and fix automation using Claude Code in parallel worktrees.

Provides:
- Parallel PR review across multiple issues
- Two-phase workflow: analysis then fix
- Git worktree isolation per PR
- State persistence and UI monitoring
"""

from __future__ import annotations

import contextlib
import json
import logging
import subprocess
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .curses_ui import CursesUI, ThreadLogManager
from .git_utils import get_repo_root, run
from .github_api import _gh_call, fetch_issue_info, write_secure
from .models import ReviewerOptions, ReviewPhase, ReviewState, WorkerResult
from .prompts import get_review_analysis_prompt, get_review_fix_prompt
from .status_tracker import StatusTracker
from .worktree_manager import WorktreeManager

logger = logging.getLogger(__name__)


class PRReviewer:
    """Reviews and fixes open PRs linked to specified issues.

    Features:
    - Parallel PR review in isolated git worktrees
    - Two-phase workflow: analysis session then fix session
    - State persistence for observability
    - Real-time curses UI for status monitoring
    """

    def __init__(self, options: ReviewerOptions):
        """Initialize PR reviewer.

        Args:
            options: Reviewer configuration options

        """
        self.options = options
        self.repo_root = get_repo_root()
        self.state_dir = self.repo_root / ".issue_implementer"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.worktree_manager = WorktreeManager()
        self.status_tracker = StatusTracker(options.max_workers)
        self.log_manager = ThreadLogManager()

        self.states: dict[int, ReviewState] = {}
        self.state_lock = threading.Lock()

        self.ui: CursesUI | None = None

    def _log(self, level: str, msg: str, thread_id: int | None = None) -> None:
        """Log to both standard logger and UI thread buffer.

        Args:
            level: Log level ("error", "warning", or "info")
            msg: Message to log
            thread_id: Thread ID (defaults to current thread)

        """
        getattr(logger, level)(msg)
        tid = thread_id or threading.get_ident()
        prefix = {"error": "ERROR", "warning": "WARN", "info": ""}.get(level, "")
        ui_msg = f"{prefix}: {msg}" if prefix else msg
        self.log_manager.log(tid, ui_msg)

    def run(self) -> dict[int, WorkerResult]:
        """Run the PR reviewer.

        Returns:
            Dictionary mapping issue number to WorkerResult

        """
        logger.info(f"Starting PR review for issues: {self.options.issues}")

        # Discover PRs for all issues
        pr_map = self._discover_prs(self.options.issues)

        if not pr_map:
            logger.warning("No open PRs found for the specified issues")
            return {}

        logger.info(f"Found {len(pr_map)} PR(s) to review: {pr_map}")

        # Start UI if enabled
        if not self.options.dry_run and self.options.enable_ui:
            self.ui = CursesUI(self.status_tracker, self.log_manager)
            self.ui.start()

        try:
            results = self._review_all(pr_map)
            return results
        finally:
            if self.ui:
                self.ui.stop()
            if not self.options.dry_run:
                self.worktree_manager.cleanup_all()

    def _discover_prs(self, issue_numbers: list[int]) -> dict[int, int]:
        """Find open PRs linked to the given issue numbers.

        First tries branch name lookup ({issue}-auto-impl), then falls back
        to searching the PR body for the issue reference.

        Args:
            issue_numbers: List of issue numbers to find PRs for

        Returns:
            Mapping of issue_number -> pr_number for found PRs

        """
        pr_map: dict[int, int] = {}

        for issue_num in issue_numbers:
            pr_number = self._find_pr_for_issue(issue_num)
            if pr_number is not None:
                pr_map[issue_num] = pr_number
            else:
                logger.warning(f"No open PR found for issue #{issue_num}")

        return pr_map

    def _find_pr_for_issue(self, issue_number: int) -> int | None:
        """Find the open PR for a single issue.

        Args:
            issue_number: GitHub issue number

        Returns:
            PR number if found, None otherwise

        """
        # Strategy 1: Look for branch named {issue}-auto-impl
        branch_name = f"{issue_number}-auto-impl"
        try:
            result = _gh_call(
                [
                    "pr",
                    "list",
                    "--head",
                    branch_name,
                    "--state",
                    "open",
                    "--json",
                    "number",
                    "--limit",
                    "1",
                ],
                check=False,
            )
            pr_data = json.loads(result.stdout or "[]")
            if pr_data:
                pr_number = pr_data[0]["number"]
                logger.info(f"Found PR #{pr_number} for issue #{issue_number} via branch name")
                return int(pr_number)
        except Exception as e:
            logger.debug(f"Branch-name lookup failed for issue #{issue_number}: {e}")

        # Strategy 2: Search PR body for issue reference
        try:
            result = _gh_call(
                [
                    "pr",
                    "list",
                    "--state",
                    "open",
                    "--search",
                    f"#{issue_number} in:body",
                    "--json",
                    "number",
                    "--limit",
                    "5",
                ],
                check=False,
            )
            pr_data = json.loads(result.stdout or "[]")
            if pr_data:
                pr_number = pr_data[0]["number"]
                logger.info(f"Found PR #{pr_number} for issue #{issue_number} via body search")
                return int(pr_number)
        except Exception as e:
            logger.debug(f"Body search failed for issue #{issue_number}: {e}")

        return None

    def _gather_pr_context(
        self,
        pr_number: int,
        issue_number: int,
        worktree_path: Path,
    ) -> dict[str, str]:
        """Gather all context needed for PR analysis.

        Fetches diff, CI status, CI failure logs, review comments, and issue body.

        Args:
            pr_number: GitHub PR number
            issue_number: Linked GitHub issue number
            worktree_path: Path to worktree (for cwd)

        Returns:
            Dictionary with keys: pr_diff, issue_body, ci_status, ci_logs,
            review_comments, pr_description

        """
        context: dict[str, str] = {
            "pr_diff": "",
            "issue_body": "",
            "ci_status": "",
            "ci_logs": "",
            "review_comments": "",
            "pr_description": "",
        }

        # Fetch PR diff
        with contextlib.suppress(Exception):
            result = _gh_call(["pr", "diff", str(pr_number)], check=False)
            context["pr_diff"] = (result.stdout or "")[:8000]  # Cap to avoid huge diffs

        # Fetch PR description and reviews/comments
        with contextlib.suppress(Exception):
            result = _gh_call(
                [
                    "pr",
                    "view",
                    str(pr_number),
                    "--json",
                    "body,reviews,comments",
                ],
            )
            pr_data = json.loads(result.stdout or "{}")
            context["pr_description"] = pr_data.get("body", "")

            # Aggregate review comments
            review_parts: list[str] = []
            for review in pr_data.get("reviews", []):
                state = review.get("state", "")
                author = review.get("author", {}).get("login", "unknown")
                body = review.get("body", "")
                if body:
                    review_parts.append(f"[{state}] @{author}: {body}")
            for comment in pr_data.get("comments", []):
                author = comment.get("author", {}).get("login", "unknown")
                body = comment.get("body", "")
                if body:
                    review_parts.append(f"@{author}: {body}")
            context["review_comments"] = "\n".join(review_parts)

        # Fetch CI check status
        with contextlib.suppress(Exception):
            result = _gh_call(
                ["pr", "checks", str(pr_number), "--json", "name,state,conclusion"],
                check=False,
            )
            checks = json.loads(result.stdout or "[]")
            status_lines = [
                f"{c.get('name', '?')}: {c.get('conclusion') or c.get('state', '?')}"
                for c in checks
            ]
            context["ci_status"] = "\n".join(status_lines)

        # Fetch failed CI run logs
        with contextlib.suppress(Exception):
            result = _gh_call(
                [
                    "run",
                    "list",
                    "--branch",
                    f"--pr={pr_number}",
                    "--status",
                    "failure",
                    "--json",
                    "databaseId",
                    "--limit",
                    "1",
                ],
                check=False,
            )
            runs = json.loads(result.stdout or "[]")
            if runs:
                run_id = runs[0].get("databaseId")
                if run_id:
                    log_result = _gh_call(
                        ["run", "view", str(run_id), "--log-failed"],
                        check=False,
                    )
                    context["ci_logs"] = (log_result.stdout or "")[:5000]

        # Fetch issue body
        with contextlib.suppress(Exception):
            issue = fetch_issue_info(issue_number)
            context["issue_body"] = issue.body

        return context

    def _run_analysis_session(
        self,
        pr_number: int,
        issue_number: int,
        worktree_path: Path,
        context: dict[str, str],
        slot_id: int | None = None,
    ) -> str | None:
        """Run the analysis (read-only) Claude session to produce a fix plan.

        Args:
            pr_number: GitHub PR number
            issue_number: Linked issue number
            worktree_path: Path to worktree
            context: PR context from _gather_pr_context
            slot_id: Worker slot ID for status updates

        Returns:
            Path to the saved plan file as a string, or None on failure

        """
        if self.options.dry_run:
            logger.info(f"[DRY RUN] Would run analysis session for PR #{pr_number}")
            return None

        plan_file = self.state_dir / f"review-plan-{issue_number}.md"
        prompt = get_review_analysis_prompt(
            pr_number=pr_number,
            issue_number=issue_number,
            pr_diff=context.get("pr_diff", ""),
            issue_body=context.get("issue_body", ""),
            ci_status=context.get("ci_status", ""),
            ci_logs=context.get("ci_logs", ""),
            review_comments=context.get("review_comments", ""),
            pr_description=context.get("pr_description", ""),
            worktree_path=str(worktree_path),
        )

        prompt_file = worktree_path / f".claude-review-analysis-{issue_number}.md"
        prompt_file.write_text(prompt)

        log_file = self.state_dir / f"review-analysis-{issue_number}.log"

        try:
            result = run(
                [
                    "claude",
                    str(prompt_file),
                    "--output-format",
                    "json",
                    "--permission-mode",
                    "dontAsk",
                    "--allowedTools",
                    "Read,Glob,Grep,Bash",
                ],
                cwd=worktree_path,
                timeout=1200,  # 20 minutes
            )
            log_file.write_text(result.stdout or "")

            # Extract the plan text from JSON output
            try:
                data = json.loads(result.stdout or "{}")
                plan_text = data.get("result", result.stdout or "")
            except (json.JSONDecodeError, AttributeError):
                plan_text = result.stdout or ""

            # Save plan to disk
            write_secure(plan_file, plan_text)
            logger.info(f"Analysis complete for PR #{pr_number}, plan saved to {plan_file}")
            return str(plan_file)

        except subprocess.CalledProcessError as e:
            stdout = e.stdout or ""
            stderr = e.stderr or ""
            error_output = f"EXIT CODE: {e.returncode}\n\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
            log_file.write_text(error_output)
            raise RuntimeError(
                f"Analysis session failed for PR #{pr_number}: {e.stderr or e.stdout}"
            ) from e
        except subprocess.TimeoutExpired as e:
            log_file.write_text(f"TIMEOUT after {e.timeout}s\n\nOutput:\n{e.output or ''}")
            raise RuntimeError(f"Analysis session timed out for PR #{pr_number}") from e
        finally:
            with contextlib.suppress(Exception):
                prompt_file.unlink()

    def _run_fix_session(
        self,
        pr_number: int,
        issue_number: int,
        worktree_path: Path,
        plan_path: str,
        slot_id: int | None = None,
    ) -> str | None:
        """Run the fix (full tools) Claude session to implement fixes.

        Args:
            pr_number: GitHub PR number
            issue_number: Linked issue number
            worktree_path: Path to worktree
            plan_path: Path to the analysis plan file
            slot_id: Worker slot ID for status updates

        Returns:
            Claude session_id if captured, None otherwise

        """
        if self.options.dry_run:
            logger.info(f"[DRY RUN] Would run fix session for PR #{pr_number}")
            return None

        # Read plan content
        plan_content = ""
        with contextlib.suppress(Exception):
            plan_content = Path(plan_path).read_text()

        prompt = get_review_fix_prompt(
            pr_number=pr_number,
            issue_number=issue_number,
            plan=plan_content,
            worktree_path=str(worktree_path),
        )

        prompt_file = worktree_path / f".claude-review-fix-{issue_number}.md"
        prompt_file.write_text(prompt)

        log_file = self.state_dir / f"review-fix-{issue_number}.log"

        try:
            result = run(
                [
                    "claude",
                    str(prompt_file),
                    "--output-format",
                    "json",
                    "--permission-mode",
                    "dontAsk",
                    "--allowedTools",
                    "Read,Write,Edit,Glob,Grep,Bash",
                ],
                cwd=worktree_path,
                timeout=1800,  # 30 minutes
            )
            log_file.write_text(result.stdout or "")

            # Extract session_id
            try:
                data = json.loads(result.stdout or "{}")
                session_id: str | None = data.get("session_id")
                return session_id
            except (json.JSONDecodeError, AttributeError):
                logger.warning(f"Could not parse session_id for PR #{pr_number}")
                return None

        except subprocess.CalledProcessError as e:
            stdout = e.stdout or ""
            stderr = e.stderr or ""
            error_output = f"EXIT CODE: {e.returncode}\n\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
            log_file.write_text(error_output)
            raise RuntimeError(
                f"Fix session failed for PR #{pr_number}: {e.stderr or e.stdout}"
            ) from e
        except subprocess.TimeoutExpired as e:
            log_file.write_text(f"TIMEOUT after {e.timeout}s\n\nOutput:\n{e.output or ''}")
            raise RuntimeError(f"Fix session timed out for PR #{pr_number}") from e
        finally:
            with contextlib.suppress(Exception):
                prompt_file.unlink()

    def _push_fixes(
        self,
        pr_number: int,
        issue_number: int,
        branch_name: str,
        worktree_path: Path,
    ) -> None:
        """Commit any uncommitted changes and push to the PR branch.

        Args:
            pr_number: GitHub PR number
            issue_number: Linked issue number
            branch_name: Git branch name for the PR
            worktree_path: Path to worktree

        """
        if self.options.dry_run:
            logger.info(f"[DRY RUN] Would push fixes for PR #{pr_number}")
            return

        # Check for uncommitted changes
        result = run(
            ["git", "status", "--porcelain"],
            cwd=worktree_path,
            capture_output=True,
        )

        if result.stdout.strip():
            logger.info(f"Committing uncommitted changes for PR #{pr_number}")
            # Stage all non-secret files
            secret_files = {
                ".env",
                ".secret",
                "credentials.json",
                "id_rsa",
                "id_dsa",
                "id_ecdsa",
                "id_ed25519",
            }
            secret_extensions = {".key", ".pem", ".pfx", ".p12"}

            files_to_add: list[str] = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                filename_part = line[3:]
                if filename_part.startswith('"') and filename_part.endswith('"'):
                    filename_part = filename_part[1:-1]
                filename = Path(filename_part).name
                if filename in secret_files or any(
                    filename.endswith(ext) for ext in secret_extensions
                ):
                    logger.warning(f"Skipping potential secret file: {filename_part}")
                    continue
                files_to_add.append(filename_part)

            if files_to_add:
                run(["git", "add", *files_to_add], cwd=worktree_path)
                commit_msg = (
                    f"fix: Address review feedback for PR #{pr_number}\n\n"
                    f"Closes #{issue_number}\n\n"
                    f"Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
                )
                run(["git", "commit", "-m", commit_msg], cwd=worktree_path)
                logger.info(f"Committed changes for PR #{pr_number}")

        # Check if branch needs to be pushed
        result = run(
            ["git", "log", "origin/" + branch_name + "..HEAD", "--oneline"],
            cwd=worktree_path,
            capture_output=True,
            check=False,
        )

        if result.stdout.strip():
            logger.info(
                f"Pushing {len(result.stdout.strip().splitlines())} commit(s) to PR #{pr_number}"
            )
            run(["git", "push", "origin", branch_name], cwd=worktree_path)
            logger.info(f"Pushed fixes to PR #{pr_number}")
        else:
            logger.info(f"No new commits to push for PR #{pr_number}")

    def _run_learn(
        self,
        session_id: str,
        worktree_path: Path,
        issue_number: int,
        slot_id: int | None = None,
    ) -> bool:
        """Resume Claude session to run /learn.

        Args:
            session_id: Claude session ID
            worktree_path: Path to worktree
            issue_number: Issue number
            slot_id: Worker slot ID for status updates

        Returns:
            True if learn completed successfully, False otherwise

        """
        self.state_dir.mkdir(parents=True, exist_ok=True)
        log_file = self.state_dir / f"review-learn-{issue_number}.log"
        try:
            result = run(
                [
                    "claude",
                    "--resume",
                    session_id,
                    (
                        "/skills-registry-commands:learn"
                        " commit the results and create a PR."
                        " IMPORTANT: Only push skills to ProjectMnemosyne."
                        " Do NOT create files under .claude-plugin/ in this repo."
                    ),
                    "--print",
                    "--permission-mode",
                    "dontAsk",
                    "--allowedTools",
                    "Read,Write,Edit,Glob,Grep,Bash",
                ],
                cwd=worktree_path,
                timeout=600,  # 10 minutes
            )
            log_file.write_text(result.stdout or "")
            logger.info(f"Learn completed for issue #{issue_number}")
            return True
        except Exception as e:
            logger.warning(f"Learn failed for issue #{issue_number}: {e}")
            error_output = f"FAILED: {e}\n"
            if hasattr(e, "stdout"):
                error_output += f"\nSTDOUT:\n{getattr(e, 'stdout', '') or ''}"
            if hasattr(e, "stderr"):
                error_output += f"\nSTDERR:\n{getattr(e, 'stderr', '') or ''}"
            log_file.write_text(error_output)
            return False

    def _save_state(self, state: ReviewState) -> None:
        """Save review state to disk."""
        state_file = self.state_dir / f"review-{state.issue_number}.json"
        write_secure(state_file, state.model_dump_json(indent=2))

    def _get_or_create_state(self, issue_number: int, pr_number: int) -> ReviewState:
        """Get or create review state for an issue."""
        with self.state_lock:
            if issue_number not in self.states:
                self.states[issue_number] = ReviewState(
                    issue_number=issue_number,
                    pr_number=pr_number,
                )
            return self.states[issue_number]

    def _fail_review(
        self,
        issue_number: int,
        error_msg: str,
        slot_id: int,
    ) -> WorkerResult:
        """Record a review failure, update state and tracker, and return a failed WorkerResult.

        Args:
            issue_number: GitHub issue number.
            error_msg: Human-readable error description.
            slot_id: Worker slot ID for status updates.

        Returns:
            WorkerResult with success=False.

        """
        self.status_tracker.update_slot(slot_id, f"#{issue_number}: FAILED - {error_msg[:50]}")
        err_state = self.states.get(issue_number)
        if err_state:
            with self.state_lock:
                err_state.phase = ReviewPhase.FAILED
                err_state.error = error_msg
            self._save_state(err_state)
        return WorkerResult(issue_number=issue_number, success=False, error=error_msg)

    def _review_pr(self, issue_number: int, pr_number: int) -> WorkerResult:
        """Review and fix a single PR.

        Args:
            issue_number: GitHub issue number
            pr_number: GitHub PR number

        Returns:
            WorkerResult

        """
        slot_id = self.status_tracker.acquire_slot()
        if slot_id is None:
            return WorkerResult(
                issue_number=issue_number,
                success=False,
                error="Failed to acquire worker slot",
            )

        thread_id = threading.get_ident()

        try:
            self.status_tracker.update_slot(
                slot_id, f"#{issue_number}: PR #{pr_number} Creating worktree"
            )
            self._log(
                "info", f"Starting review of PR #{pr_number} for issue #{issue_number}", thread_id
            )

            state = self._get_or_create_state(issue_number, pr_number)

            # Create worktree on the PR branch
            branch_name = f"{issue_number}-auto-impl"
            worktree_path = self.worktree_manager.create_worktree(issue_number, branch_name)

            with self.state_lock:
                state.worktree_path = str(worktree_path)
                state.branch_name = branch_name
            self._save_state(state)

            # Phase 1: Gather context
            self.status_tracker.update_slot(
                slot_id, f"#{issue_number}: PR #{pr_number} Gathering context"
            )
            context = self._gather_pr_context(pr_number, issue_number, worktree_path)

            # Phase 2: Analysis session
            self.status_tracker.update_slot(slot_id, f"#{issue_number}: PR #{pr_number} Analyzing")
            with self.state_lock:
                state.phase = ReviewPhase.ANALYZING
            self._save_state(state)

            plan_path = self._run_analysis_session(
                pr_number, issue_number, worktree_path, context, slot_id
            )

            with self.state_lock:
                state.plan_path = plan_path
            self._save_state(state)

            # Phase 3: Fix session (always runs, even if no problems found)
            self.status_tracker.update_slot(slot_id, f"#{issue_number}: PR #{pr_number} Fixing")
            with self.state_lock:
                state.phase = ReviewPhase.FIXING
            self._save_state(state)

            session_id = self._run_fix_session(
                pr_number, issue_number, worktree_path, plan_path or "", slot_id
            )

            with self.state_lock:
                state.session_id = session_id
            self._save_state(state)

            # Phase 4: Push fixes
            self.status_tracker.update_slot(slot_id, f"#{issue_number}: PR #{pr_number} Pushing")
            with self.state_lock:
                state.phase = ReviewPhase.PUSHING
            self._save_state(state)

            self._push_fixes(pr_number, issue_number, branch_name, worktree_path)

            # Phase 5: Learn (optional)
            if self.options.enable_learn and session_id:
                self.status_tracker.update_slot(
                    slot_id, f"#{issue_number}: PR #{pr_number} Learn"
                )
                with self.state_lock:
                    state.phase = ReviewPhase.LEARN
                self._save_state(state)
                self._run_learn(session_id, worktree_path, issue_number, slot_id)

            # Mark completed
            with self.state_lock:
                state.phase = ReviewPhase.COMPLETED
                state.completed_at = datetime.now(timezone.utc)
            self._save_state(state)

            self._log(
                "info", f"PR #{pr_number} review complete for issue #{issue_number}", thread_id
            )

            return WorkerResult(
                issue_number=issue_number,
                success=True,
                pr_number=pr_number,
                branch_name=branch_name,
                worktree_path=str(worktree_path),
            )

        except subprocess.TimeoutExpired as e:
            error_msg = f"Timeout: {' '.join(str(c) for c in e.cmd[:3])} exceeded {e.timeout}s"
            self._log("error", error_msg, thread_id)
            return self._fail_review(issue_number, error_msg, slot_id)

        except subprocess.CalledProcessError as e:
            error_msg = (
                f"Command failed (exit {e.returncode}): {' '.join(str(c) for c in e.cmd[:3])}"
            )
            self._log("error", error_msg, thread_id)
            return self._fail_review(issue_number, error_msg, slot_id)

        except RuntimeError as e:
            self._log("error", f"Runtime error: {e}", thread_id)
            return self._fail_review(issue_number, str(e)[:80], slot_id)

        except Exception as e:
            self._log("error", f"Unexpected {type(e).__name__}: {e}", thread_id)
            return self._fail_review(issue_number, str(e)[:80], slot_id)

        finally:
            time.sleep(1)
            self.status_tracker.release_slot(slot_id)

    def _review_all(self, pr_map: dict[int, int]) -> dict[int, WorkerResult]:
        """Review all PRs in parallel.

        Args:
            pr_map: Mapping of issue_number -> pr_number

        Returns:
            Dictionary mapping issue number to WorkerResult

        """
        results: dict[int, WorkerResult] = {}

        with ThreadPoolExecutor(max_workers=self.options.max_workers) as executor:
            futures: dict[Future[Any], int] = {}

            # Submit all PRs upfront (no dependency ordering needed for review)
            for issue_num, pr_num in pr_map.items():
                future = executor.submit(self._review_pr, issue_num, pr_num)
                futures[future] = issue_num

            while futures:
                try:
                    done, _pending = wait(futures.keys(), timeout=1.0, return_when=FIRST_COMPLETED)
                except Exception:
                    time.sleep(0.1)
                    continue

                for future in done:
                    issue_num = futures.pop(future)
                    try:
                        result = future.result()
                        results[issue_num] = result
                        if result.success:
                            logger.info(f"Issue #{issue_num} PR review completed")
                        else:
                            logger.error(f"Issue #{issue_num} PR review failed: {result.error}")
                    except Exception as e:
                        logger.error(f"Issue #{issue_num} raised exception: {e}")
                        results[issue_num] = WorkerResult(
                            issue_number=issue_num,
                            success=False,
                            error=str(e),
                        )

        self._print_summary(results)
        return results

    def _print_summary(self, results: dict[int, WorkerResult]) -> None:
        """Print review summary."""
        total = len(results)
        successful = sum(1 for r in results.values() if r.success)
        failed = total - successful

        logger.info("=" * 60)
        logger.info("PR Review Summary")
        logger.info("=" * 60)
        logger.info(f"Total PRs: {total}")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {failed}")

        if failed > 0:
            logger.info("\nFailed issues:")
            for issue_num, result in results.items():
                if not result.success:
                    logger.info(f"  #{issue_num}: {result.error}")
