# Evaluation Criteria

## R001: Lowercase Image Name

The workflow must use lowercase Docker image name.

**Verification**: Check image name references are all lowercase.

## R002: SBOM Fix

The SBOM generation step must use correct image reference.

**Verification**: Validate SBOM step configuration.

## R003: Valid Workflow

The workflow file must have valid syntax.

**Verification**: Parse workflow as valid YAML.
