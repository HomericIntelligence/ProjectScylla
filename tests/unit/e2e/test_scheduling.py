"""Unit tests for the off-peak scheduling module."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from scylla.e2e.scheduling import PEAK_END_UTC, PEAK_START_UTC, is_peak_hours, wait_for_off_peak


def _utc(weekday: int, hour: int) -> datetime:
    """Build a UTC datetime with the given weekday (0=Mon) and hour."""
    # 2026-03-02 is a Monday (weekday=0)
    base_monday = datetime(2026, 3, 2, hour, 0, 0, tzinfo=timezone.utc)
    # Advance by weekday days
    from datetime import timedelta

    return base_monday + timedelta(days=weekday)


class TestIsPeakHours:
    """Tests for is_peak_hours()."""

    def test_weekday_in_peak_window_returns_true(self) -> None:
        """Weekday at PEAK_START_UTC returns True."""
        peak_time = _utc(weekday=0, hour=PEAK_START_UTC)
        with patch("scylla.e2e.scheduling.datetime") as mock_dt:
            mock_dt.now.return_value = peak_time
            assert is_peak_hours() is True

    def test_weekday_one_before_peak_end_returns_true(self) -> None:
        """Weekday at PEAK_END_UTC - 1 (still inside window) returns True."""
        peak_time = _utc(weekday=1, hour=PEAK_END_UTC - 1)
        with patch("scylla.e2e.scheduling.datetime") as mock_dt:
            mock_dt.now.return_value = peak_time
            assert is_peak_hours() is True

    def test_weekday_at_peak_end_returns_false(self) -> None:
        """Weekday at exactly PEAK_END_UTC is off-peak."""
        off_peak_time = _utc(weekday=2, hour=PEAK_END_UTC)
        with patch("scylla.e2e.scheduling.datetime") as mock_dt:
            mock_dt.now.return_value = off_peak_time
            assert is_peak_hours() is False

    def test_weekday_before_peak_start_returns_false(self) -> None:
        """Weekday early morning (hour < PEAK_START_UTC) is off-peak."""
        off_peak_time = _utc(weekday=3, hour=PEAK_START_UTC - 1)
        with patch("scylla.e2e.scheduling.datetime") as mock_dt:
            mock_dt.now.return_value = off_peak_time
            assert is_peak_hours() is False

    def test_saturday_during_peak_hours_returns_false(self) -> None:
        """Weekends are always off-peak even during peak window."""
        saturday_peak = _utc(weekday=5, hour=PEAK_START_UTC)
        with patch("scylla.e2e.scheduling.datetime") as mock_dt:
            mock_dt.now.return_value = saturday_peak
            assert is_peak_hours() is False

    def test_sunday_during_peak_hours_returns_false(self) -> None:
        """Sundays are always off-peak."""
        sunday_peak = _utc(weekday=6, hour=PEAK_START_UTC + 2)
        with patch("scylla.e2e.scheduling.datetime") as mock_dt:
            mock_dt.now.return_value = sunday_peak
            assert is_peak_hours() is False

    def test_friday_in_peak_window_returns_true(self) -> None:
        """Friday is still a weekday — peak hours apply."""
        friday_peak = _utc(weekday=4, hour=PEAK_START_UTC + 1)
        with patch("scylla.e2e.scheduling.datetime") as mock_dt:
            mock_dt.now.return_value = friday_peak
            assert is_peak_hours() is True


class TestWaitForOffPeak:
    """Tests for wait_for_off_peak()."""

    def test_already_off_peak_returns_immediately(self) -> None:
        """Returns without sleeping when already off-peak."""
        off_peak_time = _utc(weekday=0, hour=PEAK_END_UTC + 1)
        with (
            patch("scylla.e2e.scheduling.datetime") as mock_dt,
            patch("scylla.e2e.scheduling.time") as mock_time,
        ):
            mock_dt.now.return_value = off_peak_time
            wait_for_off_peak()
            mock_time.sleep.assert_not_called()

    def test_during_peak_hours_sleeps_then_exits(self) -> None:
        """Sleeps at least once when peak, then exits when off-peak."""
        peak_time = _utc(weekday=0, hour=PEAK_START_UTC + 1)
        off_peak_time = _utc(weekday=0, hour=PEAK_END_UTC + 1)
        call_count = 0

        def fake_now(_tz: object) -> datetime:
            nonlocal call_count
            call_count += 1
            # First 3 calls: peak (initial check + off_peak_start calc + while check)
            # 4th+ call (after sleep): off-peak
            return peak_time if call_count <= 3 else off_peak_time

        with (
            patch("scylla.e2e.scheduling.datetime") as mock_dt,
            patch("scylla.e2e.scheduling.time") as mock_time,
        ):
            mock_dt.now.side_effect = fake_now
            wait_for_off_peak(check_interval_seconds=1)
            mock_time.sleep.assert_called_once_with(1)

    def test_weekend_returns_immediately(self) -> None:
        """Returns without sleeping on weekends."""
        saturday = _utc(weekday=5, hour=PEAK_START_UTC)
        with (
            patch("scylla.e2e.scheduling.datetime") as mock_dt,
            patch("scylla.e2e.scheduling.time") as mock_time,
        ):
            mock_dt.now.return_value = saturday
            wait_for_off_peak()
            mock_time.sleep.assert_not_called()
