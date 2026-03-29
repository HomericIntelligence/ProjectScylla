"""Off-peak scheduling to avoid Claude API peak hours.

Peak hours are defined as 8AM–2PM ET on weekdays (conservative window covering
both EST and EDT):
  EST offset: UTC-5  → peak = 13:00–19:00 UTC
  EDT offset: UTC-4  → peak = 12:00–18:00 UTC

We use the broader window (12:00–19:00 UTC) to ensure we always stay outside
peak hours regardless of daylight saving time.

Usage:
    from scylla.e2e.scheduling import wait_for_off_peak

    if config.off_peak:
        wait_for_off_peak()
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Peak window in UTC (covers 8AM EDT to 3PM EDT and 8AM EST to 2PM EST)
PEAK_START_UTC = 12  # 8AM EDT / 7AM EST (conservative start)
PEAK_END_UTC = 19  # 3PM EDT / 2PM EST (conservative end)


def is_peak_hours() -> bool:
    """Return True if the current UTC time falls within peak API hours.

    Peak hours are weekdays 12:00–19:00 UTC (8AM–3PM EDT / 7AM–2PM EST).
    Weekends are always off-peak.

    Returns:
        True if currently in peak hours, False otherwise.

    """
    now = datetime.now(timezone.utc)
    # weekday() returns 0=Monday ... 6=Sunday
    if now.weekday() >= 5:
        return False
    return PEAK_START_UTC <= now.hour < PEAK_END_UTC


def wait_for_off_peak(check_interval_seconds: int = 300) -> None:
    """Block until the current time is outside peak API hours.

    If already off-peak, returns immediately. Otherwise logs a warning and
    sleeps in intervals until peak hours are over.

    Args:
        check_interval_seconds: How often to re-check (default: 5 minutes).

    """
    if not is_peak_hours():
        return

    now = datetime.now(timezone.utc)
    off_peak_start = now.replace(hour=PEAK_END_UTC, minute=0, second=0, microsecond=0)
    if now.hour >= PEAK_END_UTC:
        # Already past end of today's peak window — shouldn't happen, but guard it
        return

    wait_minutes = int((off_peak_start - now).total_seconds() / 60)
    logger.warning(
        f"[SCHEDULING] Currently in peak API hours (UTC {now.hour:02d}:xx, "
        f"weekday={now.weekday()}). Waiting ~{wait_minutes} minutes until "
        f"{PEAK_END_UTC:02d}:00 UTC..."
    )

    while is_peak_hours():
        time.sleep(check_interval_seconds)
        now = datetime.now(timezone.utc)
        logger.info(
            f"[SCHEDULING] Still peak hours (UTC {now.hour:02d}:{now.minute:02d}), waiting..."
        )

    logger.info("[SCHEDULING] Off-peak hours — proceeding with run.")
