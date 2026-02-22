#!/usr/bin/env bats
# Tests for preflight_check.sh
# Covers the 5 behavioral scenarios from issue #800.

load helpers/common

SCRIPT="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)/../../../../claude-code/shared/skills/github/gh-implement-issue/scripts/preflight_check.sh"

setup() {
    setup_mocks
    clean_state
}

# ---------------------------------------------------------------------------
# Test 1: Closed issue triggers exit 1
# ---------------------------------------------------------------------------
@test "closed issue triggers exit 1" {
    export GH_MOCK_ISSUE_STATE='{"state":"CLOSED","title":"Done Issue","closedAt":"2024-01-01T00:00:00Z"}'

    run bash "$SCRIPT" 800

    [ "$status" -eq 1 ]
    [[ "$output" == *"[STOP]"* ]]
    [[ "$output" == *"CLOSED"* ]]
}

# ---------------------------------------------------------------------------
# Test 2: Merged PR triggers exit 1
# ---------------------------------------------------------------------------
@test "merged PR triggers exit 1" {
    export GH_MOCK_ISSUE_STATE='{"state":"OPEN","title":"My Issue","closedAt":null}'
    export GH_MOCK_PR_JSON='[{"number":99,"title":"Fix everything","state":"MERGED"}]'

    run bash "$SCRIPT" 800

    [ "$status" -eq 1 ]
    [[ "$output" == *"[STOP]"* ]]
    [[ "$output" == *"MERGED"* ]]
}

# ---------------------------------------------------------------------------
# Test 3: Open PR exits 0 with warning
# ---------------------------------------------------------------------------
@test "open PR exits 0 with warning" {
    export GH_MOCK_ISSUE_STATE='{"state":"OPEN","title":"My Issue","closedAt":null}'
    export GH_MOCK_PR_JSON='[{"number":42,"title":"WIP: Fix","state":"OPEN"}]'

    run bash "$SCRIPT" 800

    [ "$status" -eq 0 ]
    [[ "$output" == *"[WARN]"* ]]
    [[ "$output" == *"OPEN PR"* ]]
}

# ---------------------------------------------------------------------------
# Test 4: Worktree conflict triggers exit 1
# ---------------------------------------------------------------------------
@test "worktree conflict triggers exit 1" {
    export GH_MOCK_ISSUE_STATE='{"state":"OPEN","title":"My Issue","closedAt":null}'
    export GH_MOCK_PR_JSON='[]'
    export GIT_MOCK_WORKTREE="/home/user/ProjectScylla/.worktrees/issue-800  abc1234 [800-auto-impl]"

    run bash "$SCRIPT" 800

    [ "$status" -eq 1 ]
    [[ "$output" == *"[STOP]"* ]]
    [[ "$output" == *"Worktree already exists"* ]]
}

# ---------------------------------------------------------------------------
# Test 5: Clean state passes all checks
# ---------------------------------------------------------------------------
@test "clean state passes all checks" {
    export GH_MOCK_ISSUE_STATE='{"state":"OPEN","title":"Clean Issue","closedAt":null}'
    export GH_MOCK_PR_JSON='[]'
    # GIT_MOCK_WORKTREE, GIT_MOCK_LOG, GIT_MOCK_BRANCH all unset → empty output

    run bash "$SCRIPT" 800

    [ "$status" -eq 0 ]
    [[ "$output" == *"SAFE TO PROCEED"* ]]
}
