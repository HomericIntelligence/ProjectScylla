# Evaluation Criteria

## R001: Checkout Updated
All actions/checkout references must be updated to v6.

**Verification**: Search workflow files for `actions/checkout@v`.

## R002: Setup Python Updated
All actions/setup-python references must be updated.

**Verification**: Search workflow files for `actions/setup-python@v`.

## R003: Consistent Versions
All workflows must use the same action versions.

**Verification**: Compare action versions across all workflow files.

## R004: Valid Syntax
All workflow files must have valid YAML syntax.

**Verification**: Parse each workflow file as valid YAML.
