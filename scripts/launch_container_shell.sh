#!/bin/bash
# Launch an interactive container for running multiple experiments
#
# This script starts a persistent Docker container where you can run multiple
# experiments without having to restart the container each time.
#
# Usage:
#   ./scripts/launch_container_shell.sh [container-name]
#
# Examples:
#   # Launch with default name
#   ./scripts/launch_container_shell.sh
#
#   # Launch with custom name
#   ./scripts/launch_container_shell.sh my-experiment-env
#
# Inside the container, run experiments with:
#   python scripts/run_e2e_experiment.py --tiers-dir tests/fixtures/tests/test-001 --tiers T0 --runs 1 -v

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
CONTAINER_NAME="${1:-scylla-shell-$(date +%s)}"

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

# Check if container with this name already exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log_warn "Container '${CONTAINER_NAME}' already exists"

    # Check if it's running
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_info "Container is already running. Attaching to it..."
        exec docker exec -it "${CONTAINER_NAME}" bash
    else
        log_info "Starting existing container and attaching..."
        docker start "${CONTAINER_NAME}"
        exec docker exec -it "${CONTAINER_NAME}" bash
    fi
fi

# Check if image exists, build if not
if ! docker images -q "${IMAGE_NAME}" &> /dev/null || [ -z "$(docker images -q "${IMAGE_NAME}")" ]; then
    log_warn "Docker image ${IMAGE_NAME} not found"
    log_info "Building Docker image..."

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

    log_info "Credentials will be available in container"
else
    log_warn "Claude Code credentials not found at ${CREDS_FILE}"
    log_warn "Container will use ANTHROPIC_API_KEY from environment if available"
fi

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

# Ensure results directory exists and is writable by container user
mkdir -p "${PROJECT_DIR}/results"
chmod 777 "${PROJECT_DIR}/results"

log_info "Starting interactive container: ${CONTAINER_NAME}"
log_info ""
log_info "Inside the container, you can run experiments with:"
log_info "  ${BLUE}python scripts/run_e2e_experiment.py --tiers-dir tests/fixtures/tests/test-001 --tiers T0 --runs 1 -v${NC}"
log_info ""
log_info "To exit the container: ${BLUE}exit${NC} or press ${BLUE}Ctrl+D${NC}"
log_info "To stop the container from outside: ${BLUE}docker stop ${CONTAINER_NAME}${NC}"
log_info "To re-attach later: ${BLUE}docker exec -it ${CONTAINER_NAME} bash${NC}"
log_info ""

# Run the container interactively
exec docker run \
    --rm \
    -it \
    --name "${CONTAINER_NAME}" \
    --workdir /workspace \
    "${VOLUMES[@]}" \
    "${ENV_VARS[@]}" \
    "${IMAGE_NAME}" \
    bash
