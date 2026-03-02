"""Docker build timing utilities.

Shared helper functions used by both the CI script in docker-test.yml and the
unit tests in tests/unit/docker/test_docker_build_timing.py.

No Docker daemon required to import this module — all functions operate on
plain text (build log strings) or pure arithmetic.
"""

from __future__ import annotations


def count_cached_layers(build_log: str) -> int:
    """Count the number of CACHED layer lines in a docker build --progress=plain log.

    BuildKit emits ``#N CACHED`` lines for each layer that was restored from
    the local layer cache.  This count indicates how effective the cache was
    for a particular build.

    Args:
        build_log: Full stdout+stderr from ``docker build --progress=plain``.

    Returns:
        Number of lines that contain the word ``CACHED`` (case-insensitive).

    """
    return build_log.upper().count("CACHED")


def compute_reduction(cold_seconds: int, warm_seconds: int) -> float:
    """Compute the percentage reduction in build time from cold to warm build.

    Args:
        cold_seconds: Wall-clock seconds for the cold (no-cache) build.
        warm_seconds: Wall-clock seconds for the warm (source-change) rebuild.

    Returns:
        Percentage reduction, rounded to one decimal place.
        Returns 0.0 if *cold_seconds* is zero to avoid division by zero.

    """
    if cold_seconds <= 0:
        return 0.0
    reduction = (cold_seconds - warm_seconds) / cold_seconds * 100
    return round(reduction, 1)


def build_summary_table(
    cold_seconds: int,
    warm_seconds: int,
    cached_layers: int,
    reduction: float,
) -> str:
    """Render a Markdown table summarising the before/after build timing.

    The table is written to ``$GITHUB_STEP_SUMMARY`` by the CI report step so
    it appears as a structured summary in the GitHub Actions UI.

    Args:
        cold_seconds: Wall-clock seconds for the cold build.
        warm_seconds: Wall-clock seconds for the warm rebuild.
        cached_layers: Number of ``CACHED`` layers in the warm build log.
        reduction: Percentage time reduction (from :func:`compute_reduction`).

    Returns:
        Markdown string containing the full summary table.

    """
    verdict = "PASS" if reduction >= 30 else "FAIL"
    return (
        "## Docker Build Timing: Source-Only Change Cache Efficiency\n\n"
        "| Metric | Value |\n"
        "|--------|-------|\n"
        f"| Cold build (no cache) | {cold_seconds}s |\n"
        f"| Warm rebuild (source change only) | {warm_seconds}s |\n"
        f"| Reduction | {reduction}% |\n"
        f"| Cached layers (warm build) | {cached_layers} |\n"
        f"| Acceptance criterion (≥30%) | {verdict} |\n"
    )
