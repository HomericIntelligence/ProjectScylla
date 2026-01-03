# Evaluation Criteria

## R001: Root Stage Installation
The agent must move CLI installation to a stage running as root.

**Verification**: Check Dockerfile for CLI installation before USER directive.

## R002: GitHub CLI Present
The GitHub CLI must be installed and accessible.

**Verification**: Run `gh --version` in container.

## R003: Claude CLI Present
The Claude CLI must be installed and accessible.

**Verification**: Run `claude --version` in container.

## R004: PATH Configuration
The PATH must include CLI binary locations.

**Verification**: Check ENV PATH directive includes necessary directories.

## R005: Build Success
Docker build must complete without errors.

**Verification**: Run `docker build` and verify exit code 0.
