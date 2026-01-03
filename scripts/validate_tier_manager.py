#!/usr/bin/env python3
"""Validate that tier_manager loads subtests correctly from shared directory.

This script tests the centralized subtest loading after the migration.

Usage:
    python scripts/validate_tier_manager.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scylla.e2e.tier_manager import TierManager
from scylla.e2e.models import TierID


def validate_tier_manager() -> bool:
    """Validate that tier_manager loads subtests from shared directory."""
    print("=" * 60)
    print("Validating TierManager with centralized shared subtests")
    print("=" * 60)

    # Use test-001 as the tiers directory (it now only has test.yaml and expected/)
    test_dir = Path(__file__).parent.parent / "tests" / "fixtures" / "tests" / "test-001"
    shared_dir = Path(__file__).parent.parent / "tests" / "claude-code" / "shared"

    print(f"\nTest directory: {test_dir}")
    print(f"Shared directory: {shared_dir}")

    if not test_dir.exists():
        print(f"ERROR: Test directory not found: {test_dir}")
        return False

    if not shared_dir.exists():
        print(f"ERROR: Shared directory not found: {shared_dir}")
        return False

    # Verify shared subtests exist
    subtests_dir = shared_dir / "subtests"
    if not subtests_dir.exists():
        print(f"ERROR: Subtests directory not found: {subtests_dir}")
        return False

    # Count shared subtests
    print("\n--- Shared Subtests Directory ---")
    total_shared = 0
    for tier in ["t0", "t1", "t2", "t3", "t4", "t5", "t6"]:
        tier_dir = subtests_dir / tier
        if tier_dir.exists():
            count = len(list(tier_dir.glob("*.yaml")))
            print(f"  {tier.upper()}: {count} subtests")
            total_shared += count
    print(f"  Total: {total_shared} shared subtest configs")

    # Initialize TierManager with test-001 as tiers_dir
    manager = TierManager(test_dir)

    # Test loading each tier
    print("\n--- Loading Tiers via TierManager ---")
    all_passed = True
    expected_counts = {
        TierID.T0: 24,
        TierID.T1: 10,
        TierID.T2: 15,
        TierID.T3: 41,
        TierID.T4: 7,
        TierID.T5: 15,
        TierID.T6: 1,
    }

    for tier_id, expected_count in expected_counts.items():
        try:
            tier_config = manager.load_tier_config(tier_id)
            actual_count = len(tier_config.subtests)

            if actual_count == expected_count:
                status = "PASS"
            elif actual_count > 0:
                status = "WARN"  # Got some but not expected count
            else:
                status = "FAIL"
                all_passed = False

            print(f"  {tier_id.value}: {actual_count} subtests (expected {expected_count}) [{status}]")

            # Show first few subtests for verification
            if tier_config.subtests:
                subtest_names = [s.name for s in tier_config.subtests[:3]]
                print(f"       Sample: {', '.join(subtest_names)}")

        except Exception as e:
            print(f"  {tier_id.value}: ERROR - {e}")
            all_passed = False

    # Test specific subtest loading
    print("\n--- Validating Subtest Properties ---")

    # T0/00-empty should have no blocks
    t0_config = manager.load_tier_config(TierID.T0)
    empty_subtest = next((s for s in t0_config.subtests if s.id == "00"), None)
    if empty_subtest:
        has_empty_blocks = empty_subtest.resources.get("claude_md", {}).get("blocks", []) == []
        print(f"  T0/00-empty has empty blocks: {has_empty_blocks} [{'PASS' if has_empty_blocks else 'FAIL'}]")
        if not has_empty_blocks:
            all_passed = False
    else:
        print("  T0/00-empty: NOT FOUND [FAIL]")
        all_passed = False

    # T1/04-github should have github skill category
    t1_config = manager.load_tier_config(TierID.T1)
    github_subtest = next((s for s in t1_config.subtests if s.id == "04"), None)
    if github_subtest:
        categories = github_subtest.resources.get("skills", {}).get("categories", [])
        has_github = "github" in categories
        print(f"  T1/04-github has github skill category: {has_github} [{'PASS' if has_github else 'FAIL'}]")
        if not has_github:
            all_passed = False
    else:
        print("  T1/04-github: NOT FOUND [FAIL]")
        all_passed = False

    # T3/05-algorithm-review-specialist should have L3 agents
    t3_config = manager.load_tier_config(TierID.T3)
    algo_subtest = next((s for s in t3_config.subtests if s.id == "05"), None)
    if algo_subtest:
        levels = algo_subtest.resources.get("agents", {}).get("levels", [])
        has_l3 = 3 in levels
        print(f"  T3/05-algorithm has L3 agent level: {has_l3} [{'PASS' if has_l3 else 'FAIL'}]")
        if not has_l3:
            all_passed = False
    else:
        print("  T3/05-algorithm: NOT FOUND [FAIL]")
        all_passed = False

    # Verify test-specific tier directories are gone
    print("\n--- Verifying Per-Test Tier Dirs Removed ---")
    for tier in ["t0", "t1", "t2", "t3", "t4", "t5", "t6"]:
        tier_dir = test_dir / tier
        if tier_dir.exists():
            print(f"  {tier}: EXISTS (should be deleted) [FAIL]")
            all_passed = False
        else:
            print(f"  {tier}: Removed [PASS]")

    print("\n" + "=" * 60)
    if all_passed:
        print("VALIDATION PASSED - TierManager loads from shared correctly")
    else:
        print("VALIDATION FAILED - Some checks did not pass")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    success = validate_tier_manager()
    sys.exit(0 if success else 1)
