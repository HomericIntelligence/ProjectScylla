#!/bin/bash
# Run the Scylla CI suite locally inside a container.
#
# Mirrors what GitHub Actions runs, using the same CI container image.
# Supports both Podman (rootless, no SU — preferred) and Docker.
#
# Usage:
#   ./scripts/run_ci_local.sh              # Run all CI checks
#   ./scripts/run_ci_local.sh pre-commit   # Pre-commit hooks only
#   ./scripts/run_ci_local.sh lint         # Full lint job (pre-commit + ruff C901 + mypy + lint-imports)
#   ./scripts/run_ci_local.sh unit         # Full unit-tests job (guards + consistency + pytest unit)
#   ./scripts/run_ci_local.sh integration  # Full integration-tests job (guards + nats-server + pytest int)
#   ./scripts/run_ci_local.sh test         # pytest unit + integration
#   ./scripts/run_ci_local.sh test-unit    # pytest unit tests only
#   ./scripts/run_ci_local.sh test-int     # pytest integration tests only
#   ./scripts/run_ci_local.sh security     # pip-audit dependency scan
#   ./scripts/run_ci_local.sh secrets      # gitleaks secrets scan
#   ./scripts/run_ci_local.sh schema       # workflow schema + schemas/ JSON validation
#   ./scripts/run_ci_local.sh deps         # deps/version-sync checks + uv.lock sync
#   ./scripts/run_ci_local.sh shell-test   # BATS shell tests
#
# Container engine: auto-detected (podman first, docker fallback).
# Override: CONTAINER_ENGINE=docker ./scripts/run_ci_local.sh
#
# Image: uses 'scylla-ci:local' if available, falls back to GHCR image.
# Build locally: just ci-build  (or: podman build -f ci/Containerfile -t scylla-ci:local .)

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SUBSET="${1:-all}"

# CI image: prefer locally-built image; fall back to GHCR
LOCAL_IMAGE="scylla-ci:local"
GHCR_IMAGE="ghcr.io/homericintelligence/scylla-ci:latest"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[CI]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[CI]${NC} $*"; }
log_error() { echo -e "${RED}[CI]${NC} $*" >&2; }
log_step()  { echo -e "\n${BLUE}==>${NC} $*"; }

# ============================================================================
# Container engine detection
# ============================================================================

detect_engine() {
    if [ -n "${CONTAINER_ENGINE:-}" ]; then
        if ! command -v "${CONTAINER_ENGINE}" &> /dev/null; then
            log_error "CONTAINER_ENGINE=${CONTAINER_ENGINE} not found in PATH"
            exit 1
        fi
        log_info "Container engine: ${CONTAINER_ENGINE} (from env)"
        return
    fi

    if command -v podman &> /dev/null; then
        CONTAINER_ENGINE="podman"
        log_info "Container engine: podman (rootless)"
    elif command -v docker &> /dev/null; then
        CONTAINER_ENGINE="docker"
        log_info "Container engine: docker"
    else
        log_error "No container engine found. Install podman (recommended) or docker."
        log_error "  Podman: https://podman.io/getting-started/installation"
        exit 1
    fi
    export CONTAINER_ENGINE
}

# ============================================================================
# Image resolution
# ============================================================================

resolve_image() {
    if "${CONTAINER_ENGINE}" image exists "${LOCAL_IMAGE}" 2>/dev/null || \
       "${CONTAINER_ENGINE}" images -q "${LOCAL_IMAGE}" 2>/dev/null | grep -q .; then
        CI_IMAGE="${LOCAL_IMAGE}"
        log_info "Using local CI image: ${CI_IMAGE}"
    else
        log_warn "Local image '${LOCAL_IMAGE}' not found."
        log_warn "Pulling from GHCR: ${GHCR_IMAGE}"
        log_warn "(To build locally: just ci-build)"
        "${CONTAINER_ENGINE}" pull "${GHCR_IMAGE}"
        CI_IMAGE="${GHCR_IMAGE}"
    fi
    export CI_IMAGE
}

# ============================================================================
# Run a command inside the CI container
# ============================================================================
# Volume mounts:
#   /workspace  — the full repo (rw, :Z for SELinux/Podman)
#   /workspace/.git — repo git metadata (read-only, for pre-commit incremental)
# --userns=keep-id — Podman: map host UID into container (fixes mounted file ownership)
# No effect on Docker (flag ignored or equivalent to default behavior)

run_in_container() {
    local cmd=("$@")
    local engine_flags=()

    # Podman-specific flags for rootless execution
    if [ "${CONTAINER_ENGINE}" = "podman" ]; then
        engine_flags+=(--userns=keep-id)
    fi

    "${CONTAINER_ENGINE}" run --rm \
        "${engine_flags[@]}" \
        --volume "${PROJECT_ROOT}:/workspace:Z" \
        --workdir /workspace \
        "${CI_IMAGE}" \
        "${cmd[@]}"
}

# ============================================================================
# CI steps (mirror .github/workflows/_required.yml)
# ============================================================================

run_pre_commit() {
    log_step "Pre-commit (linting, type checking, security hooks)"
    run_in_container \
        uv run \
        pre-commit run --all-files --show-diff-on-failure
}

run_lint() {
    log_step "lint: pre-commit + ruff C901 + mypy + lint-imports"
    run_pre_commit
    run_in_container uv run ruff check --select C901 src/scylla/ scripts/
    run_in_container uv run mypy scripts/ src/scylla/ tests/
    run_in_container uv run lint-imports
}

run_guards() {
    # Enforce no new deprecated BaseExecutionInfo usage
    local count
    count=$(grep -rn "BaseExecutionInfo" "${PROJECT_ROOT}" \
        --include="*.py" \
        --exclude-dir=".venv" \
        --exclude-dir=".pixi" \
        | grep -v "src/scylla/core/results.py" \
        | grep -v "src/scylla/core/__init__.py" \
        | grep -v "# deprecated" \
        | grep -v "(deprecated)" \
        | grep -v "test_results.py" \
        | wc -l)
    echo "BaseExecutionInfo usage count (excluding definition, re-export, and tests): $count"
    if [ "$count" -gt "0" ]; then
        echo "::error::Found $count usages of deprecated BaseExecutionInfo — remove before merging"
        return 1
    fi

    # Enforce no new deprecated BaseRunMetrics usage
    count=$(grep -rn "BaseRunMetrics" "${PROJECT_ROOT}" \
        --include="*.py" \
        --exclude-dir=".venv" \
        --exclude-dir=".pixi" \
        | grep -v "src/scylla/core/results.py" \
        | grep -v "# deprecated" \
        | grep -v "(deprecated)" \
        | grep -v "test_results.py" \
        | wc -l)
    echo "BaseRunMetrics usage count (excluding definition and tests): $count"
    if [ "$count" -gt "0" ]; then
        echo "::error::Found $count usages of deprecated BaseRunMetrics — remove before merging"
        return 1
    fi

    # Enforce tier label consistency in metrics-definitions.md
    local bad_pats
    bad_pats="T3.{0,10}Tool|T4.{0,10}Deleg|T5.{0,10}Hier|T2.{0,10}Skill|T2.{0,10}Deleg|T3.{0,10}Hier|T4.{0,10}Hybrid|T1.{0,10}Tool|T0.{0,10}Skill|T1.{0,10}Prompt|T2.{0,10}Prompt|T3.{0,10}Skill|T4.{0,10}Tool|T5.{0,10}Deleg|T6.{0,10}Hier|T6.{0,10}Hybrid|T0.{0,10}Tool|T0.{0,10}Deleg|T5.{0,10}Skill|T6.{0,10}Deleg"
    count=$(grep -En "$bad_pats" \
        "${PROJECT_ROOT}/.claude/shared/metrics-definitions.md" | wc -l)
    echo "Bad tier label count: $count"
    if [ "$count" -gt "0" ]; then
        echo "::error::Found $count tier label mismatch(es) in metrics-definitions.md"
        return 1
    fi
}

run_uv_sync_checks() {
    # uv.lock up-to-date + consistency scripts shared by unit/integration jobs.
    run_in_container uv lock --check
    run_in_container uv run python scripts/check_python_version_consistency.py
    run_in_container uv run python scripts/check_doc_config_consistency.py --verbose
}

run_unit() {
    log_step "unit-tests: guards + consistency + pytest unit (75% floor)"
    run_guards
    run_uv_sync_checks
    run_in_container uv run python scripts/check_unit_test_structure.py
    run_in_container uv run python scripts/validate_config_schemas.py config/defaults.yaml config/models/*.yaml tests/fixtures/config/tiers/*.yaml
    run_in_container uv run hephaestus-check-complexity --threshold 10
    run_in_container uv run lint-imports
    run_in_container \
        uv run pytest tests/unit --override-ini="addopts=" -v --strict-markers \
            --cov=src/scylla --cov-report=term-missing --cov-report=xml --cov-fail-under=75 \
            --junitxml=junit-unit.xml
}

run_integration() {
    log_step "integration-tests: guards + nats-server + pytest integration (5% floor)"
    run_guards
    run_uv_sync_checks
    run_in_container \
        uv run pytest tests/integration -v \
            --cov=src/scylla --cov-report=term-missing --cov-report=xml --cov-fail-under=5 \
            --reruns 2 --reruns-delay 5 \
            --junitxml=junit-integration.xml
}

run_test_unit() {
    log_step "Unit tests (pytest tests/unit, 75% coverage floor)"
    run_in_container \
        uv run pytest tests/unit \
            --override-ini="addopts=" \
            -v --strict-markers \
            --cov=src/scylla --cov-report=term-missing \
            --cov-fail-under=75
}

run_test_integration() {
    log_step "Integration tests (pytest tests/integration)"
    run_in_container \
        uv run pytest tests/integration \
            -v --cov=src/scylla --cov-report=term-missing
}

run_security() {
    log_step "Security scan (pip-audit, HIGH/CRITICAL only)"
    run_in_container \
        sh -c 'uv run pip-audit --format json | uv run python scripts/filter_audit.py'
}

run_secrets() {
    log_step "Security secrets scan (gitleaks)"
    run_in_container gitleaks detect --source . --config .gitleaks.toml --verbose
}

run_schema() {
    log_step "schema-validation: workflow schemas + schemas/ JSON"
    run_in_container \
        sh -c '
            set -euo pipefail
            find .github/workflows -name "*.yml" | sort | \
                xargs uv run check-jsonschema \
                  --schemafile https://json.schemastore.org/github-workflow
            find schemas/ -name "*.json" 2>/dev/null | sort | while read -r f; do
                echo "Checking $f ..."
                python3 -c "import json, sys; json.load(open(\"$f\"))"
            done
        '
}

run_deps() {
    log_step "deps/version-sync: version consistency + uv.lock sync"
    run_in_container uv run python scripts/check_package_version_consistency.py --scan-skills
    run_in_container uv run python scripts/check_ci_version_sync.py --verbose
    run_in_container uv lock --check
}

run_shell_tests() {
    log_step "Shell tests (BATS)"
    run_in_container \
        sh -c "PREFLIGHT_INTEGRATION=0 bats tests/shell/ --recursive --timing"
}

# ============================================================================
# Main
# ============================================================================

FAILED=()

run_step() {
    local name="$1"
    local fn="$2"
    # Keep `set -e` active inside fn (fail-fast: a broken check must not let
    # follow-on steps run and emit confusing downstream errors), but capture
    # the exit code here so the top-level script survives to report all
    # failures.
    set +e
    "${fn}"
    local rc=$?
    set -e
    if [ "${rc}" -ne 0 ]; then
        FAILED+=("${name}")
        log_error "${name} FAILED"
    fi
}

detect_engine
resolve_image

log_info "CI subset: ${SUBSET}"
log_info "Project root: ${PROJECT_ROOT}"

case "${SUBSET}" in
    pre-commit)
        run_step "pre-commit" run_pre_commit
        ;;
    lint)
        run_step "lint" run_lint
        ;;
    unit)
        run_step "unit-tests" run_unit
        ;;
    integration)
        run_step "integration-tests" run_integration
        ;;
    test|test-all)
        run_step "test-unit" run_test_unit
        run_step "test-integration" run_test_integration
        ;;
    test-unit)
        run_step "test-unit" run_test_unit
        ;;
    test-int|test-integration)
        run_step "test-integration" run_test_integration
        ;;
    security)
        run_step "security" run_security
        ;;
    secrets)
        run_step "secrets" run_secrets
        ;;
    schema)
        run_step "schema" run_schema
        ;;
    deps)
        run_step "deps" run_deps
        ;;
    shell-test|shell)
        run_step "shell-test" run_shell_tests
        ;;
    all)
        run_step "lint" run_lint
        run_step "unit-tests" run_unit
        run_step "integration-tests" run_integration
        run_step "security" run_security
        run_step "secrets" run_secrets
        run_step "schema" run_schema
        run_step "deps" run_deps
        run_step "shell-test" run_shell_tests
        ;;
    *)
        log_error "Unknown subset: ${SUBSET}"
        log_error "Valid values: all, lint, unit, integration, pre-commit, test, test-unit, test-int, security, secrets, schema, deps, shell-test"
        exit 1
        ;;
esac

echo ""
if [ "${#FAILED[@]}" -eq 0 ]; then
    log_info "All CI checks passed."
else
    log_error "Failed: ${FAILED[*]}"
    exit 1
fi
