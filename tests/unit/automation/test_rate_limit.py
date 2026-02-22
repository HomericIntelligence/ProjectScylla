"""Tests for rate limiting utilities."""

from datetime import datetime, timezone

from scylla.automation.rate_limit import (
    detect_claude_usage_limit,
    detect_rate_limit,
    parse_reset_epoch,
)


class TestParseResetEpoch:
    """Tests for parse_reset_epoch function."""

    def test_parse_unix_epoch(self):
        """Test parsing Unix epoch timestamp."""
        epoch = parse_reset_epoch("1234567890")
        assert epoch == 1234567890

    def test_parse_iso8601(self):
        """Test parsing ISO 8601 format."""
        epoch = parse_reset_epoch("2024-01-15T12:30:45Z")
        expected = int(datetime(2024, 1, 15, 12, 30, 45, tzinfo=timezone.utc).timestamp())
        assert epoch == expected

    def test_parse_human_readable(self):
        """Test parsing human-readable format."""
        epoch = parse_reset_epoch("2024-01-15 12:30:45 +0000 UTC")
        expected = int(datetime(2024, 1, 15, 12, 30, 45, tzinfo=timezone.utc).timestamp())
        assert epoch == expected

    def test_parse_human_readable_no_tz_name(self):
        """Test parsing human-readable format without timezone name."""
        epoch = parse_reset_epoch("2024-01-15 12:30:45 +0000")
        expected = int(datetime(2024, 1, 15, 12, 30, 45, tzinfo=timezone.utc).timestamp())
        assert epoch == expected

    def test_parse_invalid_format(self):
        """Test parsing invalid format returns None."""
        epoch = parse_reset_epoch("invalid timestamp")
        assert epoch is None

    def test_parse_empty_string(self):
        """Test parsing empty string returns None."""
        epoch = parse_reset_epoch("")
        assert epoch is None


class TestDetectRateLimit:
    """Tests for detect_rate_limit function."""

    def test_detect_with_reset_time(self):
        """Test detecting rate limit with reset time."""
        stderr = "API rate limit exceeded. Resets at 2024-01-15 12:30:45 +0000 UTC"

        is_limited, reset_epoch = detect_rate_limit(stderr)

        assert is_limited is True
        assert reset_epoch > 0

    def test_detect_with_reset_time_iso(self):
        """Test detecting rate limit with ISO format reset time."""
        stderr = "API rate limit exceeded. Reset time: 2024-01-15T12:30:45Z"

        is_limited, reset_epoch = detect_rate_limit(stderr)

        assert is_limited is True
        assert reset_epoch > 0

    def test_detect_without_reset_time(self):
        """Test detecting rate limit without reset time."""
        stderr = "rate limit exceeded"

        is_limited, reset_epoch = detect_rate_limit(stderr)

        assert is_limited is True
        assert reset_epoch == 0

    def test_detect_429_status(self):
        """Test detecting 429 status code."""
        stderr = "Error: 429 Too Many Requests"

        is_limited, _reset_epoch = detect_rate_limit(stderr)

        assert is_limited is True

    def test_no_rate_limit(self):
        """Test when there's no rate limit."""
        stderr = "Some other error occurred"

        is_limited, reset_epoch = detect_rate_limit(stderr)

        assert is_limited is False
        assert reset_epoch == 0


class TestDetectClaudeUsageLimit:
    """Tests for detect_claude_usage_limit function."""

    def test_detect_usage_limit(self):
        """Test detecting Claude usage limit."""
        stderr = "Error: usage limit exceeded"
        assert detect_claude_usage_limit(stderr) is True

    def test_detect_quota_exceeded(self):
        """Test detecting quota exceeded."""
        stderr = "quota exceeded for your account"
        assert detect_claude_usage_limit(stderr) is True

    def test_detect_credit_exhausted(self):
        """Test detecting credit exhausted."""
        stderr = "Your credit is exhausted"
        assert detect_claude_usage_limit(stderr) is True

    def test_detect_billing_issue(self):
        """Test detecting billing limit specifically."""
        stderr = "billing limit exceeded"
        assert detect_claude_usage_limit(stderr) is True

    def test_no_usage_limit(self):
        """Test when there's no usage limit."""
        stderr = "Some other error"
        assert detect_claude_usage_limit(stderr) is False

    def test_case_insensitive(self):
        """Test detection is case-insensitive."""
        stderr = "USAGE LIMIT exceeded"
        assert detect_claude_usage_limit(stderr) is True
