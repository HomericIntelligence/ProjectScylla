"""Latency metrics for performance tracking.

This module provides detailed latency tracking including Time-to-First-Token
(TTFT) and component-level timing breakdowns.

Python Justification: Required for time calculations and data structures.

References:
- docs/research.md: Section 4.1 (Latency metric)
- .claude/shared/metrics-definitions.md: Latency components

"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class LatencyPhase(Enum):
    """Phases of request processing for latency tracking."""

    # Request phases
    QUEUE = "queue"  # Time waiting in queue
    PREPROCESSING = "preprocessing"  # Input preparation
    INFERENCE = "inference"  # Model inference
    POSTPROCESSING = "postprocessing"  # Output processing

    # Streaming phases
    TIME_TO_FIRST_TOKEN = "ttft"  # Time to first token
    INTER_TOKEN_LATENCY = "itl"  # Average between tokens
    TOTAL_GENERATION = "total_generation"  # Full generation time

    # Component phases (T3+)
    TOOL_EXECUTION = "tool_execution"  # External tool calls
    ORCHESTRATION = "orchestration"  # T4/T5 coordination
    VERIFICATION = "verification"  # T5 Monitor/Evaluator loop


@dataclass
class PhaseLatency:
    """Latency measurement for a single phase.

    Attributes:
        phase: The phase being measured.
        start_time: When the phase started.
        end_time: When the phase ended.
        duration_ms: Duration in milliseconds.
        metadata: Optional additional context.

    """

    phase: LatencyPhase
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_ms: float = 0.0
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class LatencyBreakdown:
    """Complete latency breakdown for a request.

    Attributes:
        total_duration_ms: Total request duration in milliseconds.
        ttft_ms: Time to first token in milliseconds.
        phases: Individual phase measurements.
        token_count: Number of tokens generated.
        tokens_per_second: Generation throughput.

    """

    total_duration_ms: float = 0.0
    ttft_ms: float = 0.0
    phases: list[PhaseLatency] = field(default_factory=list)
    token_count: int = 0
    tokens_per_second: float = 0.0


class LatencyTracker:
    """Tracks latency across request processing phases.

    Example:
        tracker = LatencyTracker()
        tracker.start_phase(LatencyPhase.PREPROCESSING)
        # ... do preprocessing ...
        tracker.end_phase(LatencyPhase.PREPROCESSING)

        tracker.start_phase(LatencyPhase.INFERENCE)
        tracker.record_first_token()  # Records TTFT
        # ... generate tokens ...
        tracker.end_phase(LatencyPhase.INFERENCE)

        breakdown = tracker.get_breakdown(token_count=500)

    """

    def __init__(self) -> None:
        """Initialize empty tracker."""
        self._phases: dict[LatencyPhase, PhaseLatency] = {}
        self._request_start: datetime | None = None
        self._first_token_time: datetime | None = None
        self._active_phase: LatencyPhase | None = None

    def start_request(self) -> None:
        """Mark the start of a request."""
        self._request_start = datetime.now()

    def start_phase(
        self,
        phase: LatencyPhase,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Start tracking a phase.

        Args:
            phase: The phase to start tracking.
            metadata: Optional context for this phase.

        """
        self._phases[phase] = PhaseLatency(
            phase=phase,
            start_time=datetime.now(),
            metadata=metadata or {},
        )
        self._active_phase = phase

    def end_phase(self, phase: LatencyPhase) -> float:
        """End tracking a phase.

        Args:
            phase: The phase to stop tracking.

        Returns:
            Duration of the phase in milliseconds.

        """
        if phase not in self._phases:
            return 0.0

        phase_data = self._phases[phase]
        phase_data.end_time = datetime.now()

        if phase_data.start_time:
            delta = phase_data.end_time - phase_data.start_time
            phase_data.duration_ms = delta.total_seconds() * 1000

        if self._active_phase == phase:
            self._active_phase = None

        return phase_data.duration_ms

    def record_first_token(self) -> float:
        """Record the time when first token was generated.

        Returns:
            Time to first token in milliseconds from request start.

        """
        self._first_token_time = datetime.now()

        if self._request_start:
            delta = self._first_token_time - self._request_start
            return delta.total_seconds() * 1000
        return 0.0

    def get_ttft(self) -> float:
        """Get Time to First Token in milliseconds.

        Returns:
            TTFT in milliseconds, or 0.0 if not recorded.

        """
        if self._request_start and self._first_token_time:
            delta = self._first_token_time - self._request_start
            return delta.total_seconds() * 1000
        return 0.0

    def get_phase_duration(self, phase: LatencyPhase) -> float:
        """Get duration of a specific phase.

        Args:
            phase: The phase to query.

        Returns:
            Duration in milliseconds, or 0.0 if not tracked.

        """
        if phase in self._phases:
            return self._phases[phase].duration_ms
        return 0.0

    def get_breakdown(self, token_count: int = 0) -> LatencyBreakdown:
        """Get complete latency breakdown.

        Args:
            token_count: Number of tokens generated (for throughput calc).

        Returns:
            LatencyBreakdown with all measurements.

        """
        # Calculate total duration
        total_ms = 0.0
        if self._request_start:
            end_time = datetime.now()
            delta = end_time - self._request_start
            total_ms = delta.total_seconds() * 1000

        # Calculate tokens per second
        tps = 0.0
        if total_ms > 0 and token_count > 0:
            tps = token_count / (total_ms / 1000)

        return LatencyBreakdown(
            total_duration_ms=total_ms,
            ttft_ms=self.get_ttft(),
            phases=list(self._phases.values()),
            token_count=token_count,
            tokens_per_second=tps,
        )

    def clear(self) -> None:
        """Clear all tracked data."""
        self._phases.clear()
        self._request_start = None
        self._first_token_time = None
        self._active_phase = None


def calculate_latency_stats(
    breakdowns: list[LatencyBreakdown],
) -> dict[str, float]:
    """Calculate statistics across multiple latency measurements.

    Args:
        breakdowns: List of latency breakdowns to analyze.

    Returns:
        Dictionary with statistical summaries.

    """
    if not breakdowns:
        return {
            "total_ms_mean": 0.0,
            "total_ms_p50": 0.0,
            "total_ms_p95": 0.0,
            "total_ms_p99": 0.0,
            "ttft_ms_mean": 0.0,
            "ttft_ms_p50": 0.0,
            "ttft_ms_p95": 0.0,
            "tokens_per_second_mean": 0.0,
        }

    totals = [b.total_duration_ms for b in breakdowns]
    ttfts = [b.ttft_ms for b in breakdowns if b.ttft_ms > 0]
    tps_values = [b.tokens_per_second for b in breakdowns if b.tokens_per_second > 0]

    def percentile(values: list[float], p: float) -> float:
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        idx = int(len(sorted_vals) * p / 100)
        return sorted_vals[min(idx, len(sorted_vals) - 1)]

    def mean(values: list[float]) -> float:
        if not values:
            return 0.0
        return sum(values) / len(values)

    return {
        "total_ms_mean": mean(totals),
        "total_ms_p50": percentile(totals, 50),
        "total_ms_p95": percentile(totals, 95),
        "total_ms_p99": percentile(totals, 99),
        "ttft_ms_mean": mean(ttfts),
        "ttft_ms_p50": percentile(ttfts, 50),
        "ttft_ms_p95": percentile(ttfts, 95),
        "tokens_per_second_mean": mean(tps_values),
    }


def analyze_verification_overhead(
    breakdowns: list[LatencyBreakdown],
) -> dict[str, float]:
    """Analyze the latency overhead from T5 verification loops.

    The verification loop (Monitor + Evaluator) is expected to roughly
    double inference latency per iteration.

    Args:
        breakdowns: List of latency breakdowns with verification phases.

    Returns:
        Dictionary with verification overhead metrics.

    """
    verification_times = []
    inference_times = []

    for breakdown in breakdowns:
        for phase in breakdown.phases:
            if phase.phase == LatencyPhase.VERIFICATION:
                verification_times.append(phase.duration_ms)
            elif phase.phase == LatencyPhase.INFERENCE:
                inference_times.append(phase.duration_ms)

    if not verification_times or not inference_times:
        return {
            "verification_ms_mean": 0.0,
            "inference_ms_mean": 0.0,
            "overhead_ratio": 0.0,
            "overhead_percentage": 0.0,
        }

    verification_mean = sum(verification_times) / len(verification_times)
    inference_mean = sum(inference_times) / len(inference_times)

    # Overhead ratio: verification / inference
    ratio = verification_mean / inference_mean if inference_mean > 0 else 0.0

    # Overhead percentage: verification / (inference + verification)
    total = verification_mean + inference_mean
    percentage = (verification_mean / total * 100) if total > 0 else 0.0

    return {
        "verification_ms_mean": verification_mean,
        "inference_ms_mean": inference_mean,
        "overhead_ratio": ratio,
        "overhead_percentage": percentage,
    }
