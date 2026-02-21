#!/usr/bin/env bash
#
# Tests for preflight_check.sh Check 3 — PR-to-issue matching via closingIssuesReferences.
#
# Verifies that Check 3 uses authoritative closing references rather than
# free-text search, preventing false positives from PRs that mention an issue
# number in their title or body without formally closing it.
#
# Usage:
#   bash tests/test_preflight_check.sh
#
# Exit codes:
#   0 = all tests passed
#   1 = one or more tests failed

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFLIGHT="${SCRIPT_DIR}/../scripts/preflight_check.sh"

PASS_COUNT=0
FAIL_COUNT=0

pass_test() { echo "[PASS] $1"; ((PASS_COUNT++)); }
fail_test() { echo "[FAIL] $1"; ((FAIL_COUNT++)); }

# Strip ANSI color codes from a string.
# SC2001 is suppressed: bash parameter expansion cannot match \x1b hex escapes.
# shellcheck disable=SC2001
strip_ansi() { echo "$1" | sed 's/\x1b\[[0-9;]*m//g'; }

# ---------------------------------------------------------------------------
# run_preflight <issue> <mock_body>
# Runs preflight_check.sh in a subshell with the given gh mock functions.
# Sets global LAST_OUTPUT (stripped of ANSI) and LAST_EXIT.
# ---------------------------------------------------------------------------
run_preflight() {
    local issue="$1"
    local mock_body="$2"
    local raw
    raw=$(bash -c "
        ${mock_body}
        export -f gh
        bash '${PREFLIGHT}' '${issue}' 2>&1
    " 2>&1) || true
    LAST_EXIT=$?
    LAST_OUTPUT=$(strip_ansi "$raw")
}

# Re-run and capture exit code properly (strip_ansi in pipeline loses it)
run_preflight_with_exit() {
    local issue="$1"
    local mock_body="$2"
    local tmpfile
    tmpfile=$(mktemp)
    bash -c "
        ${mock_body}
        export -f gh
        bash '${PREFLIGHT}' '${issue}' 2>&1
    " > "$tmpfile" 2>&1
    LAST_EXIT=$?
    LAST_OUTPUT=$(strip_ansi "$(cat "$tmpfile")")
    rm -f "$tmpfile"
}

# ---------------------------------------------------------------------------
# Test 1: No PRs exist → PASS (exit 0)
# ---------------------------------------------------------------------------
t1_mock=$(cat <<'EOF'
gh() {
    case "$1 $2" in
        "issue view")
            echo '{"state":"OPEN","title":"Test Issue","closedAt":null}'
            ;;
        "pr list")
            echo '[]'
            ;;
        "pr view")
            echo ''
            ;;
    esac
}
EOF
)

run_preflight_with_exit "735" "$t1_mock"
if echo "$LAST_OUTPUT" | grep -q "\[PASS\] Check 3:" && [[ $LAST_EXIT -eq 0 ]]; then
    pass_test "Test 1: No PRs → PASS exit 0"
else
    fail_test "Test 1: No PRs → expected PASS+exit0, got exit=${LAST_EXIT}: $(echo "$LAST_OUTPUT" | grep -E 'Check 3')"
fi

# ---------------------------------------------------------------------------
# Test 2: MERGED PR with closingIssuesReferences = [735] → STOP (exit 1)
# ---------------------------------------------------------------------------
t2_mock=$(cat <<'EOF'
gh() {
    case "$1 $2" in
        "issue view")
            echo '{"state":"OPEN","title":"Test Issue","closedAt":null}'
            ;;
        "pr list")
            echo '[{"number":42,"title":"Fix the bug","state":"MERGED"}]'
            ;;
        "pr view")
            echo '735'
            ;;
    esac
}
EOF
)

run_preflight_with_exit "735" "$t2_mock"
if echo "$LAST_OUTPUT" | grep -q "\[STOP\] Check 3:" && [[ $LAST_EXIT -eq 1 ]]; then
    pass_test "Test 2: MERGED PR with closingIssuesReferences=[735] → STOP exit 1"
else
    fail_test "Test 2: expected STOP+exit1, got exit=${LAST_EXIT}: $(echo "$LAST_OUTPUT" | grep -E 'Check 3')"
fi

# ---------------------------------------------------------------------------
# Test 3: OPEN PR with closingIssuesReferences = [735] → WARN (exit 0)
# ---------------------------------------------------------------------------
t3_mock=$(cat <<'EOF'
gh() {
    case "$1 $2" in
        "issue view")
            echo '{"state":"OPEN","title":"Test Issue","closedAt":null}'
            ;;
        "pr list")
            echo '[{"number":99,"title":"WIP fix","state":"OPEN"}]'
            ;;
        "pr view")
            echo '735'
            ;;
    esac
}
EOF
)

run_preflight_with_exit "735" "$t3_mock"
if echo "$LAST_OUTPUT" | grep -q "\[WARN\] Check 3:" && [[ $LAST_EXIT -eq 0 ]]; then
    pass_test "Test 3: OPEN PR with closingIssuesReferences=[735] → WARN exit 0"
else
    fail_test "Test 3: expected WARN+exit0, got exit=${LAST_EXIT}: $(echo "$LAST_OUTPUT" | grep -E 'Check 3')"
fi

# ---------------------------------------------------------------------------
# Test 4: MERGED PR mentions issue 735 in title but closingIssuesReferences
#         is empty → PASS (regression: no false positive)
# ---------------------------------------------------------------------------
t4_mock=$(cat <<'EOF'
gh() {
    case "$1 $2" in
        "issue view")
            echo '{"state":"OPEN","title":"Test Issue","closedAt":null}'
            ;;
        "pr list")
            echo '[{"number":55,"title":"Fix 735-related bug in parser","state":"MERGED"}]'
            ;;
        "pr view")
            # closingIssuesReferences is empty — PR only mentions 735 in title
            echo ''
            ;;
    esac
}
EOF
)

run_preflight_with_exit "735" "$t4_mock"
if echo "$LAST_OUTPUT" | grep -q "\[PASS\] Check 3:" && [[ $LAST_EXIT -eq 0 ]]; then
    pass_test "Test 4: MERGED PR mentions issue in title but no closingRef → PASS (no false positive)"
else
    fail_test "Test 4: expected PASS+exit0, got exit=${LAST_EXIT}: $(echo "$LAST_OUTPUT" | grep -E 'Check 3')"
fi

# ---------------------------------------------------------------------------
# Test 5: Multiple PRs; only one formally closes the issue → only that PR reported
# ---------------------------------------------------------------------------
t5_mock=$(cat <<'EOF'
gh() {
    case "$1 $2" in
        "issue view")
            echo '{"state":"OPEN","title":"Test Issue","closedAt":null}'
            ;;
        "pr list")
            echo '[{"number":10,"title":"Unrelated PR","state":"MERGED"},{"number":20,"title":"Fix for 735","state":"MERGED"}]'
            ;;
        "pr view")
            local pr_num="$3"
            case "$pr_num" in
                10) echo '' ;;     # does not close 735
                20) echo '735' ;;  # formally closes 735
            esac
            ;;
    esac
}
EOF
)

run_preflight_with_exit "735" "$t5_mock"
if echo "$LAST_OUTPUT" | grep -q "\[STOP\] Check 3:" \
    && echo "$LAST_OUTPUT" | grep -q "20:" \
    && ! echo "$LAST_OUTPUT" | grep -q "10:"; then
    pass_test "Test 5: Multiple PRs — only the one with closingRef reported"
else
    fail_test "Test 5: expected only PR 20 reported, got: $(echo "$LAST_OUTPUT" | grep -E 'Check 3|PR #')"
fi

# ---------------------------------------------------------------------------
# Test 6: PRs exist but none formally close this issue → PASS (exit 0)
# ---------------------------------------------------------------------------
t6_mock=$(cat <<'EOF'
gh() {
    case "$1 $2" in
        "issue view")
            echo '{"state":"OPEN","title":"Test Issue","closedAt":null}'
            ;;
        "pr list")
            echo '[{"number":7,"title":"Some other PR","state":"MERGED"},{"number":8,"title":"Another PR","state":"OPEN"}]'
            ;;
        "pr view")
            # Both PRs close issue 999, not 735
            echo '999'
            ;;
    esac
}
EOF
)

run_preflight_with_exit "735" "$t6_mock"
if echo "$LAST_OUTPUT" | grep -q "\[PASS\] Check 3:" && [[ $LAST_EXIT -eq 0 ]]; then
    pass_test "Test 6: PRs exist but none close this issue → PASS"
else
    fail_test "Test 6: expected PASS+exit0, got exit=${LAST_EXIT}: $(echo "$LAST_OUTPUT" | grep -E 'Check 3')"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "========================================"
echo "Results: ${PASS_COUNT} passed, ${FAIL_COUNT} failed"
echo "========================================"

[[ $FAIL_COUNT -eq 0 ]]
