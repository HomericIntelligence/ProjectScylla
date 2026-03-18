#!/usr/bin/env bash
set -uo pipefail

RESULTS_DIR=~/fullruns/haiku-2
THREADS=2
FAILED_TESTS=()

# All tests: run all subtests, 5 runs each, 3 judges (haiku, sonnet, opus)
ALL_TESTS=(
    test-001 test-002 test-003 test-004 test-005 test-006 test-007
    test-008 test-009 test-010 test-011 test-012 test-013 test-014
    test-015 test-016 test-017 test-018 test-019 test-020 test-021
    test-022 test-023 test-024 test-025 test-026 test-027 test-028
    test-029 test-030 test-031 test-032 test-033 test-034 test-035
    test-036 test-037 test-038 test-039 test-040 test-041 test-042
    test-043 test-044 test-045 test-046 test-047
)

# Pre-run analysis
echo "=== PRE-RUN STATUS ==="
pixi run python scripts/analyze_dryrun3.py --results-dir "$RESULTS_DIR" || true
echo ""

echo "=== dryrun3: all tests, 5 runs, 3 judges (haiku+sonnet+opus) ==="
for test in "${ALL_TESTS[@]}"; do
    echo "--- $test ---"
    if ! pixi run python scripts/manage_experiment.py run \
        --config "tests/fixtures/tests/$test" \
        --results-dir "$RESULTS_DIR" \
        --threads "$THREADS" \
        --parallel 1 \
        --runs 5 \
        --max-subtests 50 \
        --model claude-haiku-4-5-20251001 \
        --judge-model claude-haiku-4-5-20251001 \
        --add-judge claude-sonnet-4-5-20250514 \
        --add-judge claude-opus-4-20250514 \
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
