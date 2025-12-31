"""Command-line interface for ProjectScylla.

Python justification: Click library for CLI parsing and subprocess orchestration.
"""

import sys
from pathlib import Path

import click

from scylla.orchestrator import OrchestratorConfig, TestOrchestrator


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

    orchestrator = TestOrchestrator(config)

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
                click.echo(f"Grade: {result.grading.grade}")
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

    if output:
        click.echo(f"  Output: {output}")

    # TODO: Integrate with report generator when available
    click.echo("\nReport generation not yet implemented.")
    click.echo("This CLI provides the interface structure.")


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
