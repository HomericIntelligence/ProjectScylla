# Mojo Anti-Patterns

Common mistakes to avoid when writing Mojo code for ProjectScylla. Flag ALL occurrences immediately.

## Ownership Violations (Most Common)

### Temporary rvalue ownership transfer

```mojo
# WRONG - Cannot transfer ownership of temporary
var result = BenchmarkResult(List[Float64](), 0.0)

# CORRECT - Create named variable first
var samples = List[Float64]()
var result = BenchmarkResult(samples, 0.0)
```

**Fix**: Create named variable for ALL ownership transfers to `var` parameters.

### ImplicitlyCopyable with non-copyable fields

```mojo
# WRONG - List is NOT implicitly copyable
struct MetricData(Copyable, Movable, ImplicitlyCopyable):
    var samples: List[Float64]

# CORRECT - Only Copyable and Movable
struct MetricData(Copyable, Movable):
    var samples: List[Float64]
    fn get_samples(self) -> List[Float64]:
        return self.samples^  # Explicit transfer
```

**Fix**: NEVER add `ImplicitlyCopyable` to structs with `List`/`Dict`/`String` fields.

### Missing transfer operator

```mojo
# WRONG - Implicit copy fails
fn get_results(self) -> List[Float64]:
    return self.results

# CORRECT - Explicit transfer
fn get_results(self) -> List[Float64]:
    return self.results^
```

**Fix**: ALL returns of `List`/`Dict`/`String` MUST use `^` operator.

## Constructor Signatures

```mojo
# WRONG - mut self in constructor
fn __init__(mut self, value: Float64):
    self.value = value

# CORRECT - out self for constructors
fn __init__(out self, value: Float64):
    self.value = value
```

**Constructor Convention Table:**

| Method | Parameter | Example |
|--------|-----------|---------|
| `__init__` | `out self` | `fn __init__(out self, value: Float64)` |
| `__moveinit__` | `out self, owned existing` | `fn __moveinit__(out self, owned existing: Self)` |
| `__copyinit__` | `out self, existing` | `fn __copyinit__(out self, existing: Self)` |
| Mutating methods | `mut self` | `fn add_sample(mut self, sample: Float64)` |

## Uninitialized Data

### Uninitialized list access

```mojo
# WRONG - Cannot assign to uninitialized index
var samples = List[Float64]()
samples[0] = 0.5  # Runtime error

# CORRECT - append creates the element
var samples = List[Float64]()
samples.append(0.5)
```

### Division by zero in metrics

```mojo
# WRONG - No check for zero denominator
fn calculate_cop(cost: Float64, pass_rate: Float64) -> Float64:
    return cost / pass_rate  # Division by zero if pass_rate == 0

# CORRECT - Handle edge case
fn calculate_cop(cost: Float64, pass_rate: Float64) -> Float64:
    if pass_rate <= 0.0:
        return Float64.MAX  # Or return special value
    return cost / pass_rate
```

### Empty list statistics

```mojo
# WRONG - No check for empty list
fn calculate_mean(data: List[Float64]) -> Float64:
    var sum: Float64 = 0.0
    for i in range(len(data)):
        sum += data[i]
    return sum / Float64(len(data))  # Division by zero!

# CORRECT - Check for empty
fn calculate_mean(data: List[Float64]) -> Float64:
    var n = len(data)
    if n == 0:
        return 0.0  # Or raise error

    var sum: Float64 = 0.0
    for i in range(n):
        sum += data[i]
    return sum / Float64(n)
```

## Syntax Errors

### Missing space after `var`

```mojo
# WRONG - Typo (vara seen as variable name)
vara = 1.0
varpass_rate = 0.67

# CORRECT - Space required
var a = 1.0
var pass_rate = 0.67
```

**Detection**: Search for `var[a-z]` pattern.

## Type System Issues

### Float precision

```mojo
# WRONG - Using Float32 for metrics (precision loss)
var pass_rate: Float32 = 0.6789012345

# CORRECT - Use Float64 for metrics
var pass_rate: Float64 = 0.6789012345
```

### Integer division

```mojo
# WRONG - Integer division truncates
var pass_rate = passes / total  # Both Int, result truncated

# CORRECT - Cast to float
var pass_rate = Float64(passes) / Float64(total)
```

## Evaluation-Specific Anti-Patterns

### Not handling zero pass rate

```mojo
# WRONG - Cost-of-Pass undefined when pass_rate = 0
fn report_cop(cost: Float64, pass_rate: Float64) -> String:
    var cop = cost / pass_rate
    return String(cop)

# CORRECT - Handle special case
fn report_cop(cost: Float64, pass_rate: Float64) -> String:
    if pass_rate <= 0.0:
        return "N/A (no passes)"
    var cop = cost / pass_rate
    return String(cop)
```

### Insufficient sample size checks

```mojo
# WRONG - No sample size validation
fn calculate_ci(data: List[Float64]) -> Tuple[Float64, Float64]:
    var mean = calculate_mean(data)
    var std = calculate_std(data, mean)
    var margin = 1.96 * std / sqrt(Float64(len(data)))
    return (mean - margin, mean + margin)

# CORRECT - Validate sample size
fn calculate_ci(data: List[Float64]) -> Tuple[Float64, Float64]:
    var n = len(data)
    if n < 2:
        # Cannot calculate CI with n < 2
        var mean = calculate_mean(data)
        return (mean, mean)  # Point estimate only

    var mean = calculate_mean(data)
    var std = calculate_std(data, mean)
    var margin = 1.96 * std / sqrt(Float64(n))
    return (mean - margin, mean + margin)
```

## Quick Detection Checklist

Search codebase for these patterns:

- `fn __init__(mut self` -> Change to `out self`
- `inout self` -> Change to `mut self`
- `ImplicitlyCopyable` -> Check if fields are copyable
- `return self.*` without `^` -> Add transfer operator
- `var[a-z]` -> Add space after `var`
- `/ pass_rate` -> Check for zero handling
- `/ Float64(len` -> Check for empty list handling

## Metric-Specific Checks

Before submitting metrics code:

- [ ] Division operations check for zero denominators
- [ ] Mean/std/CI functions handle empty lists
- [ ] Pass rate handles case of zero attempts
- [ ] Cost-of-Pass handles zero pass rate
- [ ] Sample size validated before statistical calculations
- [ ] Float64 used for all metric values (not Float32)
