# Task: Bump GitHub Actions Dependencies

## Objective

Update GitHub Actions dependencies to their latest versions:

- `actions/checkout` from v4 to v6
- `actions/setup-python` to latest version

## Requirements

1. Update all workflow files in `.github/workflows/` that use these actions
2. Ensure version updates are consistent across all workflows
3. Maintain compatibility with existing workflow logic

## Context

Dependabot has identified that newer versions of core GitHub Actions are available. These updates include security fixes and new features.

## Expected Output

- Updated workflow files with new action versions
- All workflows use consistent, updated versions

## Success Criteria

- All `actions/checkout` references updated to v6
- All `actions/setup-python` references updated to latest
- Workflows remain syntactically valid
- No breaking changes to workflow behavior
