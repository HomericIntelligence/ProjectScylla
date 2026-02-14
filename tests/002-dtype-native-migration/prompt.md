# Task: Migrate Custom DTypes to Mojo Native Types

## Background

Mojo v0.26.1 now includes native support for exotic floating-point types that were
previously implemented as custom structs in this codebase. The current implementation
uses workarounds because earlier Mojo versions lacked native BFloat16, FP8, and other
exotic dtype support.

The codebase currently contains custom struct implementations for:

- `BF16` (BFloat16 - 8 exponent bits, 7 mantissa bits)
- `FP8` (E4M3 - 4 exponent bits, 3 mantissa bits)
- `BF8` (E5M2 - 5 exponent bits, 2 mantissa bits)
- `FP4_E2M1` (4-bit float - 2 exponent bits, 1 mantissa bit)
- `E8M0Scale` (exponent-only scaling format - 8 exponent bits, 0 mantissa bits)

These custom implementations need to be migrated to use Mojo's native `DType` built-in
types for better performance, SIMD integration, and reduced maintenance burden.

## Objective

Migrate all custom dtype struct implementations to Mojo's native built-in types while
maintaining backward compatibility through type aliases.

## Requirements

### 1. Create Type Aliases File

Create a new file `shared/core/types/dtype_aliases.mojo` that defines type aliases
mapping the old names to new native types:

| Old Type | Native DType |
|----------|--------------|
| `BF16` | `DType.bfloat16` |
| `FP8` | `DType.float8_e4m3fn` |
| `BF8` | `DType.float8_e5m2` |
| `FP4` | `DType.float4_e2m1fn` |
| `E8M0` | `DType.float8_e8m0fnu` |

Use `comptime` (not `alias`) for declarations to follow current Mojo best practices.

### 2. Handle E8M0 Specially

**Critical**: The E8M0 format (exponent-only, no mantissa) requires manual conversion
helpers because native Mojo conversion does not handle this edge case correctly.

You must implement:

- `_e8m0_from_float32(scale: Float32) -> Scalar[E8M0]` - Convert Float32 to E8M0
- `_e8m0_to_float32(e8m0_val: Scalar[E8M0]) -> Float32` - Convert E8M0 to Float32

The E8M0 format stores only the exponent, representing power-of-2 values. Conversion
requires extracting/reconstructing the exponent via bitcast operations.

### 3. Update Dependent Code

Update all code that uses the old struct types:

- Replace `E8M0Scale` struct field access with bitcast patterns
- Replace custom struct constructors with native scalar creation
- Update MXFP4 and NVFP4 blocked format handlers
- Update the extensor encode/decode methods

### 4. Delete Obsolete Files

After migration, delete:

- Old dtype struct implementation files in `shared/core/types/`
- Obsolete test files that tested the old custom implementations
- Remove deleted test files from CI workflow patterns

### 5. Ensure All Tests Pass

Run `pixi run mojo test tests/` and ensure all tests pass. If tests fail due to
tolerance issues with E8M0 quantization, adjust test tolerances appropriately
(E8M0's power-of-2 constraint can cause up to 2x scale difference).

### 6. Update Imports

Update `shared/core/__init__.mojo` to export from the new `dtype_aliases.mojo`
instead of individual dtype files.

## Constraints

**IMPORTANT: The following actions are FORBIDDEN:**

1. **No Git History Access**: You CANNOT access git commits, logs, or history.
   Do NOT use `git log`, `git show`, `git diff <commit>`, or similar commands.

2. **No GitHub API Access**: You CANNOT access GitHub issues, pull requests,
   or any GitHub API. Do NOT use `gh` CLI commands or make API requests.

3. **No Remote Operations**: You CANNOT create remote branches, push to remote,
   or create pull requests.

4. **No Commit Modification**: You CANNOT amend, reset, or modify the initial
   git commit. Your changes will be captured as a diff against HEAD.

5. **Local Changes Only**: All your work must be done as local file modifications.
   The evaluation system will capture your changes via `git diff HEAD`.

## Validation

You CAN and SHOULD run these commands to verify your solution:

- `pixi run mojo build scylla/` - Verify code compiles
- `pixi run mojo test tests/` - Run tests to verify functionality
- `pixi run mojo format scylla/` - Format your code

## Expected Output

When complete, your workspace should contain:

- New file: `shared/core/types/dtype_aliases.mojo` with type definitions
- Modified files: Updated to use native types instead of custom structs
- Deleted files: Old custom dtype implementation files

Your solution will be evaluated based on:

1. Functional correctness (tests pass)
2. Completeness (all types migrated)
3. Code quality (follows Mojo idioms)
4. Change minimality (focused, no unrelated changes)
