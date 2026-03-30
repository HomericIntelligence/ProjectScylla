#!/usr/bin/env bash
# =============================================================================
# Haiku Paper Experiment Runner
# 3-stage execution: Agent → Commit/Promote → Judge
# Tests: test-001, test-002, test-003
# Agent: claude-haiku-4-5
# Judges: claude-opus-4-6, claude-sonnet-4-6, claude-haiku-4-5
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TESTS=("test-001" "test-002" "test-003")
TIERS="T0 T1 T2 T3 T4 T5 T6"
RUNS=3
AGENT_MODEL="claude-haiku-4-5"
PRIMARY_JUDGE="claude-opus-4-6"
RESULTS_DIR="${RESULTS_DIR:-results}"
OFF_PEAK="${OFF_PEAK:---off-peak}"  # set OFF_PEAK="" to disable

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
preflight() {
    echo "=== Pre-flight checks ==="
    local fail=0

    # Verify claude CLI is available (agents run via claude code, not API key)
    if ! command -v claude &>/dev/null; then
        echo "FAIL: claude CLI not found in PATH"
        fail=1
    else
        echo "  OK: claude CLI found"
    fi

    if ! command -v pixi &>/dev/null; then
        echo "FAIL: pixi not found in PATH"
        fail=1
    else
        echo "  OK: pixi found"
    fi

    for test_id in "${TESTS[@]}"; do
        local test_dir="tests/fixtures/tests/${test_id}"
        if [[ ! -d "$test_dir" ]]; then
            echo "FAIL: Test directory not found: ${test_dir}"
            fail=1
        else
            echo "  OK: ${test_dir} exists"
        fi
    done

    local avail
    avail=$(df --output=avail -BG . | tail -1 | tr -d ' G')
    if (( avail < 10 )); then
        echo "WARN: Only ${avail}G free disk space (recommend 10G+)"
    else
        echo "  OK: ${avail}G free disk space"
    fi

    echo "  OK: Git status clean: $(git status --short | wc -l) uncommitted files"

    if (( fail )); then
        echo ""
        echo "Pre-flight FAILED. Fix the issues above and re-run."
        exit 1
    fi
    echo "=== Pre-flight PASSED ==="
    echo ""
}

# ---------------------------------------------------------------------------
# Run a single stage for a single test
# ---------------------------------------------------------------------------
run_stage() {
    local test_id="$1"
    local stage="$2"
    local config_dir="tests/fixtures/tests/${test_id}"

    local common_args=(
        --config "$config_dir"
        --tiers $TIERS
        --runs "$RUNS"
        --model "$AGENT_MODEL"
        --judge-model "$PRIMARY_JUDGE"
        --add-judge claude-sonnet-4-6
        --add-judge claude-haiku-4-5
        --results-dir "$RESULTS_DIR"
        -v
    )

    case "$stage" in
        1)
            echo "[$test_id] Stage 1: Agent execution (10 concurrent agents)"
            pixi run python scripts/manage_experiment.py run \
                "${common_args[@]}" \
                --max-concurrent-agents 10 \
                --until agent_complete \
                ${OFF_PEAK}
            ;;
        2)
            echo "[$test_id] Stage 2: Commit + Diff + Promote (2 concurrent agents)"
            pixi run python scripts/manage_experiment.py run \
                "${common_args[@]}" \
                --max-concurrent-agents 2 \
                --until promoted_to_completed
            ;;
        3)
            echo "[$test_id] Stage 3: Judging + Finalization (5 concurrent agents)"
            pixi run python scripts/manage_experiment.py run \
                "${common_args[@]}" \
                --max-concurrent-agents 5 \
                ${OFF_PEAK}
            ;;
        *)
            echo "Unknown stage: $stage"
            exit 1
            ;;
    esac
}

# ---------------------------------------------------------------------------
# Verify stage completion
# ---------------------------------------------------------------------------
verify_stage() {
    local test_id="$1"
    local expected_state="$2"

    echo ""
    echo "[$test_id] Verifying runs reached: ${expected_state}"

    pixi run python -c "
import json, sys
from pathlib import Path

results = Path('${RESULTS_DIR}')
# Find the most recent experiment directory for this test
candidates = sorted(results.glob('*${test_id}*'), key=lambda p: p.name, reverse=True)
if not candidates:
    print('  WARNING: No experiment directory found for ${test_id}')
    sys.exit(0)

cp_path = candidates[0] / 'checkpoint.json'
if not cp_path.exists():
    print(f'  WARNING: No checkpoint at {cp_path}')
    sys.exit(0)

cp = json.loads(cp_path.read_text())
total = 0
at_target = 0
issues = []
for tier, subtests in cp.get('run_states', {}).items():
    for st, runs in subtests.items():
        for run, state in runs.items():
            total += 1
            if state == '${expected_state}':
                at_target += 1
            elif state in ('failed', 'rate_limited'):
                issues.append(f'  FAILED: {tier}/{st}/{run} is {state}')
            else:
                issues.append(f'  WARN:   {tier}/{st}/{run} is {state} (expected ${expected_state})')

print(f'  Runs: {at_target}/{total} at ${expected_state}')
if issues:
    for i in issues[:10]:
        print(i)
    if len(issues) > 10:
        print(f'  ... and {len(issues) - 10} more')
    sys.exit(1)
else:
    print('  ALL RUNS OK')
"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    local stage="${1:-all}"

    preflight

    case "$stage" in
        1)
            for test_id in "${TESTS[@]}"; do
                run_stage "$test_id" 1
                verify_stage "$test_id" "agent_complete"
            done
            echo ""
            echo "=== Stage 1 complete. Run: $0 2 ==="
            ;;
        2)
            for test_id in "${TESTS[@]}"; do
                run_stage "$test_id" 2
                verify_stage "$test_id" "promoted_to_completed"
            done
            echo ""
            echo "=== Stage 2 complete. Run: $0 3 ==="
            ;;
        3)
            for test_id in "${TESTS[@]}"; do
                run_stage "$test_id" 3
                verify_stage "$test_id" "worktree_cleaned"
            done
            echo ""
            echo "=== Stage 3 complete. Experiment finished! ==="
            ;;
        all)
            echo "Running all 3 stages sequentially..."
            echo ""
            for s in 1 2 3; do
                for test_id in "${TESTS[@]}"; do
                    run_stage "$test_id" "$s"
                done
                echo ""
                echo "=== Stage $s complete ==="
                echo ""
            done
            echo "=== All stages complete. Experiment finished! ==="
            ;;
        verify)
            echo "Verifying final state..."
            for test_id in "${TESTS[@]}"; do
                verify_stage "$test_id" "worktree_cleaned"
            done
            ;;
        *)
            echo "Usage: $0 [1|2|3|all|verify]"
            echo ""
            echo "  1       Stage 1: Agent execution (10 threads)"
            echo "  2       Stage 2: Commit + Promote (2 threads)"
            echo "  3       Stage 3: Judging (5 threads)"
            echo "  all     Run all 3 stages sequentially"
            echo "  verify  Check final experiment state"
            echo ""
            echo "Environment variables:"
            echo "  (Agents run via claude CLI — no API key needed)"
            echo "  RESULTS_DIR         Results directory (default: results)"
            echo "  OFF_PEAK            Set to '' to disable off-peak waiting"
            exit 1
            ;;
    esac
}

main "$@"
