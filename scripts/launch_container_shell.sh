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

# Source shared Docker functions
# shellcheck source=docker_common.sh
source "$(dirname "${BASH_SOURCE[0]}")/docker_common.sh"

# Configuration
CONTAINER_NAME="${1:-scylla-shell-$(date +%s)}"

# Check Docker prerequisites
check_docker_prerequisites || exit 1

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

# Build image if needed
ensure_image_built || exit 1

# Prepare volume mounts and credentials
prepare_credential_mount
prepare_env_vars

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
