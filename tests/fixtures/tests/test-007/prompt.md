# Task: Simplify Justfile Build System

## Objective

Simplify the project's justfile by merging duplicate commands, deleting unused commands, simplifying the flow, and fixing build/package issues.

## Requirements

1. **Merge Duplicate Commands**: Identify and consolidate duplicate or similar recipes
2. **Remove Unused Commands**: Delete recipes that are no longer used or referenced
3. **Simplify Flow**: Streamline command dependencies and execution paths
4. **Fix Build Issues**: Ensure build and package commands work correctly
5. **Update CI Workflows**: Ensure GitHub Actions workflows reference updated recipe names

## Context

This project uses Just as a command runner. Over time, the justfile has accumulated duplicate and unused recipes that need cleanup.

## Expected Changes

- Simplified `justfile` with fewer, cleaner recipes
- Updated `.github/workflows/` files if recipe names changed
- Updated documentation references to justfile commands
- All existing functionality preserved or improved

## Success Criteria

- `just --list` shows clean, organized recipes
- `just build` succeeds
- `just test` succeeds
- CI workflows pass with updated recipe references
- No duplicate or redundant recipes remain
