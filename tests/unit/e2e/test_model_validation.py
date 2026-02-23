"""Tests for model validation utilities."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from scylla.e2e.model_validation import is_rate_limit_error, validate_model


class TestIsRateLimitError:
    """Tests for is_rate_limit_error()."""

    def test_no_rate_limit_returns_false(self) -> None:
        """Normal output returns (False, None)."""
        result, wait = is_rate_limit_error("Model validation OK")
        assert result is False
        assert wait is None

    def test_hit_your_limit_detected(self) -> None:
        """'hit your limit' triggers rate limit detection."""
        result, wait = is_rate_limit_error("You've hit your limit for the day.")
        assert result is True

    def test_rate_limit_phrase_detected(self) -> None:
        """'rate limit' phrase triggers detection."""
        result, wait = is_rate_limit_error("API rate limit exceeded.")
        assert result is True

    def test_parse_minutes(self) -> None:
        """Minutes are correctly parsed."""
        result, wait = is_rate_limit_error("rate limit — try again in 5 minutes")
        assert result is True
        assert wait == 5 * 60

    def test_parse_seconds(self) -> None:
        """Seconds are correctly parsed."""
        result, wait = is_rate_limit_error("rate limit, wait 30 seconds")
        assert result is True
        assert wait == 30

    def test_parse_hours(self) -> None:
        """Hours are correctly parsed."""
        result, wait = is_rate_limit_error("rate limit in 2 hours")
        assert result is True
        assert wait == 2 * 3600

    def test_unparseable_time_defaults_to_one_hour(self) -> None:
        """When time cannot be parsed, defaults to 3600s."""
        result, wait = is_rate_limit_error("rate limit — no time given")
        assert result is True
        assert wait == 3600

    def test_am_pm_returns_twelve_hours(self) -> None:
        """AM/PM time patterns return 12-hour estimate."""
        result, wait = is_rate_limit_error("rate limit resets 6am")
        assert result is True
        assert wait == 12 * 3600

    def test_empty_string_returns_false(self) -> None:
        """Empty string returns (False, None)."""
        result, wait = is_rate_limit_error("")
        assert result is False
        assert wait is None


class TestValidateModel:
    """Tests for validate_model()."""

    def test_successful_validation(self) -> None:
        """Returns True when model responds with is_error:false."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        # Note: pattern check is '"is_error":false' (no space after colon)
        mock_result.stdout = '{"result":"OK","is_error":false}'
        mock_result.stderr = ""

        with patch("scylla.e2e.model_validation.subprocess.run", return_value=mock_result):
            assert validate_model("claude-test-model") is True

    def test_model_not_found(self) -> None:
        """Returns False when model returns not_found_error."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "not_found_error: model not available"
        mock_result.stderr = ""

        with patch("scylla.e2e.model_validation.subprocess.run", return_value=mock_result):
            assert validate_model("claude-invalid-model", max_retries=0) is False

    def test_claude_cli_not_found(self) -> None:
        """Returns False when Claude CLI is not installed."""
        with patch("scylla.e2e.model_validation.subprocess.run", side_effect=FileNotFoundError):
            assert validate_model("any-model") is False

    def test_timeout_exhausts_retries(self) -> None:
        """Returns False after all retries are exhausted on timeout."""
        import subprocess

        with patch(
            "scylla.e2e.model_validation.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=30),
        ):
            with patch("scylla.e2e.model_validation.time.sleep"):
                assert validate_model("claude-model", max_retries=1, base_delay=0) is False

    def test_is_importable_from_run_e2e_experiment(self) -> None:
        """validate_model should still be importable from run_e2e_experiment for compat."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from scripts.run_e2e_experiment import validate_model as compat_fn

        assert callable(compat_fn)

    def test_is_rate_limit_error_importable_from_run_e2e_experiment(self) -> None:
        """is_rate_limit_error should still be importable from run_e2e_experiment for compat."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from scripts.run_e2e_experiment import is_rate_limit_error as compat_fn

        assert callable(compat_fn)
