"""Command-line interface for ProjectScylla.

Python justification: Click library for CLI parsing and subprocess orchestration.
"""

import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path

import click

from scylla.orchestrator import OrchestratorConfig, EvalOrchestrator
from scylla.reporting import (
    MarkdownReportGenerator,
    ReportData,
    RunResult,
    SensitivityAnalysis,
    TierMetrics,
    TransitionAssessment,
    create_tier_metrics,
)


@click.group()
@click.version_option(version="0.1.0", prog_name="scylla")
def cli() -> None:
    """ProjectScylla - AI Agent Testing Framework.

    Evaluate and benchmark AI agent architectures across multiple tiers.
    """
    pass


@cli.command()
@click.argument("test_id")
@click.option(
    "--tier",
    "-t",
    multiple=True,
    help="Tier(s) to run (e.g., T0, T1). Can be specified multiple times.",
)
@click.option(
    "--model",
    "-m",
    help="Run specific model only.",
)
@click.option(
    "--runs",
    "-r",
    default=10,
    type=int,
    help="Number of runs per tier (default: 10).",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    help="Override output directory.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Verbose output.",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Minimal output (for CI).",
)
def run(
    test_id: str,
    tier: tuple[str, ...],
    model: str | None,
    runs: int,
    output_dir: Path | None,
    verbose: bool,
    quiet: bool,
) -> None:
    """Run evaluation for a test case.

    TEST_ID is the identifier of the test to run (e.g., 001-justfile-to-makefile).

    Examples:

        scylla run 001-justfile-to-makefile

        scylla run 001-justfile-to-makefile --tier T0 --tier T1

        scylla run 001-justfile-to-makefile --model claude-opus-4-5 --runs 1
    """
    if verbose and quiet:
        raise click.UsageError("Cannot use --verbose and --quiet together.")

    tiers = list(tier) if tier else None  # None means use test defaults
    model_id = model or "claude-opus-4-5-20251101"  # Default model

    # Configure orchestrator
    base_path = output_dir.parent if output_dir else Path(".")
    config = OrchestratorConfig(
        base_path=base_path,
        runs_per_tier=runs,
        tiers=tiers,
        model=model_id,
        quiet=quiet,
        verbose=verbose,
    )

    orchestrator = EvalOrchestrator(config)

    try:
        if runs == 1 and tiers and len(tiers) == 1:
            # Single run mode
            result = orchestrator.run_single(
                test_id=test_id,
                model_id=model_id,
                tier_id=tiers[0],
            )
            if not quiet:
                click.echo(f"\nResult: {'PASS' if result.judgment.passed else 'FAIL'}")
                click.echo(f"Grade: {result.judgment.letter_grade}")
                click.echo(f"Cost: ${result.metrics.cost_usd:.4f}")
        else:
            # Multi-run mode
            results = orchestrator.run_test(
                test_id=test_id,
                models=[model_id],
                tiers=tiers,
                runs_per_tier=runs,
            )
            if not quiet:
                passed = sum(1 for r in results if r.judgment.passed)
                click.echo(f"\nCompleted {len(results)} runs")
                click.echo(f"Pass rate: {passed}/{len(results)}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _load_results(test_id: str, base_path: Path = Path(".")) -> list[dict]:
    """Load all result.json files for a test.

    Args:
        test_id: Test identifier
        base_path: Base path for runs directory

    Returns:
        List of result dictionaries
    """
    runs_dir = base_path / "runs" / test_id
    results = []

    if not runs_dir.exists():
        return results

    for result_file in runs_dir.rglob("result.json"):
        with open(result_file) as f:
            results.append(json.load(f))

    return results


def _calculate_tier_metrics(
    tier_id: str, results: list[dict], t0_pass_rate: float | None = None
) -> TierMetrics:
    """Calculate metrics for a tier from results.

    Args:
        tier_id: Tier identifier
        results: List of result dictionaries for this tier
        t0_pass_rate: T0 pass rate for uplift calculation

    Returns:
        TierMetrics for the tier
    """
    tier_names = {
        "T0": "Vanilla",
        "T1": "Prompted",
        "T2": "Skills",
        "T3": "Tooling",
        "T4": "Delegation",
        "T5": "Hierarchy",
        "T6": "Hybrid",
    }

    pass_rates = [r["grading"]["pass_rate"] for r in results]
    impl_rates = [r["judgment"]["impl_rate"] for r in results]
    composites = [r["grading"]["composite_score"] for r in results]
    costs = [r["grading"]["cost_of_pass"] for r in results]
    # Filter out infinity for cost median
    valid_costs = [c for c in costs if c != float("inf")]

    pass_rate_median = statistics.median(pass_rates)
    impl_rate_median = statistics.median(impl_rates)
    composite_median = statistics.median(composites)
    cost_median = statistics.median(valid_costs) if valid_costs else float("inf")
    consistency_std = statistics.stdev(pass_rates) if len(pass_rates) > 1 else 0.0

    # Calculate uplift vs T0
    uplift = 0.0
    if t0_pass_rate is not None and t0_pass_rate > 0:
        uplift = ((pass_rate_median - t0_pass_rate) / t0_pass_rate) * 100

    return create_tier_metrics(
        tier_id=tier_id,
        tier_name=tier_names.get(tier_id, tier_id),
        pass_rate_median=pass_rate_median,
        impl_rate_median=impl_rate_median,
        composite_median=composite_median,
        cost_of_pass_median=cost_median,
        consistency_std_dev=consistency_std,
        uplift=uplift,
    )


@cli.command()
@click.argument("test_id")
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["markdown", "json", "html"]),
    default="markdown",
    help="Report format (default: markdown).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file path.",
)
def report(
    test_id: str,
    output_format: str,
    output: Path | None,
) -> None:
    """Generate report for a completed test.

    TEST_ID is the identifier of the test (e.g., 001-justfile-to-makefile).

    Examples:

        scylla report 001-justfile-to-makefile

        scylla report 001-justfile-to-makefile --format json
    """
    click.echo(f"Generating {output_format} report for: {test_id}")

    base_path = Path(".")
    results = _load_results(test_id, base_path)

    if not results:
        click.echo(f"\nNo results found for test: {test_id}", err=True)
        click.echo("Run 'scylla run {test_id}' first to generate results.", err=True)
        sys.exit(1)

    click.echo(f"  Found {len(results)} run results")

    # Group results by tier
    by_tier: dict[str, list[dict]] = {}
    for r in results:
        tier_id = r["tier_id"]
        if tier_id not in by_tier:
            by_tier[tier_id] = []
        by_tier[tier_id].append(r)

    # Sort tiers
    sorted_tiers = sorted(by_tier.keys())

    # Calculate T0 pass rate for uplift calculations
    t0_pass_rate = None
    if "T0" in by_tier:
        t0_results = by_tier["T0"]
        t0_pass_rates = [r["grading"]["pass_rate"] for r in t0_results]
        t0_pass_rate = statistics.median(t0_pass_rates)

    # Calculate metrics for each tier
    tier_metrics = []
    for tier_id in sorted_tiers:
        metrics = _calculate_tier_metrics(tier_id, by_tier[tier_id], t0_pass_rate)
        tier_metrics.append(metrics)
        click.echo(f"  {tier_id}: {len(by_tier[tier_id])} runs, "
                   f"pass rate: {metrics.pass_rate_median:.1%}")

    # Calculate sensitivity analysis if multiple tiers
    sensitivity = None
    if len(tier_metrics) > 1:
        pass_rates = [m.pass_rate_median for m in tier_metrics]
        impl_rates = [m.impl_rate_median for m in tier_metrics]
        costs = [m.cost_of_pass_median for m in tier_metrics if m.cost_of_pass_median != float("inf")]

        sensitivity = SensitivityAnalysis(
            pass_rate_variance=statistics.variance(pass_rates) if len(pass_rates) > 1 else 0.0,
            impl_rate_variance=statistics.variance(impl_rates) if len(impl_rates) > 1 else 0.0,
            cost_variance=statistics.variance(costs) if len(costs) > 1 else 0.0,
        )

    # Calculate transitions
    transitions = []
    for i in range(len(tier_metrics) - 1):
        from_tier = tier_metrics[i]
        to_tier = tier_metrics[i + 1]

        pass_delta = to_tier.pass_rate_median - from_tier.pass_rate_median
        impl_delta = to_tier.impl_rate_median - from_tier.impl_rate_median
        cost_delta = to_tier.cost_of_pass_median - from_tier.cost_of_pass_median

        # Worth it if pass rate improves more than cost increases (relative)
        worth_it = pass_delta > 0 and (cost_delta < 0 or pass_delta > cost_delta)

        transitions.append(TransitionAssessment(
            from_tier=from_tier.tier_id,
            to_tier=to_tier.tier_id,
            pass_rate_delta=pass_delta,
            impl_rate_delta=impl_delta,
            cost_delta=cost_delta,
            worth_it=worth_it,
        ))

    # Determine runs per tier (from first tier's count)
    runs_per_tier = len(by_tier[sorted_tiers[0]]) if sorted_tiers else 0

    # Create report data
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    report_data = ReportData(
        test_id=test_id,
        test_name=test_id.replace("-", " ").title(),
        timestamp=timestamp,
        runs_per_tier=runs_per_tier,
        judge_model="claude-opus-4-5",
        tiers=tier_metrics,
        sensitivity=sensitivity,
        transitions=transitions,
        key_finding=f"Evaluated {len(results)} runs across {len(sorted_tiers)} tier(s).",
        recommendations=[
            "Review per-tier metrics to identify optimal configuration.",
            "Consider cost-of-pass when selecting production tier.",
        ],
    )

    # Generate report
    if output_format == "markdown":
        report_dir = output.parent if output else base_path / "reports"
        generator = MarkdownReportGenerator(report_dir)
        report_path = generator.write_report(report_data)
        click.echo(f"\nReport generated: {report_path}")
    else:
        click.echo(f"\n{output_format} format not yet implemented.", err=True)
        sys.exit(1)


@cli.command("list")
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed test information.",
)
def list_tests(verbose: bool) -> None:
    """List available test cases.

    Examples:

        scylla list

        scylla list --verbose
    """
    # TODO: Load from tests directory when available
    tests = [
        ("001-justfile-to-makefile", "Convert Justfile to Makefile"),
    ]

    click.echo("Available tests:\n")

    for test_id, description in tests:
        if verbose:
            click.echo(f"  {test_id}")
            click.echo(f"    Description: {description}")
            click.echo()
        else:
            click.echo(f"  {test_id}: {description}")


@cli.command("list-tiers")
def list_tiers() -> None:
    """List available evaluation tiers.

    Examples:

        scylla list-tiers
    """
    tiers = [
        ("T0", "Vanilla", "Base LLM with zero-shot prompting"),
        ("T1", "Prompted", "System prompts and chain-of-thought"),
        ("T2", "Skills", "Prompt-encoded domain expertise"),
        ("T3", "Tooling", "External function calling with JSON schemas"),
        ("T4", "Delegation", "Flat multi-agent systems"),
        ("T5", "Hierarchy", "Nested orchestration with self-correction"),
        ("T6", "Hybrid", "Optimal combinations of proven components"),
    ]

    click.echo("Evaluation tiers:\n")

    for tier_id, name, description in tiers:
        click.echo(f"  {tier_id} ({name})")
        click.echo(f"    {description}")
        click.echo()


@cli.command("list-models")
def list_models() -> None:
    """List configured models.

    Examples:

        scylla list-models
    """
    # TODO: Load from config when available
    models = [
        ("claude-opus-4-5-20251101", "Claude Opus 4.5", "$15.00/$75.00 per 1M tokens"),
        ("claude-sonnet-4-20250514", "Claude Sonnet 4", "$3.00/$15.00 per 1M tokens"),
    ]

    click.echo("Configured models:\n")

    for model_id, name, pricing in models:
        click.echo(f"  {model_id}")
        click.echo(f"    Name: {name}")
        click.echo(f"    Pricing: {pricing}")
        click.echo()


@cli.command()
@click.argument("test_id")
def status(test_id: str) -> None:
    """Show status of a test evaluation.

    TEST_ID is the identifier of the test (e.g., 001-justfile-to-makefile).

    Examples:

        scylla status 001-justfile-to-makefile
    """
    click.echo(f"Status for: {test_id}\n")

    # TODO: Load from results when available
    click.echo("  No results found.")
    click.echo("\n  Run 'scylla run {test_id}' to start evaluation.")


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
