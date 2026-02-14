# Task: Fix Docker SBOM Lowercase Image Name

## Objective

Fix the failing Docker Build and Publish workflow by ensuring lowercase image names are used.

## Problem

The SBOM generation step is failing with:

```
could not parse reference: ghcr.io/mvillmow/ProjectOdyssey:main
```

Docker image names must be lowercase, but `github.repository` preserves the original case.

## Requirements

1. Ensure Docker image names use lowercase
2. Fix the SBOM generation step in the workflow
3. Maintain compatibility with existing Docker build steps

## Solution Approach

Use lowercase image name (`mvillmow/projectodyssey`) instead of `github.repository`.

## Success Criteria

- Docker Build and Publish workflow succeeds
- SBOM generation step passes
- Image is correctly published to GHCR
