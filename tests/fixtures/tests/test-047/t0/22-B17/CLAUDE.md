## Testing Strategy

ML Odyssey uses a comprehensive two-tier testing strategy designed for fast PR validation
and thorough weekly integration testing.

### Two-Tier Testing Architecture

**Tier 1: Layerwise Unit Tests** (Run on every PR)

- Fast, deterministic tests using FP-representable special values (0.0, 0.5, 1.0, 1.5, -1.0, -0.5)
- Tests each layer independently (forward AND backward passes)
- Validates analytical gradients against numerical gradients
- Small tensor sizes to prevent timeouts
- Runtime: ~12 minutes across all 7 models
- Location: `tests/models/test_<model>_layers.mojo`

**Tier 2: End-to-End Integration Tests** (Run weekly only)

- Full model validation with real datasets (EMNIST, CIFAR-10)
- Tests complete forward-backward pipeline
- Validates training convergence (5 epochs, ≥20% loss decrease)
- Runtime: ~20 minutes per model
- Schedule: Weekly on Sundays at 3 AM UTC
- Location: `tests/models/test_<model>_e2e.mojo`

### Test Coverage by Model

All 7 models have comprehensive test coverage:

| Model | Layers | Layerwise Tests | E2E Tests | Runtime (Layerwise) |
|-------|--------|-----------------|-----------|---------------------|
| LeNet-5 | 12 ops | 25 tests | 7 tests | ~45-55s |
| AlexNet | 15 ops | 42 tests | 9 tests | <60s |
| VGG-16 | 25 ops (13 conv) | 16 tests* | 10 tests | ~90s |
| ResNet-18 | Residual blocks | 12 tests | 9 tests | ~90s |
| MobileNetV1 | Depthwise sep. | 26 tests | 15 tests | ~90s |
| GoogLeNet | Inception modules | 18 tests | 15 tests | ~90s |

\* Heavy deduplication (13 conv → 5 unique tests)
\*\* Extreme deduplication (58 conv → 14 unique tests, 88% reduction)

### Special FP-Representable Values

Layerwise tests use special values that are exactly representable across all dtypes:

- `0.0`, `0.5`, `1.0`, `1.5` - Positive values for forward pass testing
- `-1.0`, `-0.5` - Negative values for ReLU gradient testing
- Seeded random tensors - For gradient checking reproducibility

These values work identically in FP4, FP8, BF8, FP16, FP32, BFloat16, Int8, ensuring
consistent behavior across precision levels.

### Gradient Checking

All parametric layers (Conv, Linear, BatchNorm) validate backward passes:

- Compares analytical gradients to numerical gradients (finite differences)
- Uses seeded random tensors for reproducibility (seed=42)
- Epsilon=1e-5, tolerance=1e-2 for float32
- Small tensor sizes (8×8 for conv) to prevent timeout

### Test Organization

```text
tests/
├── models/
│   ├── test_lenet5_layers.mojo      # Layerwise unit tests
│   ├── test_lenet5_e2e.mojo         # E2E integration tests
│   ├── test_alexnet_layers.mojo
│   ├── test_alexnet_e2e.mojo
│   └── ... (7 models total)
├── shared/
│   └── testing/
│       ├── special_values.mojo      # FP-representable test values
│       ├── layer_testers.mojo       # Reusable layer testing patterns
│       ├── dtype_utils.mojo         # DType iteration utilities
│       └── gradient_checker.mojo    # Numerical gradient validation
```

### CI/CD Workflows

**PR CI** (`.github/workflows/comprehensive-tests.yml`):

- Runs layerwise tests for all 7 models
- Target runtime: < 12 minutes
- 21 parallel test groups
- No dataset downloads required

**Weekly E2E** (`.github/workflows/model-e2e-tests-weekly.yml`):

- Runs E2E tests for all 7 models
- Downloads EMNIST and CIFAR-10 datasets
- Generates weekly report with 365-day retention
- Schedule: Sundays at 3 AM UTC

### Running Tests Locally

```bash
# Run layerwise tests for a specific model
pixi run mojo test tests/models/test_lenet5_layers.mojo

# Run E2E tests (requires datasets)
pixi run mojo test tests/models/test_lenet5_e2e.mojo

# Run all tests for a model
pixi run mojo test tests/models/test_lenet5_*.mojo

# Run all layerwise tests
pixi run mojo test tests/models/test_*_layers.mojo
```

See [Testing Strategy Guide](docs/dev/testing-strategy.md) for comprehensive documentation.
