# Evaluation Criteria

## R001: Correct Import

The agent must use ExTensor instead of Tensor in imports.

**Verification**: Check import statements in the file.

## R002: Build Success

The file must compile without errors.

**Verification**: Run `mojo build` and check exit code.

## R003: No Warnings

The file must compile without warnings.

**Verification**: Check build output for warning messages.

## R004: Correct API Usage

The agent must use correct ExTensor API patterns.

**Verification**: Check for numel(), ownership transfer (^), proper initialization.

## R005: Runtime Success

The example must run and produce output.

**Verification**: Execute the compiled example and check output.
