"""Tests for latency metrics."""

from datetime import datetime, timedelta

import pytest

from scylla.metrics.latency import (
    LatencyBreakdown,
    LatencyPhase,
    LatencyTracker,
    PhaseLatency,
    analyze_verification_overhead,
    calculate_latency_stats,
)


class TestLatencyPhase:
    """Tests for LatencyPhase enum."""

    def test_request_phases(self) -> None:
        """Request phases are defined."""
        assert LatencyPhase.QUEUE.value == "queue"
        assert LatencyPhase.PREPROCESSING.value == "preprocessing"
        assert LatencyPhase.INFERENCE.value == "inference"

    def test_streaming_phases(self) -> None:
        """Streaming phases are defined."""
        assert LatencyPhase.TIME_TO_FIRST_TOKEN.value == "ttft"
        assert LatencyPhase.INTER_TOKEN_LATENCY.value == "itl"
        assert LatencyPhase.TOTAL_GENERATION.value == "total_generation"

    def test_component_phases(self) -> None:
        """Component phases for T3+ are defined."""
        assert LatencyPhase.TOOL_EXECUTION.value == "tool_execution"
        assert LatencyPhase.ORCHESTRATION.value == "orchestration"
        assert LatencyPhase.VERIFICATION.value == "verification"


class TestPhaseLatency:
    """Tests for PhaseLatency dataclass."""

    def test_creation(self) -> None:
        """Create phase latency with defaults."""
        phase = PhaseLatency(phase=LatencyPhase.INFERENCE)
        assert phase.phase == LatencyPhase.INFERENCE
        assert phase.duration_ms == 0.0

    def test_with_timing(self) -> None:
        """Create phase with timing data."""
        now = datetime.now()
        phase = PhaseLatency(
            phase=LatencyPhase.INFERENCE,
            start_time=now,
            end_time=now + timedelta(milliseconds=100),
            duration_ms=100.0,
        )
        assert phase.duration_ms == 100.0


class TestLatencyTracker:
    """Tests for LatencyTracker class."""

    def test_start_request(self) -> None:
        """Track request start time."""
        tracker = LatencyTracker()
        tracker.start_request()
        breakdown = tracker.get_breakdown()
        assert breakdown.total_duration_ms >= 0

    def test_phase_tracking(self) -> None:
        """Track individual phases."""
        tracker = LatencyTracker()
        tracker.start_phase(LatencyPhase.PREPROCESSING)
        duration = tracker.end_phase(LatencyPhase.PREPROCESSING)
        assert duration >= 0

    def test_get_phase_duration(self) -> None:
        """Get duration of specific phase."""
        tracker = LatencyTracker()
        tracker.start_phase(LatencyPhase.INFERENCE)
        tracker.end_phase(LatencyPhase.INFERENCE)
        duration = tracker.get_phase_duration(LatencyPhase.INFERENCE)
        assert duration >= 0

    def test_untracked_phase_returns_zero(self) -> None:
        """Untracked phase returns 0 duration."""
        tracker = LatencyTracker()
        duration = tracker.get_phase_duration(LatencyPhase.TOOL_EXECUTION)
        assert duration == 0.0

    def test_record_first_token(self) -> None:
        """Record TTFT timing."""
        tracker = LatencyTracker()
        tracker.start_request()
        ttft = tracker.record_first_token()
        assert ttft >= 0

    def test_get_ttft(self) -> None:
        """Get TTFT after recording."""
        tracker = LatencyTracker()
        tracker.start_request()
        tracker.record_first_token()
        ttft = tracker.get_ttft()
        assert ttft >= 0

    def test_ttft_without_request_start(self) -> None:
        """TTFT returns 0 without request start."""
        tracker = LatencyTracker()
        tracker.record_first_token()
        assert tracker.get_ttft() == 0.0

    def test_get_breakdown(self) -> None:
        """Get complete breakdown."""
        tracker = LatencyTracker()
        tracker.start_request()
        tracker.start_phase(LatencyPhase.INFERENCE)
        tracker.record_first_token()
        tracker.end_phase(LatencyPhase.INFERENCE)

        breakdown = tracker.get_breakdown(token_count=100)
        assert breakdown.total_duration_ms >= 0
        assert breakdown.ttft_ms >= 0
        assert breakdown.token_count == 100
        assert len(breakdown.phases) == 1

    def test_tokens_per_second(self) -> None:
        """Calculate tokens per second."""
        breakdown = LatencyBreakdown(
            total_duration_ms=1000,  # 1 second
            token_count=100,
            tokens_per_second=100.0,
        )
        assert breakdown.tokens_per_second == 100.0

    def test_clear(self) -> None:
        """Clear all tracked data."""
        tracker = LatencyTracker()
        tracker.start_request()
        tracker.start_phase(LatencyPhase.INFERENCE)
        tracker.record_first_token()
        tracker.end_phase(LatencyPhase.INFERENCE)

        tracker.clear()
        breakdown = tracker.get_breakdown()
        assert breakdown.total_duration_ms == 0.0
        assert breakdown.ttft_ms == 0.0
        assert len(breakdown.phases) == 0


class TestCalculateLatencyStats:
    """Tests for calculate_latency_stats function."""

    def test_empty_list(self) -> None:
        """Empty list returns zero stats."""
        stats = calculate_latency_stats([])
        assert stats["total_ms_mean"] == 0.0
        assert stats["ttft_ms_mean"] == 0.0

    def test_single_breakdown(self) -> None:
        """Stats from single breakdown."""
        breakdown = LatencyBreakdown(
            total_duration_ms=100.0,
            ttft_ms=20.0,
            tokens_per_second=50.0,
        )
        stats = calculate_latency_stats([breakdown])
        assert stats["total_ms_mean"] == 100.0
        assert stats["ttft_ms_mean"] == 20.0
        assert stats["tokens_per_second_mean"] == 50.0

    def test_percentiles(self) -> None:
        """Calculate percentile statistics."""
        breakdowns = [
            LatencyBreakdown(total_duration_ms=100.0),
            LatencyBreakdown(total_duration_ms=200.0),
            LatencyBreakdown(total_duration_ms=300.0),
            LatencyBreakdown(total_duration_ms=400.0),
            LatencyBreakdown(total_duration_ms=500.0),
        ]
        stats = calculate_latency_stats(breakdowns)
        assert stats["total_ms_p50"] == 300.0
        assert stats["total_ms_mean"] == 300.0


class TestAnalyzeVerificationOverhead:
    """Tests for analyze_verification_overhead function."""

    def test_empty_list(self) -> None:
        """Empty list returns zero overhead."""
        result = analyze_verification_overhead([])
        assert result["overhead_ratio"] == 0.0
        assert result["overhead_percentage"] == 0.0

    def test_no_verification_phases(self) -> None:
        """No verification phases returns zero overhead."""
        breakdown = LatencyBreakdown(
            phases=[
                PhaseLatency(phase=LatencyPhase.INFERENCE, duration_ms=100.0),
            ]
        )
        result = analyze_verification_overhead([breakdown])
        assert result["overhead_ratio"] == 0.0

    def test_with_verification_phases(self) -> None:
        """Calculate verification overhead correctly."""
        breakdown = LatencyBreakdown(
            phases=[
                PhaseLatency(phase=LatencyPhase.INFERENCE, duration_ms=100.0),
                PhaseLatency(phase=LatencyPhase.VERIFICATION, duration_ms=100.0),
            ]
        )
        result = analyze_verification_overhead([breakdown])

        # Verification = Inference, so ratio = 1.0
        assert result["overhead_ratio"] == 1.0
        # Verification is 50% of total
        assert result["overhead_percentage"] == 50.0

    def test_double_verification(self) -> None:
        """Verification doubles inference time (T5 expected behavior)."""
        breakdown = LatencyBreakdown(
            phases=[
                PhaseLatency(phase=LatencyPhase.INFERENCE, duration_ms=100.0),
                PhaseLatency(phase=LatencyPhase.VERIFICATION, duration_ms=200.0),
            ]
        )
        result = analyze_verification_overhead([breakdown])

        # Verification is 2x inference
        assert result["overhead_ratio"] == 2.0
        # Verification is 66.7% of total
        assert result["overhead_percentage"] == pytest.approx(66.67, rel=0.01)
