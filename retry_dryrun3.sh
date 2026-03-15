#!/usr/bin/env bash
set -uo pipefail

RESULTS_DIR=~/dryrun3
THREADS=2
FAILED_TESTS=()

# Full-ablation tests: run all subtests (no cap)
FULL_ABLATION_TESTS=(test-001 test-002 test-003)

# Standard tests: run with 3 subtests per tier
STANDARD_TESTS=(
    test-004 test-005 test-006 test-007 test-008 test-009 test-010
    test-011 test-012 test-013 test-014 test-015 test-016 test-017
    test-018 test-019 test-020 test-021 test-022 test-023 test-024
    test-025 test-026 test-027 test-028 test-029 test-030 test-031
    test-032 test-033 test-034 test-035 test-036 test-037 test-038
    test-039 test-040 test-041 test-042 test-043 test-044 test-045
    test-046 test-047
)

# Pre-run analysis
echo "=== PRE-RUN STATUS ==="
pixi run python scripts/analyze_dryrun3.py --results-dir "$RESULTS_DIR" || true
echo ""

echo "=== dryrun3 retry: full-ablation tests (all subtests) ==="
for test in "${FULL_ABLATION_TESTS[@]}"; do
    echo "--- $test ---"
    if ! pixi run python scripts/manage_experiment.py run \
        --config "tests/fixtures/tests/$test" \
        --results-dir "$RESULTS_DIR" \
        --threads "$THREADS" \
        --parallel 1 \
        --max-subtests 50 \
        -v; then
        FAILED_TESTS+=("$test")
        echo "WARNING: $test exited with non-zero status"
    fi
done

echo "=== dryrun3 retry: standard tests (max-subtests=3) ==="
for test in "${STANDARD_TESTS[@]}"; do
    echo "--- $test ---"
    if ! pixi run python scripts/manage_experiment.py run \
        --config "tests/fixtures/tests/$test" \
        --max-subtests 3 \
        --results-dir "$RESULTS_DIR" \
        --threads "$THREADS" \
        --parallel 1 \
        -v; then
        FAILED_TESTS+=("$test")
        echo "WARNING: $test exited with non-zero status"
    fi
done

# Summary of any manage_experiment errors
if [ ${#FAILED_TESTS[@]} -gt 0 ]; then
    echo ""
    echo "=== TESTS WITH MANAGE_EXPERIMENT ERRORS: ${FAILED_TESTS[*]} ==="
fi

# Post-run analysis + Go/NoGo
echo ""
echo "=== POST-RUN STATUS ==="
pixi run python scripts/analyze_dryrun3.py --results-dir "$RESULTS_DIR"
