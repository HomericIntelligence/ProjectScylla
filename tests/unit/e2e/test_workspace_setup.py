"""Tests for workspace_setup._setup_workspace git worktree behavior.

Git subprocess calls are mocked (infrastructure), but the Python logic
under test is exercised directly.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scylla.e2e.models import TierID
from scylla.e2e.workspace_setup import _setup_workspace


def _ok() -> MagicMock:
    r = MagicMock()
    r.returncode = 0
    r.stdout = ""
    r.stderr = ""
    return r


def _fail(stderr: str = "fatal: error") -> MagicMock:
    r = MagicMock()
    r.returncode = 1
    r.stdout = ""
    r.stderr = stderr
    return r


class TestSetupWorkspaceProactiveCleanup:
    """Proactive prune + branch-delete before first worktree add prevents cross-test collisions."""

    def test_prune_and_branch_delete_before_worktree_add(self, tmp_path: Path) -> None:
        """Git worktree prune and branch -D are issued before worktree add."""
        workspace = tmp_path / "workspace"
        base_repo = tmp_path / "repo"
        base_repo.mkdir()

        with patch("subprocess.run", return_value=_ok()) as mock_run:
            _setup_workspace(
                workspace=workspace,
                command_logger=MagicMock(),
                tier_id=TierID.T0,
                subtest_id="00",
                run_number=1,
                base_repo=base_repo,
            )

        cmds = [c[0][0] for c in mock_run.call_args_list]
        # First: prune
        assert cmds[0] == ["git", "-C", str(base_repo), "worktree", "prune"]
        # Second: branch -D
        assert cmds[1] == ["git", "-C", str(base_repo), "branch", "-D", "T0_00_run_01"]
        # Third: worktree add
        assert "add" in cmds[2]

    def test_stale_branch_delete_failure_is_ignored(self, tmp_path: Path) -> None:
        """Branch -D returning non-zero (branch didn't exist) does not abort setup."""
        workspace = tmp_path / "workspace"
        base_repo = tmp_path / "repo"
        base_repo.mkdir()

        # prune ok, branch -D fails (branch not found), worktree add ok
        with patch("subprocess.run", side_effect=[_ok(), _fail("branch not found"), _ok()]):
            # Must not raise
            _setup_workspace(
                workspace=workspace,
                command_logger=MagicMock(),
                tier_id=TierID.T1,
                subtest_id="01",
                run_number=1,
                base_repo=base_repo,
            )

    def test_branch_name_format(self, tmp_path: Path) -> None:
        """Branch name is <TierID>_<subtest_id>_run_<NN>."""
        workspace = tmp_path / "workspace"
        base_repo = tmp_path / "repo"
        base_repo.mkdir()

        with patch("subprocess.run", return_value=_ok()) as mock_run:
            _setup_workspace(
                workspace=workspace,
                command_logger=MagicMock(),
                tier_id=TierID.T3,
                subtest_id="01",
                run_number=2,
                base_repo=base_repo,
            )

        cmds = [c[0][0] for c in mock_run.call_args_list]
        delete_cmd = next(c for c in cmds if "branch" in c and "-D" in c)
        assert "T3_01_run_02" in delete_cmd

    def test_cross_test_collision_resolved(self, tmp_path: Path) -> None:
        """Proactive delete clears stale branch so worktree add succeeds without collision.

        Simulates: prior test left T0_00_run_01 branch; branch -D removes it;
        worktree add succeeds on first attempt (no reactive recovery needed).
        """
        workspace = tmp_path / "workspace"
        base_repo = tmp_path / "repo"
        base_repo.mkdir()

        # prune ok, branch -D ok (clears stale branch), worktree add ok
        with patch("subprocess.run", side_effect=[_ok(), _ok(), _ok()]) as mock_run:
            _setup_workspace(
                workspace=workspace,
                command_logger=MagicMock(),
                tier_id=TierID.T0,
                subtest_id="00",
                run_number=1,
                base_repo=base_repo,
            )

        # Exactly 3 calls: prune, branch -D, worktree add
        assert mock_run.call_count == 3


class TestSetupWorkspaceResumeRecovery:
    """Reactive recovery path for genuine resume scenarios still works."""

    def test_non_collision_failure_raises(self, tmp_path: Path) -> None:
        """A worktree add failure unrelated to branch collision raises RuntimeError."""
        workspace = tmp_path / "workspace"
        base_repo = tmp_path / "repo"
        base_repo.mkdir()

        with (
            patch(
                "subprocess.run",
                side_effect=[_ok(), _ok(), _fail("fatal: some other git error")],
            ),
            pytest.raises(RuntimeError, match="Failed to create worktree"),
        ):
            _setup_workspace(
                workspace=workspace,
                command_logger=MagicMock(),
                tier_id=TierID.T0,
                subtest_id="00",
                run_number=1,
                base_repo=base_repo,
            )

    def test_branch_already_exists_after_proactive_delete_triggers_recovery(
        self, tmp_path: Path
    ) -> None:
        """If worktree add still reports 'already exists', reactive recovery is attempted."""
        workspace = tmp_path / "workspace"
        base_repo = tmp_path / "repo"
        base_repo.mkdir()

        with patch(
            "subprocess.run",
            side_effect=[
                _ok(),  # prune (proactive)
                _ok(),  # branch -D (proactive)
                _fail("fatal: a branch named 'T0_00_run_01' already exists"),  # worktree add
                _ok(),  # recovery: prune
                _ok(),  # recovery: worktree remove
                _ok(),  # recovery: branch -D
                _ok(),  # recovery: worktree add retry
            ],
        ):
            # Recovery succeeds - no exception
            _setup_workspace(
                workspace=workspace,
                command_logger=MagicMock(),
                tier_id=TierID.T0,
                subtest_id="00",
                run_number=1,
                base_repo=base_repo,
            )

    def test_recovery_retry_failure_raises(self, tmp_path: Path) -> None:
        """If reactive recovery retry also fails, RuntimeError is raised."""
        workspace = tmp_path / "workspace"
        base_repo = tmp_path / "repo"
        base_repo.mkdir()

        with patch(
            "subprocess.run",
            side_effect=[
                _ok(),  # prune (proactive)
                _ok(),  # branch -D (proactive)
                _fail("fatal: a branch named 'T0_00_run_01' already exists"),  # worktree add
                _ok(),  # recovery: prune
                _ok(),  # recovery: worktree remove
                _ok(),  # recovery: branch -D
                _fail("fatal: still broken"),  # recovery retry fails
            ],
        ):
            with pytest.raises(RuntimeError, match="Failed to create worktree even after cleanup"):
                _setup_workspace(
                    workspace=workspace,
                    command_logger=MagicMock(),
                    tier_id=TierID.T0,
                    subtest_id="00",
                    run_number=1,
                    base_repo=base_repo,
                )


class TestMoveToFailed:
    """Tests for _move_to_failed function."""

    def test_creates_failed_dir_and_moves_run_dir(self, tmp_path: Path) -> None:
        """Verifies .failed/ dir is created and run_dir is moved into it."""
        from scylla.e2e.workspace_setup import _move_to_failed

        run_dir = tmp_path / "run_01"
        run_dir.mkdir()

        _move_to_failed(run_dir)

        failed_dir = tmp_path / ".failed"
        assert failed_dir.is_dir()
        assert not run_dir.exists()
        assert any(failed_dir.iterdir())

    def test_returns_correct_path(self, tmp_path: Path) -> None:
        """Verifies the returned path is the new location inside .failed/."""
        from scylla.e2e.workspace_setup import _move_to_failed

        run_dir = tmp_path / "run_03"
        run_dir.mkdir()

        new_path = _move_to_failed(run_dir, attempt=1)

        assert new_path == tmp_path / ".failed" / "run_03_attempt_01"
        assert new_path.exists()

    def test_increments_attempt_number(self, tmp_path: Path) -> None:
        """If .failed/run_dir_attempt_01 exists, creates .failed/run_dir_attempt_02."""
        from scylla.e2e.workspace_setup import _move_to_failed

        failed_dir = tmp_path / ".failed"
        failed_dir.mkdir()
        # Pre-create attempt_01 to force increment
        (failed_dir / "run_01_attempt_01").mkdir()

        run_dir = tmp_path / "run_01"
        run_dir.mkdir()

        new_path = _move_to_failed(run_dir, attempt=1)

        assert new_path == failed_dir / "run_01_attempt_02"
        assert new_path.exists()

    def test_handles_first_attempt(self, tmp_path: Path) -> None:
        """Normal case: no existing failed dirs; attempt_01 is created directly."""
        from scylla.e2e.workspace_setup import _move_to_failed

        run_dir = tmp_path / "run_05"
        run_dir.mkdir()

        new_path = _move_to_failed(run_dir)

        assert new_path.name == "run_05_attempt_01"
        assert new_path.exists()
        assert not run_dir.exists()


class TestCommitTestConfig:
    """Tests for _commit_test_config function."""

    def test_stages_claude_md_when_exists(self, tmp_path: Path) -> None:
        """When CLAUDE.md exists, subprocess.run is called with git add CLAUDE.md."""
        from scylla.e2e.workspace_setup import _commit_test_config

        (tmp_path / "CLAUDE.md").write_text("# test")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _ok()
            _commit_test_config(tmp_path)

        staged_cmds = [c[0][0] for c in mock_run.call_args_list]
        assert ["git", "add", "CLAUDE.md"] in staged_cmds

    def test_stages_dot_claude_when_exists(self, tmp_path: Path) -> None:
        """When .claude/ exists, subprocess.run is called with git add .claude/."""
        from scylla.e2e.workspace_setup import _commit_test_config

        (tmp_path / ".claude").mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _ok()
            _commit_test_config(tmp_path)

        staged_cmds = [c[0][0] for c in mock_run.call_args_list]
        assert ["git", "add", ".claude/"] in staged_cmds

    def test_skips_absent_files(self, tmp_path: Path) -> None:
        """When neither CLAUDE.md nor .claude/ exist, git add is NOT called."""
        from scylla.e2e.workspace_setup import _commit_test_config

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _ok()
            _commit_test_config(tmp_path)

        all_cmds = [c[0][0] for c in mock_run.call_args_list]
        assert ["git", "add", "CLAUDE.md"] not in all_cmds
        assert ["git", "add", ".claude/"] not in all_cmds

    def test_commits_only_if_staged_changes(self, tmp_path: Path) -> None:
        """Only commits when there are staged changes (git diff --cached returns non-zero)."""
        from scylla.e2e.workspace_setup import _commit_test_config

        # Simulate no staged changes: diff --cached returns 0
        no_staged = _ok()
        no_staged.returncode = 0

        with patch("subprocess.run", return_value=no_staged) as mock_run:
            _commit_test_config(tmp_path)

        all_cmds = [c[0][0] for c in mock_run.call_args_list]
        commit_cmds = [c for c in all_cmds if "commit" in c]
        assert commit_cmds == [], "Should not commit when there are no staged changes"
