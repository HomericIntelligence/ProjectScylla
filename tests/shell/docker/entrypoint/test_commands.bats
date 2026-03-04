#!/usr/bin/env bats
# Tests for main() command dispatch in docker/entrypoint.sh

load helpers/common

SCRIPT="$(git -C "$(dirname "$BATS_TEST_FILENAME")" rev-parse --show-toplevel)/docker/entrypoint.sh"

setup() {
    setup_mocks
    clean_state
    _TMPDIR="$(mktemp -d)"
    export HOME="${_TMPDIR}/home"
    mkdir -p "${HOME}/.claude"
    # Save and clear any pre-existing /tmp/host-creds credentials so they
    # do not interfere with auth-failure tests.
    _HOST_CREDS_BACKUP=""
    if [[ -f /tmp/host-creds/.credentials.json ]]; then
        _HOST_CREDS_BACKUP="$(cat /tmp/host-creds/.credentials.json)"
        rm -f /tmp/host-creds/.credentials.json
    fi
}

teardown() {
    # Restore /tmp/host-creds if it existed before the test
    if [[ -n "${_HOST_CREDS_BACKUP:-}" ]]; then
        mkdir -p /tmp/host-creds
        echo "${_HOST_CREDS_BACKUP}" > /tmp/host-creds/.credentials.json
    fi
    rm -rf "${_TMPDIR}"
}

# Helper: bind /workspace and /output to temp paths via env manipulation.
# entrypoint.sh hard-codes /workspace, /output, /prompt paths, so we use
# a wrapper that bind-mounts them when available, otherwise we test the
# error paths (missing /prompt/task.md etc.) directly.

# ---------------------------------------------------------------------------
# --help / -h
# ---------------------------------------------------------------------------

@test "--help exits 0" {
    run bash "$SCRIPT" --help

    [ "$status" -eq 0 ]
}

@test "--help output contains 'scylla-runner'" {
    run bash "$SCRIPT" --help

    [ "$status" -eq 0 ]
    [[ "$output" == *"scylla-runner"* ]]
}

@test "-h exits 0 (short form)" {
    run bash "$SCRIPT" -h

    [ "$status" -eq 0 ]
    [[ "$output" == *"scylla-runner"* ]]
}

@test "no args defaults to --help, exits 0" {
    run bash "$SCRIPT"

    [ "$status" -eq 0 ]
    [[ "$output" == *"scylla-runner"* ]]
}

# ---------------------------------------------------------------------------
# --version / -v
# ---------------------------------------------------------------------------

@test "--version exits 0" {
    run bash "$SCRIPT" --version

    [ "$status" -eq 0 ]
}

@test "--version output contains 'scylla-runner version'" {
    run bash "$SCRIPT" --version

    [ "$status" -eq 0 ]
    [[ "$output" == *"scylla-runner version"* ]]
}

@test "-v exits 0 (short form)" {
    run bash "$SCRIPT" -v

    [ "$status" -eq 0 ]
    [[ "$output" == *"scylla-runner version"* ]]
}

# ---------------------------------------------------------------------------
# --validate
# ---------------------------------------------------------------------------

@test "--validate with valid env exits 0" {
    export ANTHROPIC_API_KEY="sk-ant-test"

    run bash "$SCRIPT" --validate

    [ "$status" -eq 0 ]
    [[ "$output" == *"Environment validation passed"* ]]
}

@test "--validate with no auth exits 1" {
    run bash "$SCRIPT" --validate

    [ "$status" -eq 1 ]
    [[ "$output" == *"[ERROR]"* ]]
}

# ---------------------------------------------------------------------------
# --run-agent: error paths (no container bind mounts needed)
# ---------------------------------------------------------------------------

@test "--run-agent with missing /prompt/task.md exits 1" {
    export ANTHROPIC_API_KEY="sk-ant-test"
    export MODEL="claude-sonnet-4-5"

    # /prompt/task.md does not exist by default
    run bash "$SCRIPT" --run-agent

    [ "$status" -eq 1 ]
    [[ "$output" == *"Task prompt not found"* ]]
}

@test "--run-agent with missing auth exits 1" {
    # No ANTHROPIC_API_KEY, no credentials file
    # /prompt/task.md also missing → should fail on prompt check first
    run bash "$SCRIPT" --run-agent

    [ "$status" -eq 1 ]
}

@test "--run-agent with missing MODEL exits 1" {
    export ANTHROPIC_API_KEY="sk-ant-test"
    # Create the prompt file under _TMPDIR and symlink to /prompt if writable
    if mkdir -p /prompt 2>/dev/null; then
        echo "test task" > /prompt/task.md
        _cleanup_prompt=1
    else
        skip "Cannot create /prompt (not running as root)"
    fi

    run bash "$SCRIPT" --run-agent

    [ "$status" -eq 1 ]
    [[ "$output" == *"MODEL is not set"* ]]

    [[ -n "${_cleanup_prompt:-}" ]] && rm -f /prompt/task.md
}

# ---------------------------------------------------------------------------
# --run-agent: success path (requires /workspace /output /prompt)
# ---------------------------------------------------------------------------

@test "--run-agent success path writes result.json with exit_code 0" {
    export ANTHROPIC_API_KEY="sk-ant-test"
    export MODEL="claude-sonnet-4-5"

    if ! mkdir -p /workspace /output /prompt 2>/dev/null; then
        skip "Cannot create /workspace|/output|/prompt (not running as root)"
    fi
    echo "test task" > /prompt/task.md

    run bash "$SCRIPT" --run-agent

    [ "$status" -eq 0 ]
    [ -f /output/result.json ]
    [[ "$(cat /output/result.json)" == *'"exit_code": 0'* ]]
    [[ "$(cat /output/result.json)" == *'"timeout": false'* ]]

    rm -f /prompt/task.md /output/result.json /output/stdout.log /output/stderr.log
}

@test "--run-agent timeout writes timeout:true to result.json" {
    export ANTHROPIC_API_KEY="sk-ant-test"
    export MODEL="claude-sonnet-4-5"
    export TIMEOUT_MOCK_EXIT="124"

    if ! mkdir -p /workspace /output /prompt 2>/dev/null; then
        skip "Cannot create /workspace|/output|/prompt (not running as root)"
    fi
    echo "test task" > /prompt/task.md

    run bash "$SCRIPT" --run-agent

    [ "$status" -eq 124 ]
    [ -f /output/result.json ]
    [[ "$(cat /output/result.json)" == *'"timeout": true'* ]]

    unset TIMEOUT_MOCK_EXIT
    rm -f /prompt/task.md /output/result.json /output/stdout.log /output/stderr.log
}

# ---------------------------------------------------------------------------
# --run-judge: error paths
# ---------------------------------------------------------------------------

@test "--run-judge with no auth exits 1" {
    run bash "$SCRIPT" --run-judge

    [ "$status" -eq 1 ]
    [[ "$output" == *"No authentication"* ]]
}

@test "--run-judge with missing MODEL exits 1" {
    export ANTHROPIC_API_KEY="sk-ant-test"

    run bash "$SCRIPT" --run-judge

    [ "$status" -eq 1 ]
    [[ "$output" == *"MODEL is not set"* ]]
}

@test "--run-judge with valid env calls python judge runner" {
    export ANTHROPIC_API_KEY="sk-ant-test"
    export MODEL="claude-sonnet-4-5"

    if ! mkdir -p /workspace /output /prompt 2>/dev/null; then
        skip "Cannot create /workspace|/output|/prompt (not running as root)"
    fi
    echo "test task" > /prompt/task.md

    run bash "$SCRIPT" --run-judge

    [ "$status" -eq 0 ]
    [[ "$output" == *"judge"* ]] || [[ "$output" == *"mock judge output"* ]]

    rm -f /prompt/task.md
}

# ---------------------------------------------------------------------------
# --run: legacy mode
# ---------------------------------------------------------------------------

@test "--run with missing required var TIER exits 1" {
    export ANTHROPIC_API_KEY="sk-ant-test"
    export MODEL="claude-sonnet-4-5"
    export RUN_NUMBER="1"
    export TEST_ID="test-001"
    # TIER is unset

    run bash "$SCRIPT" --run

    [ "$status" -eq 1 ]
}

@test "--run with missing auth exits 1" {
    export TIER="T0"
    export MODEL="claude-sonnet-4-5"
    export RUN_NUMBER="1"
    export TEST_ID="test-001"
    # No ANTHROPIC_API_KEY

    run bash "$SCRIPT" --run

    [ "$status" -eq 1 ]
}

@test "--run with TEST_COMMAND propagates exit code 0" {
    export ANTHROPIC_API_KEY="sk-ant-test"
    export TIER="T0"
    export MODEL="claude-sonnet-4-5"
    export RUN_NUMBER="1"
    export TEST_ID="test-001"
    export TEST_COMMAND="true"

    run bash "$SCRIPT" --run

    [ "$status" -eq 0 ]
}

@test "--run with TEST_COMMAND propagates non-zero exit code" {
    export ANTHROPIC_API_KEY="sk-ant-test"
    export TIER="T0"
    export MODEL="claude-sonnet-4-5"
    export RUN_NUMBER="1"
    export TEST_ID="test-001"
    export TEST_COMMAND="exit 42"

    run bash "$SCRIPT" --run

    [ "$status" -eq 42 ]
}

# ---------------------------------------------------------------------------
# python/python3 passthrough
# ---------------------------------------------------------------------------

@test "python command passthrough exits 0" {
    export ANTHROPIC_API_KEY="sk-ant-test"

    run bash "$SCRIPT" python --version

    [ "$status" -eq 0 ]
}

@test "python3 command passthrough exits 0" {
    export ANTHROPIC_API_KEY="sk-ant-test"

    run bash "$SCRIPT" python3 --version

    [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Unknown command delegation
# ---------------------------------------------------------------------------

@test "unknown command delegates via exec (true exits 0)" {
    export ANTHROPIC_API_KEY="sk-ant-test"

    run bash "$SCRIPT" true

    [ "$status" -eq 0 ]
}

@test "unknown command delegates via exec (false exits 1)" {
    run bash "$SCRIPT" false

    [ "$status" -eq 1 ]
}
