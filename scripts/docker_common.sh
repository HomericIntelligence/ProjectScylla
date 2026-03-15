#!/bin/bash
# Shared container setup functions for Docker/Podman scripts
#
# This file provides common functions for container-based scripts to eliminate duplication.
# Supports both Podman (rootless, preferred) and Docker.
#
# Usage:
#   source "$(dirname "${BASH_SOURCE[0]}")/docker_common.sh"
#   # CONTAINER_ENGINE is auto-detected (podman first, docker fallback)
#   # Override: CONTAINER_ENGINE=docker source docker_common.sh
#   check_container_prerequisites
#   ensure_image_built
#   prepare_credential_mount
#   prepare_env_vars
#   # ... run "${CONTAINER_ENGINE}" commands ...
#   cleanup_temp_creds  # or rely on trap

set -euo pipefail

# Colors for output: RED=error, GREEN=info, YELLOW=warn, BLUE=debug
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $*"
}

# Configuration (can be overridden before sourcing)
IMAGE_NAME="${IMAGE_NAME:-scylla-runner:latest}"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

# Global variables set by functions
VOLUMES=()
ENV_VARS=()
TEMP_CREDS_DIR=""

# Detect container engine: Podman first (rootless, no SU), Docker as fallback.
# Override by setting CONTAINER_ENGINE before sourcing this file.
detect_container_engine() {
    if [ -n "${CONTAINER_ENGINE:-}" ]; then
        # Already set by caller — validate it exists
        if ! command -v "${CONTAINER_ENGINE}" &> /dev/null; then
            log_error "CONTAINER_ENGINE=${CONTAINER_ENGINE} not found in PATH"
            return 1
        fi
        log_info "Using container engine: ${CONTAINER_ENGINE} (from CONTAINER_ENGINE env var)"
        return 0
    fi

    if command -v podman &> /dev/null; then
        CONTAINER_ENGINE="podman"
        log_info "Using container engine: podman (rootless)"
    elif command -v docker &> /dev/null; then
        CONTAINER_ENGINE="docker"
        log_info "Using container engine: docker"
    else
        log_error "No container engine found. Install podman (recommended) or docker."
        log_error "  Podman: https://podman.io/getting-started/installation"
        log_error "  Docker: https://docs.docker.com/get-docker/"
        return 1
    fi
    export CONTAINER_ENGINE
}

# Check if the container engine is installed and available.
# For Podman, no daemon is required (rootless). For Docker, checks the daemon.
check_container_prerequisites() {
    detect_container_engine || return 1

    if [ "${CONTAINER_ENGINE}" = "docker" ]; then
        if ! docker info &> /dev/null; then
            log_error "Docker daemon is not running"
            log_error "Please start Docker and try again"
            return 1
        fi
    fi
    # Podman is daemonless — no additional check needed

    return 0
}

# Backward-compatible alias
check_docker_prerequisites() {
    check_container_prerequisites "$@"
}

# Build container image if it doesn't exist
ensure_image_built() {
    detect_container_engine || return 1

    if ! "${CONTAINER_ENGINE}" images -q "${IMAGE_NAME}" &> /dev/null || \
       [ -z "$("${CONTAINER_ENGINE}" images -q "${IMAGE_NAME}")" ]; then
        log_warn "Container image ${IMAGE_NAME} not found"
        log_info "Building container image..."

        if "${CONTAINER_ENGINE}" build -t "${IMAGE_NAME}" \
               -f "${PROJECT_DIR}/docker/Dockerfile" "${PROJECT_DIR}"; then
            log_info "Container image built successfully"
        else
            log_error "Failed to build container image"
            return 1
        fi
    else
        log_info "Using existing container image: ${IMAGE_NAME}"
    fi

    return 0
}

# Prepare credential mount and add to VOLUMES array
prepare_credential_mount() {
    local creds_file="${HOME}/.claude/.credentials.json"

    if [ -f "${creds_file}" ]; then
        log_info "Preparing Claude Code credentials for container"

        # Create a temporary directory with proper permissions
        TEMP_CREDS_DIR="${PROJECT_DIR}/.tmp-container-creds"
        mkdir -p "${TEMP_CREDS_DIR}"

        # Copy credentials file with owner-only permissions
        cp "${creds_file}" "${TEMP_CREDS_DIR}/.credentials.json"
        chmod 600 "${TEMP_CREDS_DIR}/.credentials.json"

        # Mount the temp directory into container
        VOLUMES+=("-v" "${TEMP_CREDS_DIR}:/tmp/host-creds:ro")

        # Set up cleanup trap
        trap cleanup_temp_creds EXIT

        log_info "Credentials will be available in container at /tmp/host-creds/.credentials.json"
    else
        log_warn "Claude Code credentials not found at ${creds_file}"
        log_warn "Container will use ANTHROPIC_API_KEY from environment if available"
    fi

    # Always mount project directory
    VOLUMES+=("-v" "${PROJECT_DIR}:/workspace")

    # Ensure results directory exists and is writable
    mkdir -p "${PROJECT_DIR}/results"
    chmod 777 "${PROJECT_DIR}/results"
}

# Prepare environment variables and add to ENV_VARS array
prepare_env_vars() {
    if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
        log_info "Passing ANTHROPIC_API_KEY to container"
        ENV_VARS+=("-e" "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}")
    fi

    if [ -n "${OPENAI_API_KEY:-}" ]; then
        log_info "Passing OPENAI_API_KEY to container"
        ENV_VARS+=("-e" "OPENAI_API_KEY=${OPENAI_API_KEY}")
    fi
}

# Clean up temporary credentials directory
cleanup_temp_creds() {
    if [ -n "${TEMP_CREDS_DIR}" ] && [ -d "${TEMP_CREDS_DIR}" ]; then
        rm -rf "${TEMP_CREDS_DIR}"
    fi
}
