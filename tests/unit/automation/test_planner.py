"""Tests for the Planner automation."""

import subprocess
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scylla.automation.models import PlannerOptions
from scylla.automation.planner import Planner


@pytest.fixture
def mock_options() -> None:
    """Create mock PlannerOptions."""
    return PlannerOptions(
        issues=[123],
        dry_run=False,
        force=False,
        parallel=1,
        system_prompt_file=None,
        skip_closed=True,
        enable_advise=True,
    )


@pytest.fixture
def planner(mock_options):
    """Create a Planner instance."""
    return Planner(mock_options)


class TestCallClaude:
    """Tests for _call_claude method."""

    def test_successful_call(self, planner) -> None:
        """Test successful Claude call."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="This is a plan", returncode=0)

            result = planner._call_claude("Test prompt")

            assert result == "This is a plan"
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "claude"
            assert args[1] == "--print"
            assert args[2] == "Test prompt"
            assert "--output-format" in args
            assert "text" in args

    def test_empty_response(self, planner) -> None:
        """Test handling of empty response."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="   ", returncode=0)

            with pytest.raises(RuntimeError, match="empty response"):
                planner._call_claude("Test prompt")

    def test_timeout(self, planner) -> None:
        """Test timeout handling."""
        import subprocess

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("claude", 300)

            with pytest.raises(RuntimeError, match="timed out"):
                planner._call_claude("Test prompt", timeout=300)

    def test_rate_limit_retry(self, planner) -> None:
        """Test rate limit retry logic."""
        import subprocess

        with (
            patch("subprocess.run") as mock_run,
            patch("scylla.automation.planner.detect_rate_limit") as mock_detect,
        ):
            # First call fails with rate limit, second succeeds
            mock_run.side_effect = [
                subprocess.CalledProcessError(1, "claude", stderr="rate limit exceeded"),
                MagicMock(stdout="Success", returncode=0),
            ]

            # First detect returns rate limit, then no rate limit
            mock_detect.side_effect = [(True, 0), (False, 0)]

            with patch("time.sleep"):  # Don't actually sleep
                result = planner._call_claude("Test prompt", max_retries=3)

            assert result == "Success"
            assert mock_run.call_count == 2

    def test_system_prompt_passthrough(self, mock_options) -> None:
        """Test system prompt file is passed through."""
        mock_options.system_prompt_file = Path("/tmp/system.md")

        # Create the file so exists() returns True
        with patch.object(Path, "exists", return_value=True):
            planner = Planner(mock_options)

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="Response", returncode=0)

                planner._call_claude("Test prompt")

                args = mock_run.call_args[0][0]
                assert "--system-prompt" in args
                assert str(mock_options.system_prompt_file) in args


class TestRunAdvise:
    """Tests for _run_advise method."""

    def test_returns_findings(self, planner) -> None:
        """Test successful advise returns findings."""
        with (
            patch("scylla.automation.planner.get_repo_root") as mock_get_repo,
            patch.object(Path, "exists", return_value=True),
        ):
            mock_get_repo.return_value = Path("/repo")

            with patch.object(
                planner, "_call_claude", return_value="## Related Skills\nFound 3 skills"
            ):
                result = planner._run_advise(123, "Test Issue", "Issue body")

                assert "Related Skills" in result
                assert "Found 3 skills" in result

    def test_graceful_failure_on_error(self, planner) -> None:
        """Test graceful failure when advise errors."""
        with patch("scylla.automation.planner.get_repo_root") as mock_get_repo:
            mock_get_repo.side_effect = RuntimeError("Git error")

            result = planner._run_advise(123, "Test Issue", "Issue body")

            assert result == ""

    def test_skips_when_mnemosyne_missing_and_clone_fails(self, planner) -> None:
        """Test returns empty string when ProjectMnemosyne is missing and clone fails."""
        with (
            patch("scylla.automation.planner.get_repo_root") as mock_get_repo,
            patch.object(planner, "_ensure_mnemosyne", return_value=False) as mock_ensure,
        ):
            mock_get_repo.return_value = Path("/repo")

            with patch.object(Path, "exists", return_value=False):
                result = planner._run_advise(123, "Test Issue", "Issue body")

            assert result == ""
            mock_ensure.assert_called_once()

    def test_clones_mnemosyne_when_missing(self, planner) -> None:
        """Test proceeds with advise after cloning ProjectMnemosyne."""
        call_count = [0]

        def patched_exists(p: Path) -> bool:
            call_count[0] += 1
            # First call: mnemosyne_root.exists() -> False (triggers _ensure_mnemosyne)
            # Subsequent calls (marketplace check): True
            return call_count[0] != 1

        with (
            patch("scylla.automation.planner.get_repo_root") as mock_get_repo,
            patch.object(planner, "_ensure_mnemosyne", return_value=True),
            patch.object(Path, "exists", patched_exists),
            patch.object(planner, "_call_claude", return_value="## Related Skills\nFound 2 skills"),
        ):
            mock_get_repo.return_value = Path("/repo")
            result = planner._run_advise(123, "Test Issue", "Issue body")

        assert "Related Skills" in result

    def test_marketplace_missing_triggers_reclone_and_succeeds(self, planner) -> None:
        """Test that missing marketplace.json triggers re-clone and succeeds on retry."""
        # mnemosyne_root exists but marketplace.json is absent initially.
        # After re-clone, marketplace.json becomes present.
        exists_calls: list[Path] = []

        def patched_exists(p: Path) -> bool:
            exists_calls.append(p)
            # mnemosyne_root itself always "exists" (corrupt clone scenario)
            if p.name == "ProjectMnemosyne":
                return True
            # marketplace.json: absent on first check, present after re-clone
            if p.name == "marketplace.json":
                # First time called it's absent; from the second call it's present
                return exists_calls.count(p) > 1
            return True

        with (
            patch("scylla.automation.planner.get_repo_root") as mock_get_repo,
            patch.object(Path, "exists", patched_exists),
            patch("scylla.automation.planner.shutil.rmtree") as mock_rmtree,
            patch.object(planner, "_ensure_mnemosyne", return_value=True) as mock_ensure,
            patch.object(planner, "_call_claude", return_value="## Found Skills\nSkill A"),
        ):
            mock_get_repo.return_value = Path("/repo")
            result = planner._run_advise(123, "Test Issue", "Issue body")

        mock_rmtree.assert_called_once()
        mock_ensure.assert_called_once()
        assert "Found Skills" in result

    def test_marketplace_missing_reclone_fails_returns_empty(self, planner) -> None:
        """Test that missing marketplace.json with failed re-clone returns empty string."""

        def patched_exists(p: Path) -> bool:
            # mnemosyne_root exists but marketplace.json is always absent
            if p.name == "ProjectMnemosyne":
                return True
            return p.name != "marketplace.json"

        with (
            patch("scylla.automation.planner.get_repo_root") as mock_get_repo,
            patch.object(Path, "exists", patched_exists),
            patch("scylla.automation.planner.shutil.rmtree") as mock_rmtree,
            patch.object(planner, "_ensure_mnemosyne", return_value=False) as mock_ensure,
        ):
            mock_get_repo.return_value = Path("/repo")
            result = planner._run_advise(123, "Test Issue", "Issue body")

        mock_rmtree.assert_called_once()
        mock_ensure.assert_called_once()
        assert result == ""


class TestGeneratePlan:
    """Tests for _generate_plan method."""

    def test_plan_with_advise_findings(self, planner) -> None:
        """Test plan generation with advise findings injected."""
        with (
            patch("scylla.automation.planner.gh_issue_json") as mock_gh,
            patch.object(
                planner,
                "_run_advise",
                return_value="## Related Skills\nFound skills",
            ),
            patch.object(planner, "_call_claude", return_value="# Implementation Plan\nStep 1"),
        ):
            mock_gh.return_value = {
                "title": "Test Issue",
                "body": "Issue description",
            }

            plan = planner._generate_plan(123)

            assert "Implementation Plan" in plan
            # Verify _call_claude was called with context including advise findings
            call_args = planner._call_claude.call_args[0][0]
            assert "Prior Learnings" in call_args
            assert "Related Skills" in call_args

    def test_plan_without_advise(self, mock_options) -> None:
        """Test plan generation with advise disabled."""
        mock_options.enable_advise = False
        planner = Planner(mock_options)

        with (
            patch("scylla.automation.planner.gh_issue_json") as mock_gh,
            patch.object(planner, "_run_advise") as mock_advise,
            patch.object(planner, "_call_claude", return_value="# Implementation Plan\nStep 1"),
        ):
            mock_gh.return_value = {
                "title": "Test Issue",
                "body": "Issue description",
            }

            plan = planner._generate_plan(123)

            # Advise should not be called
            mock_advise.assert_not_called()

            # Plan should still be generated
            assert "Implementation Plan" in plan


class TestEnsureMnemosyne:
    """Tests for _ensure_mnemosyne method."""

    def test_clone_success(self, planner, tmp_path) -> None:
        """Test successful clone returns True and runs correct command."""
        mnemosyne_root = tmp_path / "ProjectMnemosyne"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = planner._ensure_mnemosyne(mnemosyne_root)

        assert result is True
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "gh" in cmd
        assert "repo" in cmd
        assert "clone" in cmd
        assert "HomericIntelligence/ProjectMnemosyne" in cmd
        assert str(mnemosyne_root) in cmd

    def test_clone_failure(self, planner, tmp_path) -> None:
        """Test clone failure returns False and logs warning."""
        mnemosyne_root = tmp_path / "ProjectMnemosyne"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "gh", stderr="authentication failed"
            )

            result = planner._ensure_mnemosyne(mnemosyne_root)

        assert result is False

    def test_no_clone_if_exists(self, planner, tmp_path) -> None:
        """Test does not clone when directory already exists (runs git pull instead)."""
        mnemosyne_root = tmp_path / "ProjectMnemosyne"
        mnemosyne_root.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = planner._ensure_mnemosyne(mnemosyne_root)

        assert result is True
        # Should call git pull, not gh repo clone
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "git" in cmd
        assert "pull" in cmd
        assert "gh" not in cmd

    def test_lock_file_removed_after_successful_clone(self, planner, tmp_path) -> None:
        """Test that the lock file is removed after a successful clone."""
        mnemosyne_root = tmp_path / "ProjectMnemosyne"
        lock_path = tmp_path / ".mnemosyne.lock"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = planner._ensure_mnemosyne(mnemosyne_root)

        assert result is True
        assert not lock_path.exists(), "Lock file should be removed after successful clone"

    def test_git_pull_called_when_directory_exists(self, planner, tmp_path) -> None:
        """Test that git pull --ff-only is called when directory already exists."""
        mnemosyne_root = tmp_path / "ProjectMnemosyne"
        mnemosyne_root.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = planner._ensure_mnemosyne(mnemosyne_root)

        assert result is True
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "git" in cmd
        assert "-C" in cmd
        assert str(mnemosyne_root) in cmd
        assert "pull" in cmd
        assert "--ff-only" in cmd

    def test_git_pull_failure_logs_warning_and_returns_true(self, planner, tmp_path) -> None:
        """Test that a git pull failure logs a warning but still returns True."""
        mnemosyne_root = tmp_path / "ProjectMnemosyne"
        mnemosyne_root.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "git", stderr="not a fast-forward"
            )

            result = planner._ensure_mnemosyne(mnemosyne_root)

        assert result is True

    def test_concurrent_clone_only_once(self, mock_options, tmp_path) -> None:
        """Test concurrent calls only clone once (lock prevents double-clone)."""
        mnemosyne_root = tmp_path / "ProjectMnemosyne"

        clone_calls = []
        start_event = threading.Event()

        def fake_subprocess(cmd: list[str], **kwargs: object) -> MagicMock:
            # Only count gh repo clone calls, not git pull calls
            if "gh" in cmd and "clone" in cmd:
                clone_calls.append(1)
                # Create the directory so subsequent checks see it
                mnemosyne_root.mkdir(exist_ok=True)
            return MagicMock(returncode=0)

        planner1 = Planner(mock_options)
        planner2 = Planner(mock_options)

        results: list[bool] = []

        def worker(p: Planner) -> None:
            start_event.wait()
            results.append(p._ensure_mnemosyne(mnemosyne_root))

        t1 = threading.Thread(target=worker, args=(planner1,))
        t2 = threading.Thread(target=worker, args=(planner2,))

        with patch("subprocess.run", side_effect=fake_subprocess):
            t1.start()
            t2.start()
            start_event.set()
            t1.join()
            t2.join()

        assert all(results), "Both threads should return True"
        assert len(clone_calls) == 1, "Clone should only happen once"
