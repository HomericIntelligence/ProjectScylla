#!/usr/bin/env bats
# Tests for ensure_clean_claude_environment() in docker/entrypoint.sh
#
# ensure_clean_claude_environment() is invoked by: python, python3, bash, sh,
# unknown commands, --run-agent, --run-judge, and --run.
# We use "python --version" (mocked) as the cheapest trigger since it calls
# ensure_clean_claude_environment then exec's the mock python, which exits 0.

load helpers/common

SCRIPT="$(git -C "$(dirname "$BATS_TEST_FILENAME")" rev-parse --show-toplevel)/docker/entrypoint.sh"

setup() {
    setup_mocks
    clean_state
    _TMPDIR="$(mktemp -d)"
    export HOME="${_TMPDIR}/home"
    mkdir -p "${HOME}/.claude"
    # Save and clear any pre-existing /tmp/host-creds credentials
    _HOST_CREDS_BACKUP=""
    if [[ -f /tmp/host-creds/.credentials.json ]]; then
        _HOST_CREDS_BACKUP="$(cat /tmp/host-creds/.credentials.json)"
        rm -f /tmp/host-creds/.credentials.json
    fi
}

teardown() {
    # Restore /tmp/host-creds if it existed before test
    if [[ -n "${_HOST_CREDS_BACKUP:-}" ]]; then
        mkdir -p /tmp/host-creds
        echo "${_HOST_CREDS_BACKUP}" > /tmp/host-creds/.credentials.json
    fi
    rm -rf "${_TMPDIR}"
}

# Invoke ensure_clean_claude_environment via "python --version" passthrough
_run_cred_check() {
    run bash "$SCRIPT" python --version
}

# ---------------------------------------------------------------------------
# .claude directory created with proper permissions
# ---------------------------------------------------------------------------

@test ".claude directory created with 700 permissions" {
    rm -rf "${HOME}/.claude"

    _run_cred_check

    [ -d "${HOME}/.claude" ]
    _perms="$(stat -c '%a' "${HOME}/.claude")"
    [ "$_perms" = "700" ]
}

# ---------------------------------------------------------------------------
# Credential path: /tmp/host-creds/.credentials.json (primary mount)
# ---------------------------------------------------------------------------

@test "/tmp/host-creds/.credentials.json → copied to HOME/.claude/" {
    mkdir -p /tmp/host-creds
    echo '{"token":"from-host-creds"}' > /tmp/host-creds/.credentials.json

    _run_cred_check

    [ "$status" -eq 0 ]
    [[ "$output" == *"Found mounted credentials at /tmp/host-creds"* ]]
    [[ "$output" == *"Copied credentials"* ]]

    rm -f /tmp/host-creds/.credentials.json
}

@test "/tmp/host-creds credentials copied with permissions 600" {
    mkdir -p /tmp/host-creds
    echo '{"token":"from-host-creds"}' > /tmp/host-creds/.credentials.json

    _run_cred_check

    [ "$status" -eq 0 ]
    [ -f "${HOME}/.claude/.credentials.json" ]
    _perms="$(stat -c '%a' "${HOME}/.claude/.credentials.json")"
    [ "$_perms" = "600" ]

    rm -f /tmp/host-creds/.credentials.json
}

# ---------------------------------------------------------------------------
# Credential path: HOME/.claude/.credentials.json (already exists)
# ---------------------------------------------------------------------------

@test "existing HOME/.claude/.credentials.json used in place" {
    echo '{"token":"existing"}' > "${HOME}/.claude/.credentials.json"

    _run_cred_check

    [ "$status" -eq 0 ]
    [[ "$output" == *"Using existing Claude Code credentials"* ]]
}

@test "existing credentials file permissions fixed to 600" {
    echo '{"token":"existing"}' > "${HOME}/.claude/.credentials.json"
    chmod 644 "${HOME}/.claude/.credentials.json"

    _run_cred_check

    [ "$status" -eq 0 ]
    _perms="$(stat -c '%a' "${HOME}/.claude/.credentials.json")"
    [ "$_perms" = "600" ]
}

# ---------------------------------------------------------------------------
# Credential path: ANTHROPIC_API_KEY from environment
# ---------------------------------------------------------------------------

@test "ANTHROPIC_API_KEY only → logs using env var" {
    export ANTHROPIC_API_KEY="sk-ant-test-only"

    _run_cred_check

    [ "$status" -eq 0 ]
    [[ "$output" == *"Using ANTHROPIC_API_KEY from environment"* ]]
}

# ---------------------------------------------------------------------------
# No credentials at all → warn only
# ---------------------------------------------------------------------------

@test "no credentials at all → warns, does not exit non-zero" {
    # ensure_clean_claude_environment warns but does not exit 1

    _run_cred_check

    [ "$status" -eq 0 ]
    [[ "$output" == *"[WARN]"* ]]
    [[ "$output" == *"No Claude Code credentials"* ]] || \
    [[ "$output" == *"claude auth"* ]]
}

# ---------------------------------------------------------------------------
# Priority ordering
# ---------------------------------------------------------------------------

@test "/tmp/host-creds takes priority over HOME/.claude/.credentials.json" {
    mkdir -p /tmp/host-creds
    echo '{"token":"from-host-creds"}' > /tmp/host-creds/.credentials.json
    echo '{"token":"from-home"}' > "${HOME}/.claude/.credentials.json"

    _run_cred_check

    [ "$status" -eq 0 ]
    [[ "$output" == *"Found mounted credentials at /tmp/host-creds"* ]]
    [[ "$output" != *"Using existing Claude Code credentials"* ]]

    rm -f /tmp/host-creds/.credentials.json
}

@test "HOME/.claude takes priority over ANTHROPIC_API_KEY" {
    echo '{"token":"from-home"}' > "${HOME}/.claude/.credentials.json"
    export ANTHROPIC_API_KEY="sk-ant-test"

    _run_cred_check

    [ "$status" -eq 0 ]
    [[ "$output" == *"Using existing Claude Code credentials"* ]]
    [[ "$output" != *"Using ANTHROPIC_API_KEY from environment"* ]]
}

# ---------------------------------------------------------------------------
# Claude Code environment ready message always logged
# ---------------------------------------------------------------------------

@test "Claude Code environment ready message always appears" {
    export ANTHROPIC_API_KEY="sk-ant-test"

    _run_cred_check

    [ "$status" -eq 0 ]
    [[ "$output" == *"Claude Code environment ready"* ]]
}
