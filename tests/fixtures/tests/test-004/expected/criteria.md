# Evaluation Criteria

## R001: Dockerfile Update
The agent must update Dockerfile to use Ubuntu 24.04.

**Verification**: Check if `Dockerfile` contains `ubuntu:24.04` in FROM instruction.

## R002: Dockerfile.ci Update
The agent must update Dockerfile.ci to use Ubuntu 24.04.

**Verification**: Check if `Dockerfile.ci` contains `ubuntu:24.04` in FROM instruction.

## R003: Consistent Versions
Both Dockerfiles must use the same Ubuntu version.

**Verification**: Compare base image versions in both files.

## R004: Valid Dockerfile Syntax
The Dockerfiles must have valid syntax.

**Verification**: Run `docker build --check` or similar validation.
