#!/usr/bin/env python3
"""E2E test runner for T0 and T1 tier validation.

Python justification: Required for subprocess orchestration and CLI integration.

This script runs an initial E2E test with T0 (Vanilla) and T1 (Prompted) tiers
to verify the framework outputs and identify improvements.

Usage:
    python scripts/run_e2e_t0_t1.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scylla.adapters.base import AdapterConfig, AdapterResult
from scylla.adapters.claude_code import ClaudeCodeAdapter
from scylla.executor.tier_config import TierConfigLoader
from scylla.orchestrator import EvalOrchestrator, OrchestratorConfig

if TYPE_CHECKING:
    from scylla.config import EvalCase, Rubric


def create_adapter_wrapper():
    """Create adapter wrapper that bridges ClaudeCodeAdapter to orchestrator interface."""
    adapter = ClaudeCodeAdapter()
    # Use the main config directory which has the full tiers.yaml
    tier_loader = TierConfigLoader(Path("config"))

    def adapter_func(
        workspace: Path,
        test_case: EvalCase,
        model_id: str,
        tier_id: str,
    ) -> dict:
        """Wrapper that adapts ClaudeCodeAdapter to orchestrator interface."""
        # Get prompt file path
        test_dir = Path("tests/fixtures/tests") / test_case.id
        prompt_file = test_dir / "prompt.md"

        # Get tier config
        tier_config = tier_loader.get_tier(tier_id) if tier_id != "T0" else None

        # Create output directory
        output_dir = workspace / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Build adapter config
        config = AdapterConfig(
            model=model_id,
            prompt_file=prompt_file,
            workspace=workspace,
            output_dir=output_dir,
            timeout=300,  # 5 minutes for validation
        )

        # Capture the final prompt (for logging)
        task_prompt = adapter.load_prompt(prompt_file)
        final_prompt = adapter.inject_tier_prompt(task_prompt, tier_config)

        # Run adapter
        result = adapter.run(config, tier_config)

        # Convert to dict format expected by orchestrator
        return {
            "tokens_in": result.tokens_input,
            "tokens_out": result.tokens_output,
            "cost_usd": result.cost_usd,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "api_calls": result.api_calls,
            "final_prompt": final_prompt,  # Include for logging
        }

    return adapter_func


def create_simple_judge():
    """Create a simple judge for initial validation."""

    def judge_func(
        workspace: Path,
        test_case: EvalCase,
        rubric: Rubric,
        execution_result: dict,
    ) -> dict:
        """Simple judge that checks for hello.py creation and output."""
        passed = False
        score = 0.0
        grade = "F"
        reasoning = ""

        # Check 1: Did the agent exit cleanly?
        exit_code = execution_result.get("exit_code", -1)
        if exit_code != 0:
            reasoning = f"Agent exited with code {exit_code}"
            return {
                "passed": False,
                "score": 0.0,
                "grade": "F",
                "reasoning": reasoning,
            }

        # Check 2: Was hello.py created?
        hello_file = workspace / "hello.py"
        if not hello_file.exists():
            reasoning = "hello.py was not created"
            return {
                "passed": False,
                "score": 0.3,
                "grade": "F",
                "reasoning": reasoning,
            }

        # Check 3: Does hello.py produce correct output?
        try:
            result = subprocess.run(
                ["python", str(hello_file)],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=workspace,
            )
            output = result.stdout.strip()

            if output == "Hello, World!":
                passed = True
                score = 1.0
                grade = "A"
                reasoning = "All requirements met: file created and output correct"
            elif "hello" in output.lower() and "world" in output.lower():
                passed = True
                score = 0.8
                grade = "B"
                reasoning = "File created with similar output"
            else:
                passed = False
                score = 0.5
                grade = "D"
                reasoning = f"File created but output incorrect: {output!r}"

        except subprocess.TimeoutExpired:
            reasoning = "Script execution timed out"
            score = 0.4
            grade = "F"
        except Exception as e:
            reasoning = f"Script execution failed: {e}"
            score = 0.3
            grade = "F"

        return {
            "passed": passed,
            "score": score,
            "grade": grade,
            "reasoning": reasoning,
        }

    return judge_func


def check_prerequisites():
    """Check that prerequisites are in place."""
    # Check claude CLI is available
    try:
        result = subprocess.run(
            ["which", "claude"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print("ERROR: 'claude' CLI not found in PATH")
            print("Please install Claude Code: https://claude.ai/code")
            return False
    except Exception as e:
        print(f"ERROR: Could not check for claude CLI: {e}")
        return False

    # Check prompt file exists
    prompt_file = Path("tests/fixtures/tests/test-001/prompt.md")
    if not prompt_file.exists():
        print(f"ERROR: Prompt file not found: {prompt_file}")
        return False

    # Check tier config exists
    config_tiers = Path("config/tiers/tiers.yaml")
    if not config_tiers.exists():
        print(f"ERROR: Tier configuration not found: {config_tiers}")
        return False

    print("✓ Prerequisites check passed")
    return True


def run_e2e_validation():
    """Run E2E validation for T0 and T1 tiers."""
    print("\n" + "="*60)
    print("ProjectScylla E2E Validation - T0/T1 Tiers")
    print("="*60 + "\n")

    # Check prerequisites
    if not check_prerequisites():
        sys.exit(1)

    # Configuration
    base_path = Path("tests/fixtures")
    test_id = "test-001"
    model_id = "claude-sonnet-4-20250514"
    tiers = ["T0", "T1"]

    # Create orchestrator
    config = OrchestratorConfig(
        base_path=base_path,
        runs_per_tier=1,  # Single run for validation
        tiers=tiers,
        quiet=False,
        verbose=True,
    )

    orchestrator = EvalOrchestrator(config)

    # Set adapter and judge
    orchestrator.set_adapter(create_adapter_wrapper())
    orchestrator.set_judge(create_simple_judge())

    print(f"Running test: {test_id}")
    print(f"Model: {model_id}")
    print(f"Tiers: {tiers}")
    print(f"Runs per tier: 1")
    print("\n" + "-"*40 + "\n")

    # Run the test
    try:
        results = orchestrator.run_test(
            test_id=test_id,
            models=[model_id],
            tiers=tiers,
            runs_per_tier=1,
        )
    except Exception as e:
        print(f"\nERROR: Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Print summary
    print("\n" + "="*60)
    print("RESULTS SUMMARY")
    print("="*60 + "\n")

    for result in results:
        status = "✓ PASS" if result.judgment.passed else "✗ FAIL"
        print(f"Tier {result.tier_id}: {status}")
        print(f"  Grade: {result.judgment.letter_grade}")
        print(f"  Impl Rate: {result.judgment.impl_rate:.2f}")
        print(f"  Cost: ${result.metrics.cost_usd:.4f}")
        print(f"  Tokens: {result.metrics.tokens_input} in / {result.metrics.tokens_output} out")
        print(f"  Duration: {result.execution.duration_seconds:.2f}s")
        print()

    # Calculate tier comparison
    if len(results) == 2:
        t0_result = results[0]
        t1_result = results[1]

        print("-"*40)
        print("TIER COMPARISON (T1 vs T0)")
        print("-"*40)

        # Pass rate difference
        pass_diff = t1_result.grading.pass_rate - t0_result.grading.pass_rate
        print(f"Pass Rate Δ: {pass_diff:+.2f}")

        # Cost difference
        cost_diff = t1_result.metrics.cost_usd - t0_result.metrics.cost_usd
        print(f"Cost Δ: ${cost_diff:+.4f}")

        # Cost of Pass comparison
        t0_cop = t0_result.grading.cost_of_pass
        t1_cop = t1_result.grading.cost_of_pass
        print(f"Cost-of-Pass T0: ${t0_cop:.4f}")
        print(f"Cost-of-Pass T1: ${t1_cop:.4f}")

        # Recommendation
        print("\n" + "-"*40)
        print("RECOMMENDATIONS")
        print("-"*40)

        if t0_result.judgment.passed and t1_result.judgment.passed:
            if t0_cop < t1_cop:
                print("→ T0 is more cost-effective (lower CoP)")
            else:
                print("→ T1 is more cost-effective (lower CoP)")
        elif t0_result.judgment.passed and not t1_result.judgment.passed:
            print("→ T0 outperforms T1 (T1 failed)")
        elif t1_result.judgment.passed and not t0_result.judgment.passed:
            print("→ T1 outperforms T0 (T0 failed)")
        else:
            print("→ Both tiers failed - investigate task or prompts")

    print("\n" + "="*60)
    print("E2E Validation Complete")
    print("="*60 + "\n")

    # Return exit code based on results
    return 0 if all(r.judgment.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(run_e2e_validation())
