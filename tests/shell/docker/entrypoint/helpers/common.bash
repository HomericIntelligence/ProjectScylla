# common.bash — shared BATS helpers for docker/entrypoint.sh tests

_HELPERS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_MOCKS_DIR="${_HELPERS_DIR}/../mocks"

# Prepend the mocks/ directory so our stubs shadow real binaries.
setup_mocks() {
    export PATH="${_MOCKS_DIR}:${PATH}"
}

# Unset all mock control variables so each test starts clean.
clean_state() {
    unset CLAUDE_MOCK_EXIT      || true
    unset TIMEOUT_MOCK_EXIT     || true
    unset GIT_MOCK_CLONE_EXIT   || true
    unset PYTHON_MOCK_EXIT      || true
    unset ANTHROPIC_API_KEY     || true
    unset OPENAI_API_KEY        || true
    unset TIER                  || true
    unset RUN_NUMBER            || true
    unset MODEL                 || true
    unset TEST_ID               || true
    unset TIMEOUT               || true
    unset REPO_URL              || true
    unset REPO_HASH             || true
    unset TEST_COMMAND          || true
}
