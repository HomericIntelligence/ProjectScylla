# Evaluation Criteria

## R001: Workflow Created
Agent must create the Docker build workflow file.

**Verification**: Check file exists at `.github/workflows/docker-build-publish.yml`.

## R002: Correct Triggers
Workflow must trigger on push to main and tags.

**Verification**: Check `on:` section of workflow.

## R003: GHCR Authentication
Workflow must authenticate with GHCR.

**Verification**: Check for `docker/login-action` with ghcr.io.

## R004: Multi-Platform
Workflow must support multiple platforms.

**Verification**: Check for `platforms:` configuration.

## R005: Proper Tagging
Images must be tagged appropriately.

**Verification**: Check for tag extraction and labeling.
