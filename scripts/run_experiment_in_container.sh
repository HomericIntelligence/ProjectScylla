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

# Source shared Docker functions
# shellcheck source=docker_common.sh
source "$(dirname "${BASH_SOURCE[0]}")/docker_common.sh"

# Check Docker prerequisites
check_docker_prerequisites || exit 1

# Build image if needed
ensure_image_built || exit 1

# Prepare volume mounts and credentials
prepare_credential_mount
prepare_env_vars

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
