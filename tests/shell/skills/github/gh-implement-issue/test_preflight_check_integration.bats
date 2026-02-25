#!/usr/bin/env bats
# Integration tests for preflight_check.sh against the real GitHub API.
# Skipped unless PREFLIGHT_INTEGRATION=1 and gh is authenticated.
#
# Usage (local only — never run in CI):
#   PREFLIGHT_INTEGRATION=1 bats tests/shell/skills/github/gh-implement-issue/test_preflight_check_integration.bats
#
# Known issues used as test fixtures:
#   #2  — permanently closed epic (will not reopen)
#   #915 — the issue tracking this integration test (open while work is in progress)
#
# If #915 closes and these tests fail, replace the open-issue number with any
# currently open issue number and update the comment above.

SCRIPT="$(git -C "$(dirname "$BATS_TEST_FILENAME")" rev-parse --show-toplevel)/scripts/preflight_check.sh"

setup_file() {
    if [[ "${PREFLIGHT_INTEGRATION:-0}" != "1" ]]; then
        skip "Set PREFLIGHT_INTEGRATION=1 to run integration tests against the real GitHub API"
    fi
    if ! gh auth status >/dev/null 2>&1; then
        skip "gh is not authenticated — run 'gh auth login' first"
    fi
}

# ---------------------------------------------------------------------------
# Scenario 1: Known-closed issue → exit 1 (STOP on Check 1)
# ---------------------------------------------------------------------------
@test "closed issue returns exit 1 and STOP for Check 1 (real API)" {
    run bash "$SCRIPT" 2

    [ "$status" -eq 1 ]
    [[ "$output" == *"[STOP]"* ]]
    [[ "$output" == *"CLOSED"* ]]
}

# ---------------------------------------------------------------------------
# Scenario 2: Known-open issue with no merged closing PRs → exit 0 (PASS)
# ---------------------------------------------------------------------------
@test "open issue with no merged closing PRs returns exit 0 (real API)" {
    run bash "$SCRIPT" 915

    # Check 1 must pass (issue is OPEN)
    [[ "$output" == *"[PASS] Check 1:"* ]]
    # Overall result is 0 — warnings from later checks are acceptable
    [ "$status" -eq 0 ]
}
