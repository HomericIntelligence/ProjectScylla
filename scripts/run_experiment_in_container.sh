#!/bin/bash
# Wrapper script to run E2E experiments inside Docker container
#
# This script launches the entire run_e2e_experiment.py inside a Docker container,
# providing complete isolation for all agent and judge executions.
#
# Usage:
#   ./scripts/run_experiment_in_container.sh [experiment-args]
#
# Examples:
#   # Run T0 with 1 run, verbose
#   ./scripts/run_experiment_in_container.sh \
#       --tiers-dir tests/fixtures/tests/test-001 \
#       --tiers T0 --runs 1 -v
#
#   # Run multiple tiers
#   ./scripts/run_experiment_in_container.sh \
#       --tiers-dir tests/fixtures/tests/test-001 \
#       --tiers T0 T1 T2 --runs 5

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Configuration
IMAGE_NAME="scylla-runner:latest"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed or not in PATH"
    log_error "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    log_error "Docker daemon is not running"
    log_error "Please start Docker and try again"
    exit 1
fi

# Check if image exists, build if not
if ! docker images -q "${IMAGE_NAME}" &> /dev/null || [ -z "$(docker images -q "${IMAGE_NAME}")" ]; then
    log_warn "Docker image ${IMAGE_NAME} not found"
    log_info "Building Docker image..."

    # Build from project root with docker/Dockerfile
    if docker build -t "${IMAGE_NAME}" -f "${PROJECT_DIR}/docker/Dockerfile" "${PROJECT_DIR}"; then
        log_info "Docker image built successfully"
    else
        log_error "Failed to build Docker image"
        exit 1
    fi
else
    log_info "Using existing Docker image: ${IMAGE_NAME}"
fi

# Prepare volume mounts
VOLUMES=(
    # Mount project directory to /workspace (read-write for results)
    "-v" "${PROJECT_DIR}:/workspace"
)

# Mount Claude credentials if available
CREDS_FILE="${HOME}/.claude/.credentials.json"
if [ -f "${CREDS_FILE}" ]; then
    log_info "Preparing Claude Code credentials for container"

    # Create a temporary directory with proper permissions
    TEMP_CREDS_DIR="${PROJECT_DIR}/.tmp-container-creds"
    mkdir -p "${TEMP_CREDS_DIR}"

    # Copy credentials file with world-readable permissions
    cp "${CREDS_FILE}" "${TEMP_CREDS_DIR}/.credentials.json"
    chmod 644 "${TEMP_CREDS_DIR}/.credentials.json"

    # Mount the temp directory into container
    VOLUMES+=("-v" "${TEMP_CREDS_DIR}:/tmp/host-creds:ro")

    # Clean up temp directory on exit
    trap "rm -rf ${TEMP_CREDS_DIR}" EXIT

    log_info "Credentials will be available in container at /tmp/host-creds/.credentials.json"
else
    log_warn "Claude Code credentials not found at ${CREDS_FILE}"
    log_warn "Container will use ANTHROPIC_API_KEY from environment if available"
fi

# Ensure results directory exists and is writable by container user
mkdir -p "${PROJECT_DIR}/results"
chmod 777 "${PROJECT_DIR}/results"

# Prepare environment variables
ENV_VARS=()

# Pass API keys if set
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    log_info "Passing ANTHROPIC_API_KEY to container"
    ENV_VARS+=("-e" "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}")
fi

if [ -n "${OPENAI_API_KEY:-}" ]; then
    log_info "Passing OPENAI_API_KEY to container"
    ENV_VARS+=("-e" "OPENAI_API_KEY=${OPENAI_API_KEY}")
fi

# Build Docker run command
DOCKER_CMD=(
    docker run
    --rm                          # Remove container after exit
)

# Add -it only if running in interactive terminal
if [ -t 0 ] && [ -t 1 ]; then
    DOCKER_CMD+=(-it)
fi

DOCKER_CMD+=(
    --workdir /workspace          # Set working directory
    "${VOLUMES[@]}"               # Volume mounts
    "${ENV_VARS[@]}"              # Environment variables
    "${IMAGE_NAME}"               # Image name
    python scripts/run_e2e_experiment.py  # Command to run
    "$@"                          # Pass all arguments to the script
)

log_info "Starting experiment in container..."
log_info "Command: ${DOCKER_CMD[*]}"
echo ""

# Run the container
exec "${DOCKER_CMD[@]}"
