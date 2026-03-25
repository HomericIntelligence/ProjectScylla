# ProjectScylla task runner — delegates to pixi run
# Ecosystem convention: justfile + pixi (invokable from Odysseus via just scylla-*)

# List all available recipes
default:
    @just --list

# Run pytest
test:
    pixi run test

# Run BATS shell tests
test-shell:
    pixi run test-shell

# Run ruff check
lint:
    pixi run lint

# Run ruff format
format:
    pixi run format

# Run mypy type checker
typecheck:
    pixi run mypy scylla scripts tests

# Build CI container image
ci-build:
    pixi run ci-build

# Run CI lint in container
ci-lint:
    pixi run ci-lint

# Run CI tests in container
ci-test:
    pixi run ci-test

# Run all CI in container
ci-all:
    pixi run ci-all

# Run pip-audit security scan
audit:
    pixi run audit

# Bump project version (usage: just bump patch|minor|major)
bump part:
    pixi run python scripts/bump_version.py {{part}}
    pixi lock


# Run all pre-commit hooks
pre-commit:
    pixi run pre-commit run --all-files
