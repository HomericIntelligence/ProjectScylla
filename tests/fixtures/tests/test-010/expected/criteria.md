# Evaluation Criteria

## R001: Zero-Copy Implementation
Agent must implement zero-copy slicing mechanism.

**Verification**: Check for view/slice operations instead of copy.

## R002: API Compatibility
Existing API must remain compatible.

**Verification**: Existing tests pass without modification.

## R003: Correctness
Sliced data must be correct.

**Verification**: Run data integrity tests.

## R004: Performance
Solution should not regress performance.

**Verification**: Benchmark comparison.
