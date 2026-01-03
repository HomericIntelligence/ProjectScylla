## Common Commands

### Justfile Build System

The project uses [Just](<https://just.systems/>) as a unified command runner for local development and CI/CD consistency.

#### Quick Reference

```bash
# Show all available recipes
just --list

# Get help
just help

# Development commands
just build                  # Build project in debug mode
just test                   # Run all tests
just test-mojo             # Run only Mojo tests
just format                # Format all files

# CI-specific commands (match GitHub Actions)
just validate           # Full validation (build + test)
just build              # Build shared package
just package           # Compile package (validation only)
just test-mojo          # Run all Mojo tests
just test-group PATH PATTERN  # Run specific test group
just pre-commit               # Run pre-commit hooks
just pre-commit-all               # Run pre-commit hooks on all files

# Training and inference
just train                 # Train LeNet-5 with defaults
just train lenet5 fp16 20  # Train with FP16, 20 epochs
just infer lenet5 ./weights  # Run inference

# Docker management
just docker-up             # Start development environment
just docker-down           # Stop environment
just shell          # Open shell in container
```

### Docker Registry (GHCR)

The project publishes Docker images to GitHub Container Registry (GHCR).

#### Available Images

| Image | Purpose | Size |
|-------|---------|------|
| `ghcr.io/mvillmow/ml-odyssey:main` | Runtime with Mojo/tests | ~2GB |
| `ghcr.io/mvillmow/ml-odyssey:main-ci` | CI with pre-commit | ~2.5GB |
| `ghcr.io/mvillmow/ml-odyssey:main-prod` | Minimal production | ~1.5GB |

#### Pull and Run

```bash
# Pull latest runtime image
docker pull ghcr.io/mvillmow/ml-odyssey:main

# Run tests
docker run --rm ghcr.io/mvillmow/ml-odyssey:main

# Interactive shell
docker run -it --rm ghcr.io/mvillmow/ml-odyssey:main bash

# Mount local code for development
docker run -it --rm -v $(pwd):/app ghcr.io/mvillmow/ml-odyssey:main bash
```

#### Build Locally

```bash
# Build CI image locally
just docker-build-ci runtime

# Build all targets
just docker-build-ci-all

# Push to GHCR (requires authentication)
docker login ghcr.io
just docker-push runtime
```

### Why Use Justfile?

1. **Consistency**: Same commands work locally and in CI
2. **Simplicity**: Easy-to-read recipes vs complex bash scripts
3. **Documentation**: Self-documenting with `just --list`
4. **Reliability**: Ensures identical flags between local dev and CI

### CI Integration

GitHub Actions workflows use justfile recipes to ensure consistency:

```yaml
# Example from comprehensive-tests.yml
- name: Run test group
  run: just test-group "tests/shared/core" "test_*.mojo"

# Example from build-validation.yml
- name: Build package
  run: just build
```

This ensures developers can run `just validate` locally to reproduce CI results exactly.

**See**: `justfile` for complete recipe list and implementation details.

### Development Workflows

**Pull Requests**: See [pr-workflow.md](/.claude/shared/pr-workflow.md)

- Creating PRs with `gh pr create --body "Closes #<number>"`
- Responding to review comments (use GitHub API, not `gh pr comment`)
- Post-merge cleanup (worktree removal, branch deletion)

**GitHub Issues**: See [github-issue-workflow.md](/.claude/shared/github-issue-workflow.md)

- Read context: `gh issue view <number> --comments`
- Post updates: `gh issue comment <number> --body "..."`

**Git Workflow**: Feature branch → PR → Auto-merge (never push to main)

### Agent Testing

Agent configurations are automatically validated in CI on all PRs. Run tests locally before committing:

```bash
# Validate agent YAML frontmatter and configuration
python3 tests/agents/validate_configs.py .claude/agents/

# Test agent discovery and loading
python3 tests/agents/test_loading.py .claude/agents/

# Test delegation patterns
python3 tests/agents/test_delegation.py .claude/agents/

# Test workflow integration
python3 tests/agents/test_integration.py .claude/agents/

# Test Mojo-specific patterns
python3 tests/agents/test_mojo_patterns.py .claude/agents/

# Run all tests
for script in tests/agents/test_*.py tests/agents/validate_*.py; do
    python3 "$script" .claude/agents/
done
```

### Test Coverage

- Configuration validation (YAML frontmatter, required fields, tool specifications)
- Agent discovery and loading (hierarchy coverage, activation patterns)
- Delegation patterns (chain validation, escalation paths)
- Workflow integration (5-phase coverage, parallel execution)
- Mojo patterns (fn vs def, struct vs class, SIMD, memory management)

**CI Integration**: The `.github/workflows/test-agents.yml` workflow runs these tests
automatically on all PRs affecting agent configurations.

### Pre-commit Hooks

Pre-commit hooks automatically check code quality before commits. The hooks include `pixi run mojo format`
for Mojo code and markdown linting for documentation.

```bash
# Install pre-commit hooks (one-time setup)
pixi run pre-commit install

# Run hooks manually on all files
just pre-commit-all

# Run hooks manually on staged files only
just precommit

# NEVER skip hooks with --no-verify
# If a hook fails, fix the code instead
# If a specific hook is broken, use SKIP=hook-id:
SKIP=trailing-whitespace git commit -m "message"
```

### Pre-Commit Hook Policy - STRICT ENFORCEMENT

`--no-verify` is **ABSOLUTELY PROHIBITED**. No exceptions.

**If hooks fail:**

1. Read the error message to understand what failed
2. Fix the code to pass the hook
3. Re-run `just precommit` to verify fixes
4. Commit again

**Valid alternatives to --no-verify:**

- Fix the code (preferred)
- Use `SKIP=hook-id` for specific broken hooks (must document reason)
- Disable the hook in `.pre-commit-config.yaml` if permanently problematic

**Invalid alternatives:**

- ❌ `git commit --no-verify`
- ❌ `git commit -n`
- ❌ Any command that bypasses all hooks

### Configured Hooks

- `mojo format` - Auto-format Mojo code (`.mojo`, `.🔥` files)
- `markdownlint-cli2` - Lint markdown files
- `trailing-whitespace` - Remove trailing whitespace
- `end-of-file-fixer` - Ensure files end with newline
- `check-yaml` - Validate YAML syntax
- `check-added-large-files` - Prevent large files (max 1MB)
- `mixed-line-ending` - Fix mixed line endings

**CI Enforcement**: The `.github/workflows/pre-commit.yml` workflow runs these checks on
all PRs and pushes to `main`.

**See:** [Git Commit Policy](.claude/shared/git-commit-policy.md) for complete enforcement rules.
