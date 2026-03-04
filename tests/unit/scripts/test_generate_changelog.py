"""Tests for scripts/generate_changelog.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from generate_changelog import (
    categorize_commits,
    generate_changelog,
    get_commits_between,
    get_latest_tag,
    get_previous_tag,
    parse_commit,
    run_git_command,
)


# ---------------------------------------------------------------------------
# parse_commit
# ---------------------------------------------------------------------------


class TestParseCommit:
    """Tests for parse_commit()."""

    def test_conventional_commit_with_scope(self) -> None:
        """Parses type(scope): message format correctly."""
        h, t, s, m = parse_commit("abc1234|feat(metrics): Add CoP calculation|Author")
        assert h == "abc1234"
        assert t == "feat"
        assert s == "metrics"
        assert m == "Add CoP calculation"

    def test_conventional_commit_without_scope(self) -> None:
        """Parses type: message format (no scope)."""
        h, t, s, m = parse_commit("abc1234|fix: Correct typo|Author")
        assert h == "abc1234"
        assert t == "fix"
        assert s == ""
        assert m == "Correct typo"

    def test_non_conventional_commit(self) -> None:
        """Non-conventional commits default to 'other' type."""
        h, t, s, m = parse_commit("abc1234|Some free-form message|Author")
        assert t == "other"
        assert s == ""
        assert m == "Some free-form message"

    def test_malformed_line_returns_other(self) -> None:
        """Lines without proper format return empty hash and 'other' type."""
        h, t, s, m = parse_commit("malformed-no-pipes")
        assert h == ""
        assert t == "other"

    def test_commit_type_lowercased(self) -> None:
        """Commit types are normalized to lowercase."""
        _, t, _, _ = parse_commit("abc|FEAT(scope): something|Author")
        assert t == "feat"

    def test_message_stripped(self) -> None:
        """Message is stripped of leading/trailing whitespace."""
        _, _, _, m = parse_commit("abc|feat(scope):   leading spaces  |Author")
        assert m == "leading spaces"

    @pytest.mark.parametrize(
        "commit_type,expected",
        [
            ("feat", "feat"),
            ("fix", "fix"),
            ("docs", "docs"),
            ("refactor", "refactor"),
            ("test", "test"),
            ("ci", "ci"),
            ("chore", "chore"),
        ],
    )
    def test_various_commit_types(self, commit_type: str, expected: str) -> None:
        """Parses all standard conventional commit types."""
        _, t, _, _ = parse_commit(f"abc|{commit_type}: message|Author")
        assert t == expected


# ---------------------------------------------------------------------------
# categorize_commits
# ---------------------------------------------------------------------------


class TestCategorizeCommits:
    """Tests for categorize_commits()."""

    def test_feat_maps_to_features(self) -> None:
        """feat commits go into Features category."""
        result = categorize_commits(["abc|feat(core): Add feature|Author"])
        assert "Features" in result

    def test_fix_maps_to_bug_fixes(self) -> None:
        """fix commits go into Bug Fixes category."""
        result = categorize_commits(["abc|fix: Fix bug|Author"])
        assert "Bug Fixes" in result

    def test_unknown_type_maps_to_other(self) -> None:
        """Unknown commit types are placed in Other."""
        result = categorize_commits(["abc|xyz: Something|Author"])
        assert "Other" in result

    def test_empty_lines_skipped(self) -> None:
        """Empty lines in commit list are ignored."""
        result = categorize_commits(["", "  ", "abc|feat: something|Author"])
        total = sum(len(v) for v in result.values())
        assert total == 1

    def test_multiple_commits_grouped(self) -> None:
        """Multiple commits of same type are grouped together."""
        commits = [
            "abc|feat: First|Author",
            "def|feat: Second|Author",
        ]
        result = categorize_commits(commits)
        assert len(result["Features"]) == 2

    def test_result_contains_hash_scope_message(self) -> None:
        """Each entry is (hash, scope, message) tuple."""
        result = categorize_commits(["abc1234|feat(scope): msg|Author"])
        entry = result["Features"][0]
        assert entry == ("abc1234", "scope", "msg")

    @pytest.mark.parametrize(
        "commit_type,category",
        [
            ("feat", "Features"),
            ("fix", "Bug Fixes"),
            ("perf", "Performance"),
            ("docs", "Documentation"),
            ("refactor", "Refactoring"),
            ("test", "Testing"),
            ("ci", "CI/CD"),
            ("chore", "Maintenance"),
            ("build", "Build"),
            ("style", "Style"),
        ],
    )
    def test_type_to_category_mapping(self, commit_type: str, category: str) -> None:
        """All standard commit types map to expected categories."""
        result = categorize_commits([f"abc|{commit_type}: msg|Author"])
        assert category in result


# ---------------------------------------------------------------------------
# run_git_command / get_latest_tag / get_previous_tag / get_commits_between
# ---------------------------------------------------------------------------


class TestRunGitCommand:
    """Tests for run_git_command()."""

    def test_returns_stdout_on_success(self) -> None:
        """Returns stripped stdout when returncode is 0."""
        with patch("generate_changelog.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "  v1.0.0\n"
            result = run_git_command(["describe", "--tags"])
        assert result == "v1.0.0"

    def test_returns_empty_string_on_failure(self) -> None:
        """Returns empty string when returncode is non-zero."""
        with patch("generate_changelog.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            result = run_git_command(["describe", "--tags"])
        assert result == ""


class TestGetLatestTag:
    """Tests for get_latest_tag()."""

    def test_returns_tag_when_found(self) -> None:
        """Returns tag string when git describe succeeds."""
        with patch("generate_changelog.run_git_command", return_value="v1.2.3"):
            result = get_latest_tag()
        assert result == "v1.2.3"

    def test_returns_none_when_no_tag(self) -> None:
        """Returns None when no tag is found."""
        with patch("generate_changelog.run_git_command", return_value=""):
            result = get_latest_tag()
        assert result is None


class TestGetPreviousTag:
    """Tests for get_previous_tag()."""

    def test_returns_previous_tag(self) -> None:
        """Returns previous tag when found."""
        with patch("generate_changelog.run_git_command", return_value="v1.1.0"):
            result = get_previous_tag("v1.2.0")
        assert result == "v1.1.0"

    def test_returns_none_when_no_previous(self) -> None:
        """Returns None when no previous tag exists."""
        with patch("generate_changelog.run_git_command", return_value=""):
            result = get_previous_tag("v1.0.0")
        assert result is None


class TestGetCommitsBetween:
    """Tests for get_commits_between()."""

    def test_returns_commit_lines(self) -> None:
        """Returns list of commit lines."""
        output = "abc|feat: A|Author\ndef|fix: B|Author"
        with patch("generate_changelog.run_git_command", return_value=output):
            result = get_commits_between("v1.0.0", "HEAD")
        assert len(result) == 2

    def test_returns_empty_list_when_no_output(self) -> None:
        """Returns empty list when no commits found."""
        with patch("generate_changelog.run_git_command", return_value=""):
            result = get_commits_between("v1.0.0")
        assert result == []

    def test_from_ref_none_uses_full_history(self) -> None:
        """When from_ref is None, uses just to_ref (full history)."""
        with patch("generate_changelog.run_git_command", return_value="") as mock:
            get_commits_between(None, "HEAD")
            # Verify the range spec doesn't include ".." prefix when from_ref is None
            call_args = mock.call_args[0][0]
            range_arg = call_args[1]  # second element after "log"
            assert ".." not in range_arg or range_arg == "HEAD"


# ---------------------------------------------------------------------------
# generate_changelog
# ---------------------------------------------------------------------------


class TestGenerateChangelog:
    """Tests for generate_changelog()."""

    def test_header_contains_version(self) -> None:
        """Changelog header includes the version string."""
        with patch("generate_changelog.get_commits_between", return_value=[]):
            result = generate_changelog("v2.0.0")
        assert "v2.0.0" in result

    def test_no_commits_message(self) -> None:
        """Shows 'No changes recorded' when commit list is empty."""
        with patch("generate_changelog.get_commits_between", return_value=[]):
            result = generate_changelog("v2.0.0", from_ref="v1.0.0")
        assert "No changes recorded" in result

    def test_features_section_present(self) -> None:
        """Features section is included when feat commits exist."""
        commits = ["abc1234|feat(core): New feature|Author"]
        with patch("generate_changelog.get_commits_between", return_value=commits):
            result = generate_changelog("v2.0.0", from_ref="v1.0.0")
        assert "## Features" in result

    def test_commit_hash_in_output(self) -> None:
        """Commit hash appears in changelog output."""
        commits = ["abc1234|feat: Something|Author"]
        with patch("generate_changelog.get_commits_between", return_value=commits):
            result = generate_changelog("v2.0.0", from_ref="v1.0.0")
        assert "abc1234" in result

    def test_scope_in_output(self) -> None:
        """Commit scope appears in bold in changelog output."""
        commits = ["abc1234|feat(metrics): CoP added|Author"]
        with patch("generate_changelog.get_commits_between", return_value=commits):
            result = generate_changelog("v2.0.0", from_ref="v1.0.0")
        assert "**metrics**" in result

    def test_total_commits_count(self) -> None:
        """Total commits count appears in changelog."""
        commits = [
            "abc|feat: A|Author",
            "def|fix: B|Author",
        ]
        with patch("generate_changelog.get_commits_between", return_value=commits):
            result = generate_changelog("v2.0.0", from_ref="v1.0.0")
        assert "Total commits" in result
        assert "2" in result

    def test_compare_link_shown(self) -> None:
        """Compare link appears when from_ref is provided."""
        with patch("generate_changelog.get_commits_between", return_value=["abc|feat: A|Author"]):
            result = generate_changelog("v2.0.0", from_ref="v1.0.0")
        assert "v1.0.0...HEAD" in result or "v1.0.0" in result
