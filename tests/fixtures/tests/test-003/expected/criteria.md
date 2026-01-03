# Evaluation Criteria

## R001: Dependency Declaration
The agent must add mypy as a dependency in pixi.toml.

**Verification**: Check if `pixi.toml` contains a mypy dependency entry.

## R002: Lock File Update
The agent must update pixi.lock with the resolved mypy version.

**Verification**: Check if `pixi.lock` contains mypy package information.

## R003: Valid Configuration
The pixi configuration must remain valid and installable.

**Verification**: Run `pixi install` and verify exit code is 0.

## R004: Tool Accessibility
The mypy tool must be accessible in the pixi environment.

**Verification**: Run `pixi run mypy --version` and check for valid output.
