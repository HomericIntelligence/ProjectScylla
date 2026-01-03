# Task: Fix prelu_activation.mojo Build Errors

## Objective

Fix the build errors in `examples/custom-layers/prelu_activation.mojo` so it compiles successfully.

## Problem

The example file has build errors due to:
- Importing non-existent 'Tensor' type (should be 'ExTensor')
- Using deprecated API patterns
- Module trait implementation causing linker issues

## Requirements

1. Change imports from 'Tensor' to 'ExTensor' (the actual type in shared.core)
2. Remove or simplify Module trait implementation if causing issues
3. Implement custom prelu_simple() function to avoid linker dependencies
4. Use ExTensor API correctly:
   - Ownership transfer with `^` operator
   - Use `numel()` instead of `size()`
   - Proper Float32 list creation
5. Use proper memory access patterns via bitcast for element-wise operations

## Expected Output

- Modified `examples/custom-layers/prelu_activation.mojo` that:
  - Compiles successfully with zero warnings
  - Runs correctly and produces expected output
  - Build command succeeds with exit code 0

## Success Criteria

- `mojo build examples/custom-layers/prelu_activation.mojo` succeeds
- Running the example produces expected PReLU output
- No linker errors or warnings
