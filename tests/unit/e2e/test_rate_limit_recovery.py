"""Unit tests for rate limit recovery functions in subtest_executor."""

from __future__ import annotations

import json
from pathlib import Path

from scylla.e2e.models import SubTestResult, TierID
from scylla.e2e.rate_limit import RateLimitInfo
from scylla.e2e.subtest_executor import (
    _detect_rate_limit_from_results,
)


class TestDetectRateLimitFromResults:
    """Tests for _detect_rate_limit_from_results function."""

    def test_detects_from_rate_limit_info_field(self, tmp_path: Path) -> None:
        """Test detection from SubTestResult.rate_limit_info field."""
        rate_info = RateLimitInfo(
            source="agent",
            retry_after_seconds=60.0,
            error_message="Rate limit exceeded",
            detected_at="2026-01-09T12:00:00Z",
        )

        results = {
            "01": SubTestResult(
                subtest_id="01",
                tier_id=TierID.T5,
                runs=[],
                pass_rate=0.0,
                selection_reason="RateLimitError: Rate limit exceeded",
                rate_limit_info=rate_info,
            )
        }

        detected = _detect_rate_limit_from_results(results, tmp_path)

        assert detected is not None
        assert detected.source == "agent"
        assert detected.retry_after_seconds == 60.0

    def test_detects_from_selection_reason(self, tmp_path: Path) -> None:
        """Test detection from SubTestResult.selection_reason."""
        results = {
            "01": SubTestResult(
                subtest_id="01",
                tier_id=TierID.T5,
                runs=[],
                pass_rate=0.0,
                selection_reason="RateLimitError: You've hit your limit",
            )
        }

        detected = _detect_rate_limit_from_results(results, tmp_path)

        assert detected is not None
        assert detected.source == "agent"
        assert "RateLimitError" in detected.error_message

    def test_detects_from_failed_directory(self, tmp_path: Path) -> None:
        """Test detection from .failed/ directory."""
        # Create .failed/ directory structure
        # Note: _detect_rate_limit_from_results uses rglob(".failed/*/agent/result.json")
        # which matches any depth, so we create: subtest_id/.failed/run_id/agent/result.json
        failed_dir = tmp_path / ".failed" / "run_01_attempt_01" / "agent"
        failed_dir.mkdir(parents=True)

        # Create result.json with rate limit error
        result_data = {
            "exit_code": -1,
            "stderr": "You've hit your limit. Retry-After: 120",
            "stdout": "",
        }
        (failed_dir / "result.json").write_text(json.dumps(result_data))

        results: dict[str, SubTestResult] = {}

        detected = _detect_rate_limit_from_results(results, tmp_path)

        assert detected is not None
        assert detected.source == "agent"
        assert detected.retry_after_seconds == 132.0  # 120 * 1.1

    def test_no_rate_limit_returns_none(self, tmp_path: Path) -> None:
        """Test that no rate limit returns None."""
        results = {
            "01": SubTestResult(
                subtest_id="01",
                tier_id=TierID.T5,
                runs=[],
                pass_rate=0.0,
                selection_reason="Success",
            )
        }

        detected = _detect_rate_limit_from_results(results, tmp_path)

        assert detected is None

    def test_malformed_json_ignored(self, tmp_path: Path) -> None:
        """Test that malformed JSON in .failed/ is ignored."""
        failed_dir = tmp_path / "01" / ".failed" / "run_01_attempt_01" / "agent"
        failed_dir.mkdir(parents=True)

        # Write invalid JSON
        (failed_dir / "result.json").write_text("not json {{{")

        results: dict[str, SubTestResult] = {}

        detected = _detect_rate_limit_from_results(results, tmp_path)

        assert detected is None


class TestSubTestResultSerialization:
    """Tests for SubTestResult with rate_limit_info field."""

    def test_to_dict_with_rate_limit_info(self) -> None:
        """Test SubTestResult.to_dict() with rate_limit_info."""
        rate_info = RateLimitInfo(
            source="agent",
            retry_after_seconds=60.0,
            error_message="Rate limit exceeded",
            detected_at="2026-01-09T12:00:00Z",
        )

        result = SubTestResult(
            subtest_id="01",
            tier_id=TierID.T5,
            runs=[],
            pass_rate=0.0,
            rate_limit_info=rate_info,
        )

        data = result.to_dict()

        assert data["rate_limit_info"] is not None
        assert data["rate_limit_info"]["source"] == "agent"
        assert data["rate_limit_info"]["retry_after_seconds"] == 60.0

    def test_to_dict_without_rate_limit_info(self) -> None:
        """Test SubTestResult.to_dict() without rate_limit_info."""
        result = SubTestResult(
            subtest_id="01",
            tier_id=TierID.T5,
            runs=[],
            pass_rate=1.0,
        )

        data = result.to_dict()

        assert data["rate_limit_info"] is None
