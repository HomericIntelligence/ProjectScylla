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
import re
import subprocess
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path

from .curses_ui import CursesUI, ThreadLogManager
from .dependency_resolver import DependencyResolver
from .git_utils import get_repo_root, run
from .github_api import fetch_issue_info, gh_issue_comment, gh_issue_create, gh_pr_create
from .models import (
    ImplementationPhase,
    ImplementationState,
    ImplementerOptions,
    IssueState,
    WorkerResult,
)
from .prompts import (
    get_follow_up_prompt,
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

        # Load issues or epic and resolve dependencies
        if self.options.issues:
            logger.info(f"Loading issues: {self.options.issues}")
            self._load_issues(self.options.issues)
        else:
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

        # Start UI if enabled and not in dry run
        if not self.options.dry_run and self.options.enable_ui:
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

    def _load_issues(self, issue_numbers: list[int]) -> None:
        """Load specific issues into the dependency graph.

        Args:
            issue_numbers: List of issue numbers to load

        """
        from .github_api import fetch_issue_info, prefetch_issue_states

        # Prefetch states for efficiency
        cached_states = prefetch_issue_states(issue_numbers)

        for issue_num in issue_numbers:
            if self.options.skip_closed and cached_states.get(issue_num) == IssueState.CLOSED:
                logger.info(f"Skipping closed issue #{issue_num}")
                self.resolver.completed.add(issue_num)
                continue

            try:
                issue = fetch_issue_info(issue_num)
                self.resolver.add_issue(issue)

                # Load dependencies recursively
                self.resolver._load_dependencies(issue, cached_states)

            except Exception as e:
                logger.error(f"Failed to load issue #{issue_num}: {e}")

        logger.info(f"Loaded {len(self.resolver.graph.issues)} issues")

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
            run(["claude", "--version"], check=True)
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

        # Detect and log issues that were skipped due to unresolved dependencies
        attempted_issues = set(results.keys())
        all_issues = set(self.resolver.graph.issues.keys())
        skipped_issues = all_issues - attempted_issues - self.resolver.completed

        if skipped_issues:
            logger.warning(f"Skipped {len(skipped_issues)} issue(s) due to failed dependencies:")
            for issue_num in sorted(skipped_issues):
                deps = self.resolver.graph.get_dependencies(issue_num)
                failed_deps = [d for d in deps if d not in self.resolver.completed]
                logger.warning(f"  #{issue_num}: blocked by failed issue(s) {failed_deps}")

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

            # Fetch issue info for context
            issue = fetch_issue_info(issue_number)
            session_id = self._run_claude_code(
                issue_number,
                worktree_path,
                get_implementation_prompt(
                    issue_number=issue_number,
                    issue_title=issue.title,
                    issue_body=issue.body,
                    branch_name=branch_name,
                    worktree_path=str(worktree_path),
                ),
            )
            with self.state_lock:
                state.session_id = session_id
            self._save_state(state)

            # Verify commit, push, and PR were created by Claude
            self.status_tracker.update_slot(slot_id, f"Issue #{issue_number}: Verifying")
            with self.state_lock:
                state.phase = ImplementationPhase.CREATING_PR
            self._save_state(state)

            pr_number = self._ensure_pr_created(issue_number, branch_name, worktree_path)
            with self.state_lock:
                state.pr_number = pr_number
            self._save_state(state)

            # Retrospective phase (after CREATING_PR, before COMPLETED)
            if self.options.enable_retrospective and state.session_id:
                self.status_tracker.update_slot(slot_id, f"Issue #{issue_number}: Retrospective")
                with self.state_lock:
                    state.phase = ImplementationPhase.RETROSPECTIVE
                self._save_state(state)
                self._run_retrospective(state.session_id, worktree_path, issue_number)

            # Follow-up issues phase (after RETROSPECTIVE, before COMPLETED)
            if self.options.enable_follow_up and state.session_id:
                self.status_tracker.update_slot(slot_id, f"Issue #{issue_number}: Follow-up issues")
                with self.state_lock:
                    state.phase = ImplementationPhase.FOLLOW_UP_ISSUES
                self._save_state(state)
                self._run_follow_up_issues(state.session_id, worktree_path, issue_number)

            # Mark as completed
            with self.state_lock:
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

    def _parse_follow_up_items(self, text: str) -> list[dict]:
        """Parse follow-up items from Claude's JSON response.

        Args:
            text: Claude's response text (may contain JSON in code blocks)

        Returns:
            List of follow-up item dictionaries with title, body, labels

        """
        # Try to extract JSON from code blocks or bare JSON
        json_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find bare JSON array
            json_match = re.search(r"(\[.*\])", text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                logger.warning("No JSON array found in follow-up response")
                return []

        try:
            items = json.loads(json_str)
            if not isinstance(items, list):
                logger.warning("Follow-up response is not a JSON array")
                return []

            # Validate and filter items
            valid_items = []
            for item in items[:5]:  # Cap at 5
                if not isinstance(item, dict):
                    continue
                if "title" not in item or "body" not in item:
                    logger.warning(f"Skipping follow-up item missing required fields: {item}")
                    continue

                # Ensure labels is a list
                if "labels" not in item:
                    item["labels"] = []
                elif not isinstance(item["labels"], list):
                    item["labels"] = []

                valid_items.append(item)

            return valid_items

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse follow-up JSON: {e}")
            return []

    def _run_follow_up_issues(
        self, session_id: str, worktree_path: Path, issue_number: int
    ) -> None:
        """Resume Claude session to identify and file follow-up issues.

        Args:
            session_id: Claude session ID to resume
            worktree_path: Path to git worktree
            issue_number: Parent issue number

        """
        # Write follow-up prompt to temp file in worktree
        prompt_file = worktree_path / f".claude-followup-{issue_number}.md"
        prompt_file.write_text(get_follow_up_prompt(issue_number))

        try:
            # Resume session and get follow-up items
            result = run(
                [
                    "claude",
                    "--resume",
                    session_id,
                    str(prompt_file),
                    "--output-format",
                    "json",
                ],
                cwd=worktree_path,
                timeout=600,  # 10 minutes
            )

            # Parse JSON output
            try:
                data = json.loads(result.stdout)
                response_text = data.get("result", "")
            except (json.JSONDecodeError, AttributeError) as e:
                logger.warning(f"Could not parse follow-up response for issue #{issue_number}: {e}")
                return

            # Extract follow-up items
            items = self._parse_follow_up_items(response_text)

            if not items:
                logger.info(f"No follow-up items identified for issue #{issue_number}")
                return

            # Create follow-up issues
            created_issues = []
            for item in items:
                try:
                    # Append reference to parent issue
                    body_with_ref = f"{item['body']}\n\n_Follow-up from #{issue_number}_"

                    # Create issue with labels
                    new_issue_num = gh_issue_create(
                        title=item["title"],
                        body=body_with_ref,
                        labels=item.get("labels"),
                    )
                    created_issues.append(new_issue_num)

                    # Rate limit: sleep between creates
                    time.sleep(1)

                except Exception as e:
                    logger.warning(f"Failed to create follow-up issue '{item['title']}': {e}")
                    # Continue with remaining items

            # Post summary comment on parent issue
            if created_issues:
                summary = f"Created {len(created_issues)} follow-up issue(s): " + ", ".join(
                    f"#{num}" for num in created_issues
                )
                try:
                    gh_issue_comment(issue_number, summary)
                    logger.info(f"Posted follow-up summary to issue #{issue_number}")
                except Exception as e:
                    logger.warning(f"Failed to post follow-up summary: {e}")

            logger.info(
                f"Follow-up issues completed for #{issue_number}: created {len(created_issues)}"
            )

        except Exception as e:
            logger.warning(f"Follow-up issues failed for issue #{issue_number}: {e}")
            # Non-blocking: never re-raise
        finally:
            # Clean up temp file
            try:
                prompt_file.unlink()
            except Exception:
                pass  # Best effort cleanup

    def _run_retrospective(self, session_id: str, worktree_path: Path, issue_number: int) -> None:
        """Resume Claude session to run /retrospective.

        Runs from repo root so ProjectMnemosyne clone persists in build/.
        Output is logged to .issue_implementer/retrospective-{issue_number}.log.
        """
        log_file = self.state_dir / f"retrospective-{issue_number}.log"
        try:
            result = run(
                [
                    "claude",
                    "--resume",
                    session_id,
                    "/skills-registry-commands:retrospective commit the results and create a PR",
                    "--print",
                    "--permission-mode",
                    "dontAsk",
                    "--allowedTools",
                    "Read,Write,Edit,Glob,Grep,Bash",
                ],
                cwd=self.repo_root,
                timeout=600,  # 10 minutes
            )
            # Write output to log file
            log_file.write_text(result.stdout or "")
            logger.info(f"Retrospective completed for issue #{issue_number}")
            logger.info(f"Retrospective log: {log_file}")
        except Exception as e:
            logger.warning(f"Retrospective failed for issue #{issue_number}: {e}")
            # Non-blocking: never re-raise

    def _run_claude_code(self, issue_number: int, worktree_path: Path, prompt: str) -> str | None:
        """Run Claude Code in a worktree.

        Returns:
            Session ID if captured, None otherwise

        """
        if self.options.dry_run:
            logger.info(f"[DRY RUN] Would run Claude Code for issue #{issue_number}")
            return None

        # Write prompt to temp file in worktree
        prompt_file = worktree_path / f".claude-prompt-{issue_number}.md"
        prompt_file.write_text(prompt)

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
            # Parse session_id from JSON output
            try:
                data = json.loads(result.stdout)
                return data.get("session_id")
            except (json.JSONDecodeError, AttributeError):
                logger.warning(f"Could not parse session_id for issue #{issue_number}")
                logger.debug(f"Claude stdout: {result.stdout[:500]}")
                return None
        except subprocess.CalledProcessError as e:
            logger.error(f"Claude Code failed for issue #{issue_number}")
            logger.error(f"Exit code: {e.returncode}")
            if e.stdout:
                logger.error(f"Stdout: {e.stdout[:1000]}")
            if e.stderr:
                logger.error(f"Stderr: {e.stderr[:1000]}")
            raise RuntimeError(f"Claude Code failed: {e.stderr or e.stdout}") from e
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("Claude Code timed out") from e
        finally:
            # Clean up temp file
            try:
                prompt_file.unlink()
            except Exception:
                pass  # Best effort cleanup

    def _commit_changes(self, issue_number: int, worktree_path: Path) -> None:
        """Commit changes in worktree."""
        # Check if there are changes
        result = run(
            ["git", "status", "--porcelain"],
            cwd=worktree_path,
            capture_output=True,
        )

        if not result.stdout.strip():
            raise RuntimeError(
                f"No changes to commit for issue #{issue_number}. "
                "Check if the implementation was successful or if the plan needs revision."
            )

        # Parse git status --porcelain output to get all changed files
        # Format: XY filename or XY "quoted filename" for special chars
        # X = index status, Y = worktree status
        # Common codes: M (modified), A (added), D (deleted), R (renamed), ?? (untracked)
        files_to_add = []
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

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            # Parse status code and filename
            # Format: "XY filename" where X and Y are status codes
            # Position 0-1: status codes, position 2: space, position 3+: filename
            status = line[:2]
            filename_part = line[3:]  # Don't strip - filename starts at position 3

            # Handle renamed files (format: "old -> new")
            if status.startswith("R"):
                # For renames, only stage the new name (after ->)
                if " -> " in filename_part:
                    filename_part = filename_part.split(" -> ", 1)[1]

            # Handle quoted filenames (git quotes names with special chars)
            if filename_part.startswith('"') and filename_part.endswith('"'):
                # Remove quotes - git uses C-style escaping
                filename_part = filename_part[1:-1]

            # Check if file is a potential secret
            from pathlib import Path

            filename = Path(filename_part).name

            # Skip secret files (never stage these)
            if filename in secret_files or any(filename.endswith(ext) for ext in secret_extensions):
                logger.warning(f"Skipping potential secret file: {filename_part}")
                continue

            files_to_add.append(filename_part)

        if not files_to_add:
            raise RuntimeError(
                f"No non-secret files to commit for issue #{issue_number}. "
                "All changes appear to be secret files."
            )

        # Stage the files
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

    def _ensure_pr_created(self, issue_number: int, branch_name: str, worktree_path: Path) -> int:
        """Ensure commit is pushed and PR is created (fallback if Claude didn't do it).

        Returns:
            PR number

        Raises:
            RuntimeError: If commit doesn't exist or PR creation fails

        """
        # Check if commit exists
        result = run(
            ["git", "log", "-1", "--oneline"],
            cwd=worktree_path,
            capture_output=True,
        )
        if not result.stdout.strip():
            raise RuntimeError(
                f"No commit found for issue #{issue_number}. Claude did not create any commits."
            )

        logger.info(f"✓ Commit exists: {result.stdout.strip()[:80]}")

        # Check if branch was pushed, if not push it
        result = run(
            ["git", "ls-remote", "--heads", "origin", branch_name],
            cwd=worktree_path,
            capture_output=True,
            check=False,
        )
        if not result.stdout.strip():
            logger.warning(f"Branch {branch_name} not pushed, pushing now...")
            run(["git", "push", "-u", "origin", branch_name], cwd=worktree_path)
            logger.info(f"✓ Pushed branch {branch_name} to origin")
        else:
            logger.info(f"✓ Branch {branch_name} already on origin")

        # Check if PR exists, if not create it
        import json

        from .github_api import _gh_call

        pr_number = None
        try:
            result = _gh_call(
                ["pr", "list", "--head", branch_name, "--json", "number", "--limit", "1"]
            )
            pr_data = json.loads(result.stdout)
            if pr_data and len(pr_data) > 0:
                pr_number = pr_data[0]["number"]
                logger.info(f"✓ PR #{pr_number} already exists")
                return pr_number
        except Exception as e:
            logger.debug(f"Could not find existing PR: {e}")

        # PR doesn't exist, create it
        logger.warning(f"No PR found for branch {branch_name}, creating one...")
        pr_number = self._create_pr(issue_number, branch_name)
        logger.info(f"✓ Created PR #{pr_number}")
        return pr_number

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
