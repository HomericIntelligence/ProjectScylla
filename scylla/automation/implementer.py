"""Bulk issue implementation using Claude Code in parallel worktrees.

Provides:
- Dependency-aware parallel implementation
- Git worktree isolation
- State persistence and resume
- CI fix automation
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path

from .curses_ui import CursesUI, ThreadLogManager
from .dependency_resolver import DependencyResolver
from .git_utils import get_repo_root, run
from .github_api import fetch_issue_info, gh_pr_create
from .models import (
    ImplementationPhase,
    ImplementationState,
    ImplementerOptions,
    WorkerResult,
)
from .prompts import (
    get_implementation_prompt,
    get_pr_description,
)
from .status_tracker import StatusTracker
from .worktree_manager import WorktreeManager

logger = logging.getLogger(__name__)


class IssueImplementer:
    """Implements GitHub issues in parallel using Claude Code.

    Features:
    - Dependency resolution and topological ordering
    - Parallel execution in isolated git worktrees
    - State persistence for resume capability
    - Automatic CI fix attempts
    - Real-time curses UI for status monitoring
    """

    def __init__(self, options: ImplementerOptions):
        """Initialize issue implementer.

        Args:
            options: Implementer configuration options

        """
        self.options = options
        self.repo_root = get_repo_root()
        self.state_dir = self.repo_root / ".issue_implementer"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.resolver = DependencyResolver(skip_closed=options.skip_closed)
        self.worktree_manager = WorktreeManager()
        self.status_tracker = StatusTracker(options.max_workers)
        self.log_manager = ThreadLogManager()

        self.states: dict[int, ImplementationState] = {}
        self.state_lock = threading.Lock()

        self.ui: CursesUI | None = None

    def run(self) -> dict[int, WorkerResult]:
        """Run the implementer.

        Returns:
            Dictionary mapping issue number to WorkerResult

        """
        # Health check mode
        if self.options.health_check:
            return self._health_check()

        # Load epic and resolve dependencies
        logger.info(f"Loading epic #{self.options.epic_number}")
        self.resolver.load_epic(self.options.epic_number)

        # Detect cycles
        try:
            self.resolver.detect_cycles()
        except Exception as e:
            logger.error(f"Dependency cycle detected: {e}")
            return {}

        # Analyze only mode
        if self.options.analyze_only:
            return self._analyze_dependencies()

        # Resume mode
        if self.options.resume:
            self._load_state()

        # Start UI if not in dry run
        if not self.options.dry_run:
            self.ui = CursesUI(self.status_tracker, self.log_manager)
            self.ui.start()

        try:
            # Implement issues
            results = self._implement_all()
            return results
        finally:
            # Stop UI
            if self.ui:
                self.ui.stop()

            # Cleanup worktrees
            if not self.options.dry_run:
                self.worktree_manager.cleanup_all()

    def _health_check(self) -> dict[int, WorkerResult]:
        """Perform health check of dependencies and environment.

        Returns:
            Empty results dictionary

        """
        logger.info("Running health check...")

        # Check gh CLI
        try:
            run(["gh", "--version"], check=True)
            logger.info("✓ gh CLI available")
        except Exception as e:
            logger.error(f"✗ gh CLI not available: {e}")

        # Check git
        try:
            run(["git", "--version"], check=True)
            logger.info("✓ git available")
        except Exception as e:
            logger.error(f"✗ git not available: {e}")

        # Check Claude Code
        try:
            run(["claude-code", "--version"], check=True)
            logger.info("✓ Claude Code available")
        except Exception as e:
            logger.error(f"✗ Claude Code not available: {e}")

        # Check repository
        try:
            branch = run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
            ).stdout.strip()
            logger.info(f"✓ In git repository (branch: {branch})")
        except Exception as e:
            logger.error(f"✗ Not in git repository: {e}")

        logger.info("Health check complete")
        return {}

    def _analyze_dependencies(self) -> dict[int, WorkerResult]:
        """Analyze and display dependency graph.

        Returns:
            Empty results dictionary

        """
        logger.info("Dependency Analysis")
        logger.info("=" * 60)

        stats = self.resolver.get_stats()
        logger.info(f"Total issues: {stats['total_issues']}")
        logger.info(f"Completed: {stats['completed_issues']}")
        logger.info(f"Remaining: {stats['remaining_issues']}")
        logger.info(f"Ready: {stats['ready_issues']}")

        # Show topological order
        try:
            order = self.resolver.topological_sort()
            logger.info("\nImplementation order:")
            for i, issue_num in enumerate(order, 1):
                issue = self.resolver.graph.issues[issue_num]
                deps = self.resolver.graph.get_dependencies(issue_num)
                dep_str = f" (depends on: {deps})" if deps else ""
                logger.info(f"  {i}. #{issue_num}: {issue.title}{dep_str}")
        except Exception as e:
            logger.error(f"Failed to compute topological order: {e}")

        return {}

    def _implement_all(self) -> dict[int, WorkerResult]:
        """Implement all issues with dependency awareness.

        Returns:
            Dictionary mapping issue number to WorkerResult

        """
        results: dict[int, WorkerResult] = {}

        with ThreadPoolExecutor(max_workers=self.options.max_workers) as executor:
            futures: dict[Future, int] = {}
            active_issues: set[int] = set()

            while True:
                # Get ready issues
                ready = self.resolver.get_ready_issues()

                # Submit new work
                submitted_any = False
                for issue in ready:
                    if issue.number not in active_issues and issue.number not in results:
                        future = executor.submit(self._implement_issue, issue.number)
                        futures[future] = issue.number
                        active_issues.add(issue.number)
                        submitted_any = True

                # Check for completed work
                if not futures:
                    # No active futures and no more work to do
                    break

                # Wait for at least one to complete
                try:
                    done, pending = wait(futures.keys(), timeout=1.0, return_when=FIRST_COMPLETED)
                except Exception:
                    # Timeout or error - check if we should continue
                    if not submitted_any and not futures:
                        break
                    # Add backoff when no work available
                    import time

                    time.sleep(0.1)
                    continue

                # Process completed futures
                for future in done:
                    issue_num = futures[future]
                    active_issues.remove(issue_num)
                    del futures[future]

                    try:
                        result = future.result()
                        results[issue_num] = result

                        if result.success:
                            self.resolver.mark_completed(issue_num)
                            logger.info(f"Issue #{issue_num} completed successfully")
                        else:
                            logger.error(f"Issue #{issue_num} failed: {result.error}")

                    except Exception as e:
                        logger.error(f"Issue #{issue_num} raised exception: {e}")
                        results[issue_num] = WorkerResult(
                            issue_number=issue_num,
                            success=False,
                            error=str(e),
                        )

                # If no futures pending and no new work submitted, we're done
                if not futures and not ready:
                    break

        self._print_summary(results)
        return results

    def _implement_issue(self, issue_number: int) -> WorkerResult:
        """Implement a single issue.

        Args:
            issue_number: Issue number to implement

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
            self.status_tracker.update_slot(slot_id, f"Issue #{issue_number}: Starting")
            self.log_manager.log(thread_id, f"Starting issue #{issue_number}")

            # Initialize state
            state = self._get_or_create_state(issue_number)

            # Create worktree
            branch_name = f"{issue_number}-auto-impl"
            worktree_path = self.worktree_manager.create_worktree(issue_number, branch_name)

            with self.state_lock:
                state.worktree_path = str(worktree_path)
                state.branch_name = branch_name
            self._save_state(state)

            # Check for existing plan
            if not self._has_plan(issue_number):
                self.log_manager.log(thread_id, f"Issue #{issue_number} has no plan, generating...")
                self._generate_plan(issue_number)

            # Implement
            self.status_tracker.update_slot(slot_id, f"Issue #{issue_number}: Implementing")
            with self.state_lock:
                state.phase = ImplementationPhase.IMPLEMENTING
            self._save_state(state)

            self._run_claude_code(
                issue_number, worktree_path, get_implementation_prompt(issue_number)
            )

            # Commit
            self.status_tracker.update_slot(slot_id, f"Issue #{issue_number}: Committing")
            with self.state_lock:
                state.phase = ImplementationPhase.COMMITTING
            self._save_state(state)

            self._commit_changes(issue_number, worktree_path)

            # Push
            self.status_tracker.update_slot(slot_id, f"Issue #{issue_number}: Pushing")
            with self.state_lock:
                state.phase = ImplementationPhase.PUSHING
            self._save_state(state)

            run(["git", "push", "-u", "origin", branch_name], cwd=worktree_path)

            # Create PR
            self.status_tracker.update_slot(slot_id, f"Issue #{issue_number}: Creating PR")
            with self.state_lock:
                state.phase = ImplementationPhase.CREATING_PR
            self._save_state(state)

            pr_number = self._create_pr(issue_number, branch_name)
            with self.state_lock:
                state.pr_number = pr_number
                state.phase = ImplementationPhase.COMPLETED
                state.completed_at = datetime.now(timezone.utc)
            self._save_state(state)

            self.log_manager.log(thread_id, f"Issue #{issue_number} completed: PR #{pr_number}")

            return WorkerResult(
                issue_number=issue_number,
                success=True,
                pr_number=pr_number,
                branch_name=branch_name,
                worktree_path=str(worktree_path),
            )

        except Exception as e:
            logger.error(f"Failed to implement issue #{issue_number}: {e}")
            state = self._get_state(issue_number)
            if state:
                with self.state_lock:
                    state.phase = ImplementationPhase.FAILED
                    state.error = str(e)
                    state.attempts += 1
                self._save_state(state)

            return WorkerResult(
                issue_number=issue_number,
                success=False,
                error=str(e),
            )
        finally:
            self.status_tracker.release_slot(slot_id)

    def _has_plan(self, issue_number: int) -> bool:
        """Check if issue has an implementation plan."""
        try:
            result = run(
                ["gh", "issue", "view", str(issue_number), "--comments", "--json", "comments"],
                capture_output=True,
            )
            data = json.loads(result.stdout)
            comments = data.get("comments", [])

            for comment in comments:
                body = comment.get("body", "")
                if "Implementation Plan" in body or "## Plan" in body:
                    return True

            return False
        except Exception:
            return False

    def _generate_plan(self, issue_number: int) -> None:
        """Generate plan for an issue using plan_issues.py."""
        plan_script = self.repo_root / "scripts" / "plan_issues.py"

        if not plan_script.exists():
            raise RuntimeError(f"Plan script not found: {plan_script}")

        run(
            ["python", str(plan_script), "--issues", str(issue_number)],
            timeout=600,  # 10 minutes
        )

    def _run_claude_code(self, issue_number: int, worktree_path: Path, prompt: str) -> None:
        """Run Claude Code in a worktree."""
        if self.options.dry_run:
            logger.info(f"[DRY RUN] Would run Claude Code for issue #{issue_number}")
            return

        try:
            run(
                ["claude-code", "--message", prompt],
                cwd=worktree_path,
                timeout=1800,  # 30 minutes
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("Claude Code timed out") from e

    def _commit_changes(self, issue_number: int, worktree_path: Path) -> None:
        """Commit changes in worktree."""
        # Check if there are changes
        result = run(
            ["git", "status", "--porcelain"],
            cwd=worktree_path,
            capture_output=True,
        )

        if not result.stdout.strip():
            logger.warning(f"No changes to commit for issue #{issue_number}")
            return

        # Stage only tracked modified files (not . to avoid secrets)
        # Get list of modified tracked files
        modified_result = run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=worktree_path,
            capture_output=True,
        )
        modified_files = (
            modified_result.stdout.strip().split("\n") if modified_result.stdout.strip() else []
        )

        # Also get untracked files that might have been created
        untracked_result = run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=worktree_path,
            capture_output=True,
        )
        untracked_files = (
            untracked_result.stdout.strip().split("\n") if untracked_result.stdout.strip() else []
        )

        # Filter out potential secrets
        files_to_add = []
        for f in modified_files + untracked_files:
            if f and not any(secret in f for secret in [".env", "credentials", ".key", ".pem"]):
                files_to_add.append(f)

        if files_to_add:
            run(["git", "add"] + files_to_add, cwd=worktree_path)

        # Generate commit message
        issue = fetch_issue_info(issue_number)
        commit_msg = f"""feat: Implement #{issue_number}

{issue.title}

Closes #{issue_number}

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
"""

        # Commit
        run(
            ["git", "commit", "-m", commit_msg],
            cwd=worktree_path,
        )

    def _create_pr(self, issue_number: int, branch_name: str) -> int:
        """Create pull request for issue."""
        issue = fetch_issue_info(issue_number)

        pr_title = f"feat: {issue.title}"
        pr_body = get_pr_description(
            issue_number=issue_number,
            summary=f"Implements #{issue_number}",
            changes="- Automated implementation via Claude Code",
            testing="- Automated tests included",
        )

        return gh_pr_create(
            branch=branch_name,
            title=pr_title,
            body=pr_body,
            auto_merge=self.options.auto_merge,
        )

    def _get_or_create_state(self, issue_number: int) -> ImplementationState:
        """Get or create implementation state for an issue."""
        with self.state_lock:
            if issue_number not in self.states:
                self.states[issue_number] = ImplementationState(issue_number=issue_number)
            return self.states[issue_number]

    def _get_state(self, issue_number: int) -> ImplementationState | None:
        """Get implementation state for an issue."""
        with self.state_lock:
            return self.states.get(issue_number)

    def _save_state(self, state: ImplementationState) -> None:
        """Save implementation state to disk."""
        from .github_api import write_secure

        state_file = self.state_dir / f"issue-{state.issue_number}.json"
        # Use write_secure for atomic writes
        write_secure(state_file, state.model_dump_json(indent=2))

    def _load_state(self) -> None:
        """Load all implementation states from disk."""
        for state_file in self.state_dir.glob("issue-*.json"):
            try:
                with open(state_file) as f:
                    state = ImplementationState.model_validate_json(f.read())
                    with self.state_lock:
                        self.states[state.issue_number] = state
                logger.info(f"Loaded state for issue #{state.issue_number}")
            except Exception as e:
                logger.error(f"Failed to load state from {state_file}: {e}")

    def _print_summary(self, results: dict[int, WorkerResult]) -> None:
        """Print implementation summary."""
        total = len(results)
        successful = sum(1 for r in results.values() if r.success)
        failed = total - successful

        logger.info("=" * 60)
        logger.info("Implementation Summary")
        logger.info("=" * 60)
        logger.info(f"Total issues: {total}")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {failed}")

        if successful > 0:
            logger.info("\nSuccessful PRs:")
            for issue_num, result in results.items():
                if result.success and result.pr_number:
                    logger.info(f"  #{issue_num}: PR #{result.pr_number}")

        if failed > 0:
            logger.info("\nFailed issues:")
            for issue_num, result in results.items():
                if not result.success:
                    logger.info(f"  #{issue_num}: {result.error}")
