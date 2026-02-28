"""Tests for retry decorator with exponential backoff."""

from unittest.mock import MagicMock, patch

import pytest

from scylla.automation.retry import is_network_error, retry_on_network_error, retry_with_backoff


class TestIsNetworkError:
    """Tests for is_network_error function."""

    def test_detects_connection_error(self):
        """Test detection of connection-related errors."""
        error = ConnectionError("Connection refused")
        assert is_network_error(error) is True

    def test_detects_timeout_error(self):
        """Test detection of timeout errors."""
        error = TimeoutError("Request timed out")
        assert is_network_error(error) is True

    def test_detects_network_keywords(self):
        """Test detection of network error keywords in error messages."""
        test_cases = [
            "network unavailable",
            "temporary failure in name resolution",
            "could not resolve host",
            "rate limit exceeded",
            "throttle limit reached",
            "503 Service Unavailable",
            "502 Bad Gateway",
            "504 Gateway Timeout",
        ]

        for message in test_cases:
            error = Exception(message)
            assert is_network_error(error) is True, f"Failed to detect: {message}"

    def test_does_not_detect_non_network_errors(self):
        """Test that non-network errors are not detected."""
        test_cases = [
            "ValueError: invalid input",
            "KeyError: missing key",
            "TypeError: wrong type",
        ]

        for message in test_cases:
            error = Exception(message)
            assert is_network_error(error) is False, f"False positive: {message}"


class TestRetryWithBackoff:
    """Tests for retry_with_backoff decorator."""

    def test_succeeds_on_first_attempt(self):
        """Test function that succeeds on first attempt."""
        mock_func = MagicMock(return_value="success")
        decorated = retry_with_backoff(max_retries=3)(mock_func)

        result = decorated()

        assert result == "success"
        assert mock_func.call_count == 1

    def test_retries_on_failure(self):
        """Test function that fails then succeeds."""
        mock_func = MagicMock(side_effect=[ValueError("fail"), ValueError("fail"), "success"])
        decorated = retry_with_backoff(max_retries=3, initial_delay=0.01)(mock_func)

        result = decorated()

        assert result == "success"
        assert mock_func.call_count == 3

    def test_raises_after_max_retries(self):
        """Test function that exhausts all retries."""
        mock_func = MagicMock(side_effect=ValueError("fail"))
        decorated = retry_with_backoff(max_retries=2, initial_delay=0.01)(mock_func)

        with pytest.raises(ValueError, match="fail"):
            decorated()

        assert mock_func.call_count == 3  # initial + 2 retries

    def test_exponential_backoff_delay(self):
        """Test exponential backoff delays are calculated correctly."""
        mock_func = MagicMock(side_effect=[ValueError("fail"), ValueError("fail"), "success"])
        decorated = retry_with_backoff(max_retries=3, initial_delay=0.1, backoff_factor=2)(
            mock_func
        )

        with patch("scylla.automation.retry.time.sleep") as mock_sleep:
            result = decorated()

        assert result == "success"
        assert mock_func.call_count == 3
        # Two failures → two sleep calls: 0.1*2^0=0.1, 0.1*2^1=0.2
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(0.1)
        mock_sleep.assert_any_call(0.2)

    def test_respects_retry_on_parameter(self):
        """Test retry_on parameter filters exception types."""
        mock_func = MagicMock(side_effect=TypeError("wrong type"))
        # Only retry on ValueError, not TypeError
        decorated = retry_with_backoff(max_retries=3, retry_on=(ValueError,), initial_delay=0.01)(
            mock_func
        )

        with pytest.raises(TypeError):
            decorated()

        # Should not retry since TypeError is not in retry_on
        assert mock_func.call_count == 1

    def test_logger_called_on_retry(self):
        """Test logger is called with retry information."""
        mock_logger = MagicMock()
        mock_func = MagicMock(side_effect=[ValueError("fail"), "success"])
        decorated = retry_with_backoff(max_retries=2, initial_delay=0.01, logger=mock_logger)(
            mock_func
        )

        result = decorated()

        assert result == "success"
        assert mock_logger.call_count == 1
        # Check log message contains retry information
        log_message = mock_logger.call_args[0][0]
        assert "Retry 1/2" in log_message
        assert "ValueError" in log_message

    def test_preserves_function_metadata(self):
        """Test decorator preserves function name and docstring."""

        @retry_with_backoff(max_retries=2)
        def example_function():
            """Return example result."""
            return "result"

        assert example_function.__name__ == "example_function"
        assert example_function.__doc__ == "Return example result."

    def test_passes_arguments_correctly(self):
        """Test decorated function receives correct arguments."""
        mock_func = MagicMock(return_value="success")
        decorated = retry_with_backoff(max_retries=2)(mock_func)

        result = decorated("arg1", "arg2", kwarg1="value1")

        assert result == "success"
        mock_func.assert_called_once_with("arg1", "arg2", kwarg1="value1")


class TestRetryOnNetworkError:
    """Tests for retry_on_network_error convenience decorator."""

    def test_retries_connection_error(self):
        """Test retry on ConnectionError."""
        mock_func = MagicMock(side_effect=[ConnectionError("connection refused"), "success"])
        decorated = retry_on_network_error(max_retries=2)(mock_func)

        result = decorated()

        assert result == "success"
        assert mock_func.call_count == 2

    def test_retries_timeout_error(self):
        """Test retry on TimeoutError."""
        mock_func = MagicMock(side_effect=[TimeoutError("timed out"), "success"])
        decorated = retry_on_network_error(max_retries=2)(mock_func)

        result = decorated()

        assert result == "success"
        assert mock_func.call_count == 2

    def test_does_not_retry_value_error(self):
        """Test ValueError is not retried."""
        mock_func = MagicMock(side_effect=ValueError("invalid value"))
        decorated = retry_on_network_error(max_retries=2)(mock_func)

        with pytest.raises(ValueError):
            decorated()

        # Should not retry non-network errors
        assert mock_func.call_count == 1

    def test_uses_longer_initial_delay(self):
        """Test retry_on_network_error uses 2.0s initial delay."""
        mock_func = MagicMock(side_effect=[ConnectionError("fail"), "success"])
        decorated = retry_on_network_error(max_retries=1)(mock_func)

        with patch("scylla.automation.retry.time.sleep") as mock_sleep:
            result = decorated()
            # Verify sleep was called with the 2.0s initial delay
            mock_sleep.assert_called_once_with(2.0)

        assert result == "success"


class TestRetryWithJitter:
    """Tests for jitter parameter in retry_with_backoff."""

    def test_jitter_false_by_default(self):
        """Test jitter is disabled by default and delays are unmodified."""
        mock_func = MagicMock(side_effect=[ValueError("fail"), "success"])
        decorated = retry_with_backoff(max_retries=2, initial_delay=0.1, backoff_factor=2)(
            mock_func
        )

        with patch("scylla.automation.retry.time.sleep") as mock_sleep:
            with patch("scylla.automation.retry.random.uniform") as mock_uniform:
                result = decorated()

        assert result == "success"
        mock_uniform.assert_not_called()
        mock_sleep.assert_called_once_with(0.1)

    def test_jitter_true_applies_random_factor(self):
        """Test jitter=True multiplies delay by random.uniform(0.5, 1.5)."""
        mock_func = MagicMock(side_effect=[ValueError("fail"), "success"])
        decorated = retry_with_backoff(
            max_retries=2, initial_delay=0.1, backoff_factor=2, jitter=True
        )(mock_func)

        with patch("scylla.automation.retry.time.sleep") as mock_sleep:
            with patch("scylla.automation.retry.random.uniform", return_value=1.2) as mock_uniform:
                result = decorated()

        assert result == "success"
        mock_uniform.assert_called_once_with(0.5, 1.5)
        # delay = 0.1 * 2^0 * 1.2 = 0.12
        mock_sleep.assert_called_once_with(0.1 * 1.2)

    def test_jitter_applied_to_each_retry(self):
        """Test jitter is applied independently to each retry delay."""
        mock_func = MagicMock(side_effect=[ValueError("fail"), ValueError("fail"), "success"])
        decorated = retry_with_backoff(
            max_retries=3, initial_delay=0.1, backoff_factor=2, jitter=True
        )(mock_func)

        # Return different jitter factors for each retry
        jitter_values = [0.8, 1.3]
        with patch("scylla.automation.retry.time.sleep") as mock_sleep:
            with patch(
                "scylla.automation.retry.random.uniform", side_effect=jitter_values
            ) as mock_uniform:
                result = decorated()

        assert result == "success"
        assert mock_uniform.call_count == 2
        mock_uniform.assert_called_with(0.5, 1.5)
        # First retry: 0.1 * 2^0 * 0.8 = 0.08
        # Second retry: 0.1 * 2^1 * 1.3 = 0.26
        sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
        assert sleep_calls[0] == pytest.approx(0.1 * 0.8)
        assert sleep_calls[1] == pytest.approx(0.2 * 1.3)

    def test_jitter_with_logger_reports_jittered_delay(self):
        """Test logger receives the jittered delay value."""
        mock_logger = MagicMock()
        mock_func = MagicMock(side_effect=[ValueError("fail"), "success"])
        decorated = retry_with_backoff(
            max_retries=2, initial_delay=1.0, backoff_factor=2, jitter=True, logger=mock_logger
        )(mock_func)

        with patch("scylla.automation.retry.time.sleep"):
            with patch("scylla.automation.retry.random.uniform", return_value=0.75):
                result = decorated()

        assert result == "success"
        log_message = mock_logger.call_args[0][0]
        # Jittered delay = 1.0 * 2^0 * 0.75 = 0.75
        assert "0.75" in log_message
