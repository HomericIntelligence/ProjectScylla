# Contributing to ProjectScylla

Thank you for your interest in contributing to ProjectScylla! This guide will help you get started.

## Table of Contents

- [Quick Start](#quick-start)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Code Quality Standards](#code-quality-standards)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [Issue Reporting Guidelines](#issue-reporting-guidelines)
- [Documentation Expectations](#documentation-expectations)
- [Code Review Process](#code-review-process)
- [Getting Help](#getting-help)

## Quick Start

**New to ProjectScylla?** Start here:

1. **Fork and Clone**

   ```bash
   git clone https://github.com/YOUR_USERNAME/ProjectScylla.git
   cd ProjectScylla
   ```

2. **Environment Setup**

   ```bash
   # Install Pixi (package manager)
   curl -fsSL https://pixi.sh/install.sh | bash

   # Configure environment variables
   cp .env.example .env
   # Edit .env and add your API keys
   ```

3. **Verify Installation**

   ```bash
   pixi run python --version  # Should be 3.10+
   pixi run pytest tests/ -v  # Run tests
   ```

4. **Make Your First Contribution**
   - Look for issues labeled `good-first-issue`
   - Read the issue description carefully
   - Comment on the issue to let others know you're working on it

## Development Setup

### Prerequisites

- **Python**: 3.10+ (managed via Pixi)
- **Git**: For version control
- **Docker**: Optional, for containerized experiments
- **API Keys**: See `.env.example` for required keys

### Installing Dependencies

ProjectScylla uses Pixi for dependency management:

```bash
# Pixi automatically manages dependencies from pixi.toml
pixi run python --version

# All dependencies are installed in .pixi/ directory
# No manual pip install needed
```

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

**Required variables:**

- `ANTHROPIC_API_KEY` - For LLM judge and agent execution
- `GITHUB_TOKEN` - For GitHub operations

**Optional variables:**

- `OPENAI_API_KEY` - For OpenAI-based agents
- `SCYLLA_LOG_LEVEL` - Set to `DEBUG` for verbose output

See `.env.example` for complete documentation.

## Development Workflow

### 1. Create a Feature Branch

**IMPORTANT:** Never push directly to `main`. All changes must go through pull requests.

```bash
# Create a feature branch
git checkout -b <issue-number>-<short-description>

# Examples:
git checkout -b 42-add-cop-metric
git checkout -b 123-fix-judge-timeout
```

### 2. Make Your Changes

- Follow existing code patterns in `scylla/`
- Add type hints to all function signatures
- Write docstrings for public APIs
- Keep changes focused and minimal

### 3. Write Tests

```bash
# Create tests in tests/unit/ or tests/integration/
# Follow existing test patterns

# Run your tests
pixi run pytest tests/unit/your_test.py -v
```

### 4. Run Code Quality Checks

```bash
# Format and lint code
pixi run ruff check scylla/ --fix
pixi run ruff format scylla/

# Run all tests
pixi run pytest tests/ -v

# Type checking (via pre-commit)
pre-commit run mypy --all-files
```

### 5. Commit Your Changes

Follow conventional commits format:

```bash
git add <files>
git commit -m "type(scope): Brief description

Longer description if needed.

Closes #<issue-number>"
```

**Commit types:**

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring
- `test`: Test additions or changes
- `chore`: Maintenance tasks

**Examples:**

```
feat(metrics): Add Cost-of-Pass calculation
fix(evaluation): Correct token counting logic
docs(readme): Update benchmark instructions
test(analysis): Add bootstrap CI tests
```

### 6. Push and Create PR

```bash
# Push your branch
git push -u origin <branch-name>

# Create pull request
gh pr create \
  --title "Brief description" \
  --body "Closes #<issue-number>

## Summary
Brief summary of changes

## Testing
How you tested the changes

## Checklist
- [x] Tests pass
- [x] Code formatted
- [x] Documentation updated" \
  --label "appropriate-label"
```

## Code Quality Standards

### Python Style

- **PEP 8**: Follow Python style guide
- **Type Hints**: Required for all function signatures
- **Docstrings**: Required for public APIs
- **Line Length**: 100 characters maximum

### Code Principles

1. **KISS** - Keep It Simple, Stupid
2. **YAGNI** - You Ain't Gonna Need It
3. **DRY** - Don't Repeat Yourself
4. **TDD** - Test-Driven Development
5. **SOLID** - Single Responsibility, Open-Closed, etc.

### Pre-commit Hooks

Install pre-commit hooks to automatically check code quality:

```bash
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

**Never skip hooks** with `--no-verify`. Fix the code instead.

## Testing Requirements

### Test Coverage

- **Unit tests**: Required for all new functionality
- **Integration tests**: For multi-component features
- **E2E tests**: For complete workflow changes

### Running Tests

```bash
# All tests
pixi run pytest tests/ --verbose

# Specific categories
pixi run pytest tests/unit/ -v          # Unit tests only
pixi run pytest tests/integration/ -v   # Integration tests

# Specific modules
pixi run pytest tests/unit/analysis/ -v
pixi run pytest tests/unit/metrics/ -v

# With coverage
pixi run pytest tests/ --cov=scylla --cov-report=html
```

### Writing Tests

Use pytest with fixtures and parametrization:

```python
import pytest

def test_metric_calculation():
    """Test that metric calculates correctly."""
    result = calculate_metric(input_data)
    assert result == expected_value

@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
])
def test_with_params(input, expected):
    """Test with multiple inputs."""
    assert double(input) == expected
```

## Pull Request Process

### Before Submitting

- [ ] All tests pass locally
- [ ] Code is formatted (`ruff format`)
- [ ] Code is linted (`ruff check`)
- [ ] Type hints added to new functions
- [ ] Documentation updated
- [ ] Commit message follows conventional commits
- [ ] PR links to related issue

### PR Description Template

```markdown
## Summary
Brief description of changes

## Motivation
Why this change is needed

## Testing
How you tested the changes

## Checklist
- [x] Tests pass
- [x] Code formatted and linted
- [x] Type hints added
- [x] Documentation updated
- [x] Linked to issue #XXX
```

### Review Process

1. **Automated Checks**: CI must pass (tests, linting, type checking)
2. **Code Review**: At least one maintainer approval required
3. **Changes Requested**: Address feedback in new commits
4. **Approval**: PR merged via rebase to maintain linear history

### Responding to Review Comments

Reply to each comment with:

- `Fixed - [brief description of change]`
- `Won't fix - [explanation]`
- `Question - [clarifying question]`

## Issue Reporting Guidelines

### Bug Reports

Use this template:

```markdown
## Description
Clear description of the bug

## Steps to Reproduce
1. Step one
2. Step two
3. Step three

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- OS: [e.g., Ubuntu 22.04]
- Python: [e.g., 3.10]
- ProjectScylla version: [e.g., commit SHA]

## Additional Context
Any other relevant information
```

### Feature Requests

```markdown
## Problem
What problem does this solve?

## Proposed Solution
How should it work?

## Alternatives Considered
What other approaches did you consider?

## Additional Context
Any other relevant information
```

### Questions

For questions about usage or implementation:

1. Check existing documentation first
2. Search closed issues
3. Create a new issue with `question` label

## Documentation Expectations

### Code Documentation

- **Docstrings**: Required for public functions, classes, and modules
- **Type hints**: Required for all function signatures
- **Comments**: Only for non-obvious logic

```python
def calculate_metric(data: pd.DataFrame, threshold: float = 0.5) -> float:
    """Calculate performance metric from experiment data.

    Args:
        data: DataFrame with columns 'score' and 'pass_rate'
        threshold: Minimum pass rate to consider (default: 0.5)

    Returns:
        Calculated metric value between 0.0 and 1.0

    Raises:
        ValueError: If data is empty or missing required columns
    """
    # Implementation here
```

### Project Documentation

- **README.md**: Update if changing user-facing features
- **CLAUDE.md**: Reference for AI agent development (don't modify without discussion)
- **docs/**: Add design docs for major features

## Code Review Process

### For Contributors

1. **Self-review**: Review your own code before requesting review
2. **Small PRs**: Keep PRs focused and reviewable (< 400 lines)
3. **Tests included**: All PRs should include tests
4. **Documentation**: Update docs for user-facing changes

### For Reviewers

1. **Timely**: Respond within 48 hours
2. **Constructive**: Be specific and helpful
3. **Thorough**: Check tests, docs, and edge cases
4. **Blocking vs. Non-blocking**: Clarify which comments must be addressed

## Getting Help

- **Documentation**: Check `docs/` directory
- **Issues**: Search existing issues first
- **Discussions**: Use GitHub Discussions for general questions
- **Chat**: Join our community chat (link in README)

## Development Tips

### Quick Iteration

```bash
# Fast test iteration (no rendering)
pixi run python scripts/generate_all_results.py --no-render

# Run specific test file
pixi run pytest tests/unit/analysis/test_stats.py -v -k "test_bootstrap"

# Auto-format on save in your editor
# Configure VSCode/PyCharm to run ruff on save
```

### Debugging

```bash
# Enable debug logging
export SCYLLA_LOG_LEVEL=DEBUG

# Run with pdb
pixi run python -m pdb scripts/run_experiment.py

# Pytest debugging
pixi run pytest tests/ -v --pdb  # Drop into debugger on failure
```

## Project Structure

```
ProjectScylla/
├── scylla/              # Python source code
│   ├── analysis/        # Statistical analysis
│   ├── adapters/        # CLI adapters
│   ├── automation/      # Automation utilities
│   ├── config/          # Configuration
│   ├── core/            # Core types
│   ├── e2e/             # E2E testing framework
│   ├── executor/        # Execution engine
│   ├── judge/           # LLM judge system
│   ├── metrics/         # Metrics calculation
│   └── reporting/       # Report generation
├── tests/               # Test suite
│   ├── unit/            # Unit tests
│   ├── integration/     # Integration tests
│   └── fixtures/        # Test fixtures
├── scripts/             # Automation scripts
├── config/              # Configuration files
├── docs/                # Documentation
└── .claude/             # AI agent configs
```

## License

By contributing, you agree that your contributions will be licensed under the BSD-3-Clause License.

---

**Thank you for contributing to ProjectScylla!** 🚀
