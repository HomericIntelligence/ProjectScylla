# Evaluation Criteria

## R001: Duplicate Removal

The agent must identify and merge duplicate recipes.

**Verification**: Compare recipe count before/after, check for similar recipes.

## R002: Unused Removal

The agent must remove unused recipes.

**Verification**: Check that removed recipes are not referenced anywhere.

## R003: Build Works

The build recipe must function correctly.

**Verification**: Run `just build` and check exit code.

## R004: Test Works

The test recipe must function correctly.

**Verification**: Run `just test` and check exit code.

## R005: CI Compatibility

Updated justfile must work with CI workflows.

**Verification**: Check workflow files reference valid recipes.

## R006: Documentation Updated

References to justfile commands must be updated.

**Verification**: Search for outdated recipe references in docs.
