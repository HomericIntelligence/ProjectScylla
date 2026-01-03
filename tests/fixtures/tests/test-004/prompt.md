# Task: Upgrade Docker Ubuntu Base Image

## Objective

Update the Docker base image from Ubuntu 22.04 to Ubuntu 24.04 in all Dockerfiles.

## Requirements

1. Update `Dockerfile` to use Ubuntu 24.04 as the base image
2. Update `Dockerfile.ci` to use Ubuntu 24.04 as the base image
3. Ensure both Dockerfiles use consistent base image versions

## Context

The project uses Docker for containerized development and CI environments. Upgrading to Ubuntu 24.04 provides newer system packages and security updates.

## Expected Output

- Modified `Dockerfile` with `FROM ubuntu:24.04` (or equivalent)
- Modified `Dockerfile.ci` with `FROM ubuntu:24.04` (or equivalent)

## Constraints

- Only modify the base image version, not other Dockerfile instructions
- Ensure the version update is consistent across all Dockerfiles
- Do not add new dependencies or modify other configurations

## Success Criteria

- Both Dockerfiles reference Ubuntu 24.04
- Docker build succeeds with the updated base image
- No breaking changes to existing container functionality
