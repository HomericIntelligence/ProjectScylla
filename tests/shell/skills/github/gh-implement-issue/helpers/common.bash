# common.bash — shared BATS helpers for preflight_check.sh tests

_HELPERS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_MOCKS_DIR="${_HELPERS_DIR}/../mocks"

# Prepend the mocks/ directory so our stub gh/git shadow the real ones.
setup_mocks() {
    export PATH="${_MOCKS_DIR}:${PATH}"
}

# Unset all mock control variables so each test starts clean.
clean_state() {
    unset GH_MOCK_ISSUE_STATE    || true
    unset GH_MOCK_PR_JSON        || true
    unset GH_MOCK_ISSUE_COMMENTS || true
    unset GIT_MOCK_LOG           || true
    unset GIT_MOCK_WORKTREE      || true
    unset GIT_MOCK_BRANCH        || true
}
