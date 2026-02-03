# Success Criteria: DType Native Migration

## File Requirements

### New File: `shared/core/types/dtype_aliases.mojo`

This file MUST exist and contain type aliases for all custom dtypes.

**Required content**:
```mojo
# Use comptime (not alias) per Mojo best practices
comptime BF16 = DType.bfloat16
comptime FP8 = DType.float8_e4m3fn
comptime BF8 = DType.float8_e5m2
comptime FP4 = DType.float4_e2m1fn
comptime E8M0 = DType.float8_e8m0fnu
```

### E8M0 Conversion Helpers

The E8M0 format is exponent-only (8 exponent bits, 0 mantissa bits). Native Mojo
conversion DOES NOT work correctly for this format. Manual helpers MUST be provided.

**Required functions**:
- `_e8m0_from_float32(scale: Float32) -> Scalar[E8M0]`
- `_e8m0_to_float32(e8m0_val: Scalar[E8M0]) -> Float32`

**Key implementation details**:
- Use `bitcast` for raw bit manipulation
- Extract exponent from Float32 bits: `((bits >> 23) & 0xFF)`
- Round to nearest power of 2 based on mantissa
- Handle special cases: zero, infinity, NaN

### Deleted Files

The following files should be DELETED:
- Custom dtype struct implementations in `shared/core/types/`
- Obsolete test files for old implementations
- Any file that only existed to support the custom structs

### Modified Files

The following should be UPDATED:
- `shared/core/__init__.mojo` - Export from dtype_aliases instead of individual files
- `shared/core/types/mxfp4.mojo` - Use native types
- `shared/core/types/nvfp4.mojo` - Use native types
- `shared/training/dtype_utils.mojo` - Update bfloat16_dtype alias
- CI workflow files - Remove deleted test patterns

## Functional Validation

### Code Compiles

```bash
pixi run mojo build scylla/
# Exit code: 0
```

### All Tests Pass

```bash
pixi run mojo test tests/
# Exit code: 0
# All test groups pass
```

## Type Mapping Reference

| Custom Type | Mojo Native DType | Purpose |
|-------------|------------------|---------|
| `BF16` | `DType.bfloat16` | Brain floating point (8 exp, 7 mantissa) |
| `FP8` | `DType.float8_e4m3fn` | 8-bit float (4 exp, 3 mantissa) |
| `BF8` | `DType.float8_e5m2` | 8-bit float (5 exp, 2 mantissa) |
| `FP4` | `DType.float4_e2m1fn` | 4-bit float (2 exp, 1 mantissa) |
| `E8M0` | `DType.float8_e8m0fnu` | Exponent-only scaling format |

## Code Quality Checks

### Use `comptime` Not `alias`

```mojo
# CORRECT
comptime BF16 = DType.bfloat16

# INCORRECT (deprecated)
alias BF16 = DType.bfloat16
```

### Bitcast Patterns

```mojo
# Reading raw bits from native dtype
var raw_byte = bitcast[DType.uint8, 1](scalar_val)[0]

# Creating native dtype from raw bits
var scalar_val = bitcast[FP8, 1](SIMD[DType.uint8, 1](raw_byte))
```

### Import Updates

```mojo
# shared/core/__init__.mojo should export from dtype_aliases
from .types.dtype_aliases import BF16, FP8, BF8, FP4, E8M0
```

## Scoring Summary

| Score | Criteria |
|-------|----------|
| 1.0 | Full migration complete, all tests pass, code quality excellent |
| 0.8 | Migration complete with minor issues, tests pass |
| 0.6 | Most types migrated, some tests may fail |
| 0.4 | Partial migration, significant issues |
| 0.0 | No meaningful progress on migration |

## Forbidden Actions Reminder

- NO access to git history, commits, or logs
- NO access to GitHub issues, PRs, or API
- NO remote git operations (push, branch, PR)
- NO modification of the initial commit
- Local file changes ONLY
