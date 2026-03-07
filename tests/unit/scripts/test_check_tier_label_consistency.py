"""Tests for scripts/check_tier_label_consistency.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from check_tier_label_consistency import (
    BAD_PATTERNS,
    TierLabelFinding,
    _collect_mismatches,
    check_tier_label_consistency,
    find_violations,
    format_json,
    format_report,
    scan_repository,
)


class TestFindViolations:
    """Tests for find_violations() — legacy API."""

    def test_returns_empty_for_clean_content(self) -> None:
        """Clean content with no bad patterns returns no violations."""
        content = "T2 Tooling\nT3 Delegation\nT4 Hierarchy\nT5 Hybrid\n"
        assert find_violations(content) == []

    @pytest.mark.parametrize(
        "bad_line, expected_pattern",
        [
            # Original set
            ("T3 Tooling tier", r"T3.*Tool"),
            ("T4 Delegation tier", r"T4.*Deleg"),
            ("T5 Hierarchy tier", r"T5.*Hier"),
            ("T2 Skills tier", r"T2.*Skill"),
            # Reverse/symmetric set
            ("T2 Delegation tier", r"T2.{0,10}Deleg"),
            ("T3 Hierarchy tier", r"T3.{0,10}Hier"),
            ("T4 Hybrid tier", r"T4.{0,10}Hybrid"),
            ("T1 Tooling tier", r"T1.{0,10}Tool"),
            ("T0 Skills tier", r"T0.{0,10}Skill"),
            ("T1 Prompts tier", r"T1.{0,10}Prompt"),
            ("T2 Prompts tier", r"T2.{0,10}Prompt"),
            ("T3 Skills tier", r"T3.{0,10}Skill"),
            ("T4 Tooling tier", r"T4.{0,10}Tool"),
            ("T5 Delegation tier", r"T5.{0,10}Deleg"),
            ("T6 Hierarchy tier", r"T6.{0,10}Hier"),
            ("T6 Hybrid tier", r"T6.{0,10}Hybrid"),
            ("T0 Tooling tier", r"T0.{0,10}Tool"),
            ("T0 Delegation tier", r"T0.{0,10}Deleg"),
            ("T5 Skills tier", r"T5.{0,10}Skill"),
            ("T6 Delegation tier", r"T6.{0,10}Deleg"),
        ],
    )
    def test_detects_each_bad_pattern(self, bad_line: str, expected_pattern: str) -> None:
        """Each known-bad pattern is detected."""
        violations = find_violations(bad_line)
        assert len(violations) == 1
        lineno, line, pattern, reason = violations[0]
        assert lineno == 1
        assert line == bad_line
        assert pattern == expected_pattern
        assert reason  # non-empty reason string

    def test_returns_line_number(self) -> None:
        """Violation includes the correct 1-based line number."""
        content = "clean line\nT3 Tooling bad\nclean line"
        violations = find_violations(content)
        assert len(violations) == 1
        assert violations[0][0] == 2

    def test_multiple_violations_on_different_lines(self) -> None:
        """Multiple bad lines produce multiple violations."""
        content = "T3 Tooling\nT4 Delegation\n"
        violations = find_violations(content)
        assert len(violations) == 2

    def test_single_line_matching_multiple_patterns(self) -> None:
        """A line matching multiple patterns produces one violation per pattern."""
        content = "T3 Tooling T4 Delegation"
        violations = find_violations(content)
        assert len(violations) == 2

    def test_empty_content_returns_no_violations(self) -> None:
        """Empty string produces no violations."""
        assert find_violations("") == []

    def test_correct_tier_names_not_flagged(self) -> None:
        """Correct tier names adjacent to tier numbers are not flagged."""
        content = (
            "T0 Prompts\nT1 Skills\nT2 Tooling\nT3 Delegation\nT4 Hierarchy\nT5 Hybrid\nT6 Super\n"
        )
        assert find_violations(content) == []

    def test_violation_tuple_has_four_elements(self) -> None:
        """Each violation tuple contains (lineno, line, pattern, reason)."""
        violations = find_violations("T3 Tooling")
        assert len(violations) == 1
        assert len(violations[0]) == 4


class TestCheckTierLabelConsistency:
    """Tests for check_tier_label_consistency() — legacy single-file API."""

    def test_clean_file_returns_zero(self, tmp_path: Path) -> None:
        """File with no bad patterns returns exit code 0."""
        f = tmp_path / "metrics-definitions.md"
        f.write_text("T3 Delegation\nT4 Hierarchy\n", encoding="utf-8")
        assert check_tier_label_consistency(f) == 0

    def test_violation_returns_one(self, tmp_path: Path) -> None:
        """File with a bad pattern returns exit code 1."""
        f = tmp_path / "metrics-definitions.md"
        f.write_text("T3 Tooling tier\n", encoding="utf-8")
        assert check_tier_label_consistency(f) == 1

    def test_missing_file_returns_one(self, tmp_path: Path) -> None:
        """Non-existent file returns exit code 1."""
        missing = tmp_path / "nonexistent.md"
        assert check_tier_label_consistency(missing) == 1

    def test_missing_file_prints_error_to_stderr(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Error message for missing file is printed to stderr."""
        missing = tmp_path / "nonexistent.md"
        check_tier_label_consistency(missing)
        captured = capsys.readouterr()
        assert "not found" in captured.err.lower() or "nonexistent.md" in captured.err

    def test_violation_details_printed_to_stderr(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Violation line and pattern are printed to stderr."""
        f = tmp_path / "metrics-definitions.md"
        f.write_text("T4 Delegation mismatched\n", encoding="utf-8")
        check_tier_label_consistency(f)
        captured = capsys.readouterr()
        assert "T4" in captured.err
        assert "Deleg" in captured.err

    def test_violation_count_in_error_message(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Error message reports the number of violations."""
        f = tmp_path / "metrics-definitions.md"
        f.write_text("T3 Tooling\nT5 Hierarchy\n", encoding="utf-8")
        check_tier_label_consistency(f)
        captured = capsys.readouterr()
        assert "2" in captured.err

    @pytest.mark.parametrize(
        "bad_line",
        [
            # Original set
            "T3 Tooling",
            "T4 Delegation",
            "T5 Hierarchy",
            "T2 Skills",
            # Reverse/symmetric set
            "T2 Delegation",
            "T3 Hierarchy",
            "T4 Hybrid",
            "T1 Tooling",
            "T0 Skills",
            "T1 Prompts",
            "T2 Prompts",
            "T3 Skills",
            "T4 Tooling",
            "T5 Delegation",
            "T6 Hierarchy",
            "T6 Hybrid",
            "T0 Tooling",
            "T0 Delegation",
            "T5 Skills",
            "T6 Delegation",
        ],
    )
    def test_each_bad_pattern_causes_failure(self, tmp_path: Path, bad_line: str) -> None:
        """Each individual bad pattern triggers a failure."""
        f = tmp_path / "metrics-definitions.md"
        f.write_text(bad_line + "\n", encoding="utf-8")
        assert check_tier_label_consistency(f) == 1

    def test_actual_metrics_definitions_file_is_clean(self) -> None:
        """The real metrics-definitions.md file has no tier label mismatches."""
        target = Path(".claude/shared/metrics-definitions.md")
        if not target.is_file():
            pytest.skip("metrics-definitions.md not found (not in repo root context)")
        assert check_tier_label_consistency(target) == 0


class TestBadPatterns:
    """Tests for the BAD_PATTERNS constant."""

    def test_bad_patterns_is_non_empty(self) -> None:
        """BAD_PATTERNS must contain at least one entry."""
        assert len(BAD_PATTERNS) > 0

    def test_bad_patterns_entries_are_tuples_of_two_strings(self) -> None:
        """Each entry in BAD_PATTERNS is a (pattern, reason) tuple of strings."""
        for pattern, reason in BAD_PATTERNS:
            assert isinstance(pattern, str)
            assert isinstance(reason, str)
            assert pattern
            assert reason


class TestCollectMismatches:
    """Tests for _collect_mismatches() — new per-file scan API."""

    @pytest.mark.parametrize(
        "bad_line, expected_tier, expected_found",
        [
            ("T3/Tooling is multi-agent", "T3", "Tooling"),
            ("T4/Delegation results", "T4", "Delegation"),
            ("T5/Hierarchy is nested", "T5", "Hierarchy"),
            ("T2/Skills is domain", "T2", "Skills"),
        ],
    )
    def test_detects_mismatch(
        self,
        tmp_path: Path,
        bad_line: str,
        expected_tier: str,
        expected_found: str,
    ) -> None:
        """Each mismatch pattern is detected with correct tier and found name."""
        f = tmp_path / "test.md"
        f.write_text(bad_line + "\n", encoding="utf-8")
        findings = _collect_mismatches(f)
        assert len(findings) == 1
        assert findings[0].tier == expected_tier
        assert findings[0].found_name.lower() == expected_found.lower()

    @pytest.mark.parametrize(
        "clean_line",
        [
            "T3/Delegation is multi-agent",
            "T2/Tooling has 15 sub-tests",
            "T4/Hierarchy uses nested orchestration",
            "T5/Hybrid combines best approaches",
            "T0/Prompts ablation",
            "T1/Skills domain expertise",
            "T6/Super everything enabled",
        ],
    )
    def test_clean_line_not_flagged(self, tmp_path: Path, clean_line: str) -> None:
        """Correct tier name pairings produce no findings."""
        f = tmp_path / "test.md"
        f.write_text(clean_line + "\n", encoding="utf-8")
        findings = _collect_mismatches(f)
        assert findings == []

    def test_returns_correct_line_number(self, tmp_path: Path) -> None:
        """Finding records the correct 1-based line number."""
        f = tmp_path / "test.md"
        f.write_text("clean\nclean\nT3/Tooling bad\n", encoding="utf-8")
        findings = _collect_mismatches(f)
        assert len(findings) == 1
        assert findings[0].line == 3

    def test_finding_has_expected_name(self, tmp_path: Path) -> None:
        """Finding records the canonical (expected) name for the tier."""
        f = tmp_path / "test.md"
        f.write_text("T3/Tooling\n", encoding="utf-8")
        findings = _collect_mismatches(f)
        assert findings[0].expected_name == "Delegation"

    def test_finding_dataclass_fields(self, tmp_path: Path) -> None:
        """TierLabelFinding has all required fields."""
        f = tmp_path / "test.md"
        f.write_text("T4/Delegation wrong\n", encoding="utf-8")
        findings = _collect_mismatches(f)
        assert len(findings) == 1
        finding = findings[0]
        assert isinstance(finding, TierLabelFinding)
        assert finding.tier == "T4"
        assert finding.expected_name == "Hierarchy"
        assert finding.line == 1
        assert finding.raw_text

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        """Non-existent file returns empty list without raising."""
        missing = tmp_path / "nonexistent.md"
        assert _collect_mismatches(missing) == []

    def test_empty_file_returns_empty(self, tmp_path: Path) -> None:
        """Empty file returns empty list."""
        f = tmp_path / "empty.md"
        f.write_text("", encoding="utf-8")
        assert _collect_mismatches(f) == []

    def test_multiple_mismatches_in_one_file(self, tmp_path: Path) -> None:
        """Multiple mismatch lines in one file all produce findings."""
        f = tmp_path / "multi.md"
        f.write_text("T3/Tooling\nT4/Delegation\nT5/Hierarchy\n", encoding="utf-8")
        findings = _collect_mismatches(f)
        assert len(findings) == 3


class TestScanRepository:
    """Tests for scan_repository() — whole-repo scan API."""

    def test_clean_repo_returns_empty(self, tmp_path: Path) -> None:
        """A repository with no mismatch returns empty list."""
        (tmp_path / "docs.md").write_text("T3/Delegation\nT2/Tooling\n", encoding="utf-8")
        result = scan_repository(tmp_path)
        assert result == []

    def test_detects_mismatches_across_files(self, tmp_path: Path) -> None:
        """Mismatches in multiple files are all collected."""
        (tmp_path / "a.md").write_text("T3/Tooling bad\n", encoding="utf-8")
        (tmp_path / "b.md").write_text("T4/Delegation bad\n", encoding="utf-8")
        result = scan_repository(tmp_path)
        assert len(result) == 2

    def test_excludes_default_dirs(self, tmp_path: Path) -> None:
        """Files under excluded directories are skipped."""
        build = tmp_path / "build"
        build.mkdir()
        (build / "report.md").write_text("T3/Tooling bad\n", encoding="utf-8")
        result = scan_repository(tmp_path)
        assert result == []

    def test_excludes_pixi_dir(self, tmp_path: Path) -> None:
        """Files under .pixi/ are excluded from scanning."""
        pixi = tmp_path / ".pixi"
        pixi.mkdir()
        (pixi / "readme.md").write_text("T5/Hierarchy bad\n", encoding="utf-8")
        result = scan_repository(tmp_path)
        assert result == []

    def test_custom_excludes(self, tmp_path: Path) -> None:
        """Custom exclude directory names are respected."""
        custom = tmp_path / "mydir"
        custom.mkdir()
        (custom / "doc.md").write_text("T3/Tooling bad\n", encoding="utf-8")
        # Without exclusion: detected
        assert len(scan_repository(tmp_path, excludes=set())) > 0
        # With exclusion: skipped
        assert scan_repository(tmp_path, excludes={"mydir"}) == []

    def test_relative_file_paths_in_findings(self, tmp_path: Path) -> None:
        """Finding.file is relative to repo_root."""
        (tmp_path / "readme.md").write_text("T2/Skills bad\n", encoding="utf-8")
        result = scan_repository(tmp_path)
        assert len(result) == 1
        assert not result[0].file.startswith(str(tmp_path))
        assert "readme.md" in result[0].file

    def test_empty_directory_returns_empty(self, tmp_path: Path) -> None:
        """Empty repository directory returns empty list."""
        assert scan_repository(tmp_path) == []

    def test_custom_glob_pattern(self, tmp_path: Path) -> None:
        """Custom glob restricts which files are scanned."""
        (tmp_path / "readme.md").write_text("T3/Tooling bad\n", encoding="utf-8")
        (tmp_path / "notes.txt").write_text("T3/Tooling bad\n", encoding="utf-8")
        # Only *.md files are matched by default.
        result = scan_repository(tmp_path, glob="**/*.md")
        assert len(result) == 1
        assert "readme.md" in result[0].file

    def test_nested_subdirectory_scanned(self, tmp_path: Path) -> None:
        """Files in subdirectories are discovered by **/*.md glob."""
        sub = tmp_path / "docs" / "api"
        sub.mkdir(parents=True)
        (sub / "guide.md").write_text("T4/Delegation bad\n", encoding="utf-8")
        result = scan_repository(tmp_path)
        assert len(result) == 1
        assert "guide.md" in result[0].file


class TestFormatReport:
    """Tests for format_report()."""

    def test_empty_findings_returns_clean_message(self) -> None:
        """Empty findings list returns the all-clear message."""
        msg = format_report([])
        assert "No tier label mismatches found" in msg

    def test_findings_included_in_report(self, tmp_path: Path) -> None:
        """Non-empty findings produce a report with mismatch details."""
        finding = TierLabelFinding(
            file="docs/README.md",
            line=5,
            tier="T3",
            found_name="Tooling",
            expected_name="Delegation",
            raw_text="T3/Tooling is used here",
        )
        report = format_report([finding])
        assert "T3" in report
        assert "Tooling" in report
        assert "Delegation" in report

    def test_finding_count_in_report(self) -> None:
        """Report header includes the total mismatch count."""
        findings = [
            TierLabelFinding(
                file="a.md",
                line=i,
                tier="T3",
                found_name="Tooling",
                expected_name="Delegation",
                raw_text="T3/Tooling",
            )
            for i in range(3)
        ]
        report = format_report(findings)
        assert "3" in report


class TestFormatJson:
    """Tests for format_json()."""

    def test_empty_findings_returns_empty_array(self) -> None:
        """Empty findings list serialises to a JSON empty array."""
        result = json.loads(format_json([]))
        assert result == []

    def test_findings_serialised_correctly(self) -> None:
        """Finding fields appear in the JSON output."""
        finding = TierLabelFinding(
            file="docs/README.md",
            line=10,
            tier="T4",
            found_name="Delegation",
            expected_name="Hierarchy",
            raw_text="T4/Delegation is wrong",
        )
        result = json.loads(format_json([finding]))
        assert len(result) == 1
        obj = result[0]
        assert obj["file"] == "docs/README.md"
        assert obj["line"] == 10
        assert obj["tier"] == "T4"
        assert obj["found_name"] == "Delegation"
        assert obj["expected_name"] == "Hierarchy"
        assert obj["raw_text"] == "T4/Delegation is wrong"
