#!/usr/bin/env python3
"""Validation script for container integration.

This script runs a minimal E2E test with container execution enabled
to validate the AgentContainerManager integration.

Test Configuration:
- Tier: T0 (empty prompt)
- Subtests: 1 (first T0 subtest only)
- Runs per subtest: 1
- Judge models: 1 (claude-opus-4-5)
- Containers: ENABLED

Usage:
    python scripts/validate_container_integration.py [--verbose]

Options:
    --verbose: Enable DEBUG logging to see Docker container logs
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from scylla.e2e.models import ExperimentConfig, TierID  # noqa: E402
from scylla.e2e.runner import E2ERunner  # noqa: E402

logger = logging.getLogger(__name__)


def main() -> int:
    """Run minimal container validation test.

    Returns:
        0 on success, 1 on failure

    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Validate container integration with minimal E2E test"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable DEBUG logging to see Docker container logs",
    )
    args = parser.parse_args()

    # Configure logging based on verbose flag
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("=" * 80)
    logger.info("Container Integration Validation Test")
    logger.info("=" * 80)
    if args.verbose:
        logger.info("Verbose mode: ENABLED (Docker container logs will be shown)")
    logger.info("")

    # Use test-001 fixture
    test_dir = project_root / "tests/fixtures/tests/test-001"
    if not test_dir.exists():
        logger.error(f"Test fixture not found: {test_dir}")
        return 1

    # Create minimal experiment configuration with containers enabled
    config = ExperimentConfig(
        experiment_id="container-validation-test",
        task_repo="https://github.com/mvillmow/Hello-World",
        task_commit="7fd1a60b01f91b314f59955a4e4d4e80d8edf11d",
        task_prompt_file=test_dir / "prompt.md",
        language="python",
        models=["claude-sonnet-4-5-20250929"],
        runs_per_subtest=1,  # Just 1 run for quick validation
        tiers_to_run=[TierID.T0],  # Just T0
        judge_models=["claude-opus-4-5-20251101"],  # Single judge
        parallel_subtests=1,
        timeout_seconds=300,
        max_turns=None,
        max_subtests=1,  # Just 1 subtest for quick validation
        use_containers=True,  # ENABLE CONTAINERS
    )

    logger.info("")
    logger.info("Configuration:")
    logger.info(f"  Tiers: {[t.value for t in config.tiers_to_run]}")
    logger.info(f"  Subtests per tier: {config.max_subtests}")
    logger.info(f"  Runs per subtest: {config.runs_per_subtest}")
    logger.info(f"  Judge models: {config.judge_models}")
    logger.info(f"  Container execution: {config.use_containers}")
    logger.info("")

    # Create results directory
    results_dir = project_root / "results" / "container-validation"
    results_dir.mkdir(parents=True, exist_ok=True)

    try:
        logger.info("Initializing E2E runner...")
        runner = E2ERunner(
            config=config,
            results_dir=results_dir,
        )

        logger.info("Starting test execution...")
        logger.info("")
        results = runner.run()

        logger.info("")
        logger.info("=" * 80)
        logger.info("Test Results")
        logger.info("=" * 80)

        if results:
            for tier_id, tier_result in results.items():
                logger.info(f"\nTier: {tier_id.value}")
                logger.info(f"  Best subtest: {tier_result.best_subtest}")
                logger.info(f"  Best score: {tier_result.best_subtest_score:.2f}")
                logger.info(f"  Total cost: ${tier_result.total_cost:.4f}")
                logger.info(f"  Total duration: {tier_result.total_duration:.2f}s")

                if tier_result.best_subtest:
                    best = tier_result.subtest_results[tier_result.best_subtest]
                    logger.info(f"\n  Best Subtest Details ({tier_result.best_subtest}):")
                    logger.info(f"    Pass rate: {best.pass_rate:.2%}")
                    logger.info(f"    Mean score: {best.mean_score:.2f}")
                    logger.info(f"    Mean cost: ${best.mean_cost:.4f}")

        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ Container validation test PASSED")
        logger.info("=" * 80)
        logger.info(f"\nResults saved to: {results_dir}")

        return 0

    except Exception as e:
        logger.error("")
        logger.error("=" * 80)
        logger.error("❌ Container validation test FAILED")
        logger.error("=" * 80)
        logger.error(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
