# Task: Add Docker Build and Publish Workflow

## Objective

Create a GitHub Actions workflow for building and publishing Docker images to GitHub Container Registry (GHCR).

## Requirements

1. Create `.github/workflows/docker-build-publish.yml`
2. Trigger on push to main and on tags
3. Build multi-platform images (amd64, arm64)
4. Push to ghcr.io with proper authentication
5. Generate SBOM and attestation
6. Tag images appropriately (latest, version, sha)

## Context

The project needs automated Docker image publishing for containerized deployments.

## Expected Output

- New workflow file at `.github/workflows/docker-build-publish.yml`
- Workflow builds and pushes images to GHCR
- Proper tagging strategy implemented

## Success Criteria

- Workflow file created with correct syntax
- Builds trigger on appropriate events
- Images pushed to GHCR successfully
- Multi-platform support working
- SBOM generation enabled
