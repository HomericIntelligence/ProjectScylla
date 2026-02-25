"""Tests for scripts/filter_audit.py."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

import scripts.filter_audit
from scripts.filter_audit import extract_cvss_score, load_ignore_list, main, severity_label

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_audit_json(
    *,
    pkg: str = "somepackage",
    version: str = "1.0.0",
    vuln_id: str = "GHSA-xxx-yyy-zzz",
    severity: list[dict[str, object]] | None = None,
) -> str:
    """Return a minimal pip-audit JSON string with one vulnerability."""
    if severity is None:
        severity = []
    data = {
        "dependencies": [
            {
                "name": pkg,
                "version": version,
                "vulns": [
                    {
                        "id": vuln_id,
                        "severity": severity,
                    }
                ],
            }
        ]
    }
    return json.dumps(data)


# ---------------------------------------------------------------------------
# TestLoadIgnoreList
# ---------------------------------------------------------------------------


class TestLoadIgnoreList:
    """Tests for load_ignore_list."""

    def test_missing_file_returns_empty_frozenset(self, tmp_path: Path) -> None:
        """A nonexistent path should return an empty frozenset."""
        result = load_ignore_list(tmp_path / "nonexistent.txt")
        assert result == frozenset()

    def test_empty_file_returns_empty_frozenset(self, tmp_path: Path) -> None:
        """An empty file should return an empty frozenset."""
        ignore_file = tmp_path / "ignore.txt"
        ignore_file.write_text("")
        result = load_ignore_list(ignore_file)
        assert result == frozenset()

    def test_comment_lines_ignored(self, tmp_path: Path) -> None:
        """Lines starting with '#' should not be included."""
        ignore_file = tmp_path / "ignore.txt"
        ignore_file.write_text("# This is a comment\n# Another comment\n")
        result = load_ignore_list(ignore_file)
        assert result == frozenset()

    def test_inline_comments_stripped(self, tmp_path: Path) -> None:
        """Inline comments should be stripped, leaving only the advisory ID."""
        ignore_file = tmp_path / "ignore.txt"
        ignore_file.write_text("GHSA-123-abc-def  # reason for ignoring\n")
        result = load_ignore_list(ignore_file)
        assert "GHSA-123-abc-def" in result
        assert "# reason for ignoring" not in str(result)

    def test_valid_ids_loaded(self, tmp_path: Path) -> None:
        """Valid advisory IDs should appear in the returned frozenset."""
        ignore_file = tmp_path / "ignore.txt"
        ignore_file.write_text("GHSA-aaa-bbb-ccc\nGHSA-ddd-eee-fff\n")
        result = load_ignore_list(ignore_file)
        assert "GHSA-aaa-bbb-ccc" in result
        assert "GHSA-ddd-eee-fff" in result


# ---------------------------------------------------------------------------
# TestExtractCvssScore
# ---------------------------------------------------------------------------


class TestExtractCvssScore:
    """Tests for extract_cvss_score."""

    def test_empty_list_returns_none(self) -> None:
        """An empty severity list should return None."""
        assert extract_cvss_score([]) is None

    def test_numeric_score_field(self) -> None:
        """An entry with a numeric 'score' field should return that value."""
        result = extract_cvss_score([{"score": 7.5}])
        assert result == pytest.approx(7.5)

    def test_base_score_field(self) -> None:
        """An entry with a 'base_score' field should return that value."""
        result = extract_cvss_score([{"base_score": 9.0}])
        assert result == pytest.approx(9.0)

    def test_max_of_multiple_scores(self) -> None:
        """When multiple score entries exist, the maximum should be returned."""
        result = extract_cvss_score([{"score": 4.0}, {"score": 7.5}])
        assert result == pytest.approx(7.5)

    def test_cvss_vector_string_no_numeric(self) -> None:
        """A CVSS vector string without a numeric score field should yield None."""
        result = extract_cvss_score([{"score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}])
        assert result is None


# ---------------------------------------------------------------------------
# TestSeverityLabel
# ---------------------------------------------------------------------------


class TestSeverityLabel:
    """Tests for severity_label."""

    def test_none_score_returns_unknown(self) -> None:
        """None score should return 'UNKNOWN'."""
        assert severity_label(None) == "UNKNOWN"

    def test_critical_threshold(self) -> None:
        """Score >= 9.0 should return 'CRITICAL'."""
        assert severity_label(9.0) == "CRITICAL"

    def test_high_threshold(self) -> None:
        """Score >= 7.0 and < 9.0 should return 'HIGH'."""
        assert severity_label(7.0) == "HIGH"

    def test_medium_threshold(self) -> None:
        """Score >= 4.0 and < 7.0 should return 'MEDIUM'."""
        assert severity_label(4.0) == "MEDIUM"

    def test_low_threshold(self) -> None:
        """Score >= 0.1 and < 4.0 should return 'LOW'."""
        assert severity_label(0.1) == "LOW"

    def test_zero_returns_none_label(self) -> None:
        """Score of 0.0 should return 'NONE'."""
        assert severity_label(0.0) == "NONE"


# ---------------------------------------------------------------------------
# TestMain
# ---------------------------------------------------------------------------


class TestMain:
    """Tests for main() using monkeypatched stdin and tmp_path ignore files."""

    def test_no_json_returns_0(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Stdin with no JSON blob should result in exit code 0."""
        monkeypatch.setattr(sys, "stdin", io.StringIO("No known vulnerabilities found\n"))
        result = main()
        assert result == 0

    def test_empty_deps_returns_0(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """JSON with an empty dependencies list should result in exit code 0."""
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"dependencies": []})))
        result = main()
        assert result == 0

    def test_low_severity_returns_0(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A LOW severity vulnerability (score=3.0) should not block CI (exit 0)."""
        payload = _make_audit_json(severity=[{"score": 3.0}])
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        result = main()
        assert result == 0

    def test_high_severity_returns_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A HIGH severity vulnerability (score=7.5) should block CI (exit 1)."""
        payload = _make_audit_json(severity=[{"score": 7.5}])
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        result = main()
        assert result == 1

    def test_critical_severity_returns_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A CRITICAL severity vulnerability (score=9.5) should block CI (exit 1)."""
        payload = _make_audit_json(severity=[{"score": 9.5}])
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        result = main()
        assert result == 1

    def test_ignored_vuln_skipped(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """A HIGH vulnerability whose ID appears in the ignore file should not block CI."""
        # load_ignore_list uses _IGNORE_FILE as a default parameter (captured at definition
        # time), so patching the module attribute alone won't affect calls with no argument.
        # Patch load_ignore_list directly to return the desired frozenset.
        monkeypatch.setattr(
            scripts.filter_audit,
            "load_ignore_list",
            lambda *_args, **_kwargs: frozenset({"GHSA-xxx-yyy-zzz"}),
        )

        payload = _make_audit_json(vuln_id="GHSA-xxx-yyy-zzz", severity=[{"score": 7.5}])
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        result = main()
        assert result == 0

    def test_medium_severity_suppressed_returns_0(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A MEDIUM severity vulnerability should not block CI and should be suppressed."""
        payload = _make_audit_json(severity=[{"score": 5.0}])
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        result = main()
        assert result == 0
        stdout = capsys.readouterr().out
        # The vuln should be mentioned as suppressed, not as blocking
        assert "BLOCKING" not in stdout

    def test_malformed_json_returns_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Malformed JSON (content after '{' that cannot be parsed) should exit 1."""
        monkeypatch.setattr(sys, "stdin", io.StringIO("{this is not valid json"))
        result = main()
        assert result == 1
