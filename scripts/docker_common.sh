#!/bin/bash
# Shared Docker setup functions for container scripts
#
# This file provides common functions for Docker-based scripts to eliminate duplication.
# Source this file at the beginning of scripts that use Docker.
#
# Usage:
#   source "$(dirname "${BASH_SOURCE[0]}")/docker_common.sh"
#   check_docker_prerequisites
#   ensure_image_built
#   prepare_credential_mount
#   prepare_env_vars
#   # ... run docker commands ...
#   cleanup_temp_creds  # or rely on trap

set -euo pipefail

# Colors for output: RED=error, GREEN=info, YELLOW=warn, BLUE=debug
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

# Check if Docker is installed and daemon is running
check_docker_prerequisites() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        log_error "Please install Docker: https://docs.docker.com/get-docker/"
        return 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        log_error "Please start Docker and try again"
        return 1
    fi

    return 0
}

# Build Docker image if it doesn't exist
ensure_image_built() {
    if ! docker images -q "${IMAGE_NAME}" &> /dev/null || [ -z "$(docker images -q "${IMAGE_NAME}")" ]; then
        log_warn "Docker image ${IMAGE_NAME} not found"
        log_info "Building Docker image..."

        if docker build -t "${IMAGE_NAME}" -f "${PROJECT_DIR}/docker/Dockerfile" "${PROJECT_DIR}"; then
            log_info "Docker image built successfully"
        else
            log_error "Failed to build Docker image"
            return 1
        fi
    else
        log_info "Using existing Docker image: ${IMAGE_NAME}"
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

        # Copy credentials file with world-readable permissions
        cp "${creds_file}" "${TEMP_CREDS_DIR}/.credentials.json"
        chmod 644 "${TEMP_CREDS_DIR}/.credentials.json"

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
