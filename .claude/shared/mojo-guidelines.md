# Mojo Guidelines

Shared Mojo language guidelines for all agents. Reference this file instead of duplicating.

## When to Use Mojo vs Python

| Use Case | Language | Reason |
|----------|----------|--------|
| Evaluation harnesses | Mojo (required) | Performance, type safety |
| Metrics calculation | Mojo (required) | SIMD, optimization |
| Benchmark runners | Mojo (required) | Consistent performance |
| Statistical analysis | Mojo (required) | Numerical accuracy |
| Subprocess output capture | Python (allowed) | Mojo limitation |
| Regex processing | Python (allowed) | No Mojo stdlib support |
| GitHub API interaction | Python (allowed) | Library availability |

**Default**: Mojo unless technical limitation documented.

## Current Syntax (v0.26.1)

### Parameter Conventions

| Convention | Use For | Example |
|------------|---------|---------|
| `out self` | Constructors | `fn __init__(out self, value: Int)` |
| `mut self` | Mutating methods | `fn modify(mut self)` |
| `read` (default) | Read-only access | `fn get(self) -> Int` |
| `var` + `^` | Ownership transfer | `fn consume(var data: List[T])` |

### Deprecated Patterns

| Wrong | Correct | Notes |
|-------|---------|-------|
| `borrowed self` | `self` | Deprecated keyword |
| `inout self` | `mut self` | Deprecated keyword |
| `@value` | `@fieldwise_init` + traits | Add `(Copyable, Movable)` |
| `DynamicVector[T]` | `List[T]` | Use `.append()` not `.push_back()` |
| `-> (T1, T2)` | `-> Tuple[T1, T2]` | Explicit tuple type |

### Function Definitions

**Use `fn`** for:

- Performance-critical metrics calculations
- Functions with explicit type annotations
- SIMD/vectorized operations
- Benchmark harnesses and evaluation code
- Production APIs

**Use `def`** for:

- Python-compatible functions
- Quick prototypes
- Dynamic typing needed

### Struct Patterns

```mojo
# With @fieldwise_init (recommended for simple structs)
@fieldwise_init
struct MetricResult(Copyable, Movable):
    var value: Float64
    var ci_lower: Float64
    var ci_upper: Float64
    var n: Int

# Manual constructor (for complex initialization)
struct BenchmarkResult(Copyable, Movable):
    var pass_rate: Float64
    var cost_of_pass: Float64
    var latency: Float64
    var samples: List[Float64]

    fn __init__(out self, pass_rate: Float64, cost: Float64, latency: Float64):
        self.pass_rate = pass_rate
        self.cost_of_pass = cost
        self.latency = latency
        self.samples = List[Float64]()
```

### List Initialization

**Per [Mojo Manual](https://docs.modular.com/mojo/manual/types#list)**: Use list literals.

```mojo
# CORRECT - List literal
var tiers = [0, 1, 2, 3, 4, 5, 6]  # Type inferred as List[Int]
var results: List[Float64] = [0.23, 0.45, 0.67]  # Explicit type

# CORRECT - Empty list
var samples = List[Float64]()

# WRONG - Variadic constructor does not exist
var tiers = List[Int](0, 1, 2, 3)  # Compiler error
```

## Evaluation-Specific Patterns

### Metrics Calculation

```mojo
fn calculate_pass_rate(results: List[Bool]) -> Float64:
    """Calculate pass rate from boolean results."""
    var n = len(results)
    if n == 0:
        return 0.0

    var passes: Int = 0
    for i in range(n):
        if results[i]:
            passes += 1

    return Float64(passes) / Float64(n)

fn calculate_cost_of_pass(total_cost: Float64, pass_rate: Float64) -> Float64:
    """Calculate Cost-of-Pass metric."""
    if pass_rate <= 0.0:
        return Float64.MAX  # Undefined when no passes
    return total_cost / pass_rate
```

### Statistical Operations

```mojo
fn calculate_mean(data: List[Float64]) -> Float64:
    """Calculate arithmetic mean."""
    var n = len(data)
    if n == 0:
        return 0.0

    var sum: Float64 = 0.0
    for i in range(n):
        sum += data[i]

    return sum / Float64(n)

fn calculate_std(data: List[Float64], mean: Float64) -> Float64:
    """Calculate standard deviation."""
    var n = len(data)
    if n <= 1:
        return 0.0

    var sum_sq: Float64 = 0.0
    for i in range(n):
        var diff = data[i] - mean
        sum_sq += diff * diff

    return sqrt(sum_sq / Float64(n - 1))
```

### Benchmark Harness Pattern

```mojo
struct BenchmarkHarness(Copyable, Movable):
    var tier: Int
    var task_count: Int
    var results: List[Float64]

    fn __init__(out self, tier: Int, task_count: Int):
        self.tier = tier
        self.task_count = task_count
        self.results = List[Float64]()

    fn add_result(mut self, result: Float64):
        self.results.append(result)

    fn get_summary(self) -> MetricResult:
        var mean = calculate_mean(self.results)
        var std = calculate_std(self.results, mean)
        var n = len(self.results)

        # 95% CI approximation
        var margin = 1.96 * std / sqrt(Float64(n))

        return MetricResult(
            value=mean,
            ci_lower=mean - margin,
            ci_upper=mean + margin,
            n=n
        )
```

## Pre-Commit Checklist

- [ ] All `__init__` use `out self` (not `mut self`)
- [ ] No `inout` keyword (use `mut`)
- [ ] No `@value` decorator (use `@fieldwise_init` + traits)
- [ ] All List/Dict returns use `^` transfer operator
- [ ] Space after `var` keyword: `var a` not `vara`
- [ ] List initialization uses literals: `[1, 2, 3]` not `List[Int](1, 2, 3)`
- [ ] Metrics handle edge cases (zero denominators, empty lists)

See [mojo-anti-patterns.md](mojo-anti-patterns.md) for common mistakes.
See [CLAUDE.md](../../CLAUDE.md#mojo-development-guidelines) for complete reference.
