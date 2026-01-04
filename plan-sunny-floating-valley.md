# Plan: Enhanced Hierarchical Reports with Score Tables and Detailed Token Statistics

## Goal

Enhance E2E reports to provide detailed comparison tables at each level, with:
1. **Score tables** for easy comparison across tiers/subtests/runs
2. **Per-criteria tables** showing best run scores from each unit
3. **Detailed token statistics** including cache read/write at all report levels
4. Scores duplicated for comparison, but reasoning only in detailed sections

## Report Hierarchy

```
Experiment Report (summary of best from each tier)
  └── Tier Report (summary of best from each subtest)
        └── Subtest Report (summary of best from each run)
              └── Run Report (individual run details)
```

## Token Data Available (from Claude Code JSON output)

```json
{
  "usage": {
    "input_tokens": 15,
    "cache_creation_input_tokens": 27655,
    "cache_read_input_tokens": 82278,
    "output_tokens": 422
  },
  "modelUsage": {
    "claude-sonnet-4-5-20250929": {
      "inputTokens": 15,
      "outputTokens": 422,
      "cacheReadInputTokens": 82278,
      "cacheCreationInputTokens": 27655,
      "costUSD": 0.134
    }
  }
}
```

## Implementation

### Phase 1: Create TokenStats Dataclass

**File: `src/scylla/e2e/models.py`**

Add new dataclass for detailed token statistics:
```python
@dataclass
class TokenStats:
    """Detailed token usage statistics.

    Tracks all token types including cache operations for
    accurate cost analysis and efficiency metrics.
    """
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0

    @property
    def total_input(self) -> int:
        """Total input tokens including cache."""
        return self.input_tokens + self.cache_read_tokens

    @property
    def total_tokens(self) -> int:
        """Total all tokens."""
        return self.total_input + self.output_tokens + self.cache_creation_tokens

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "cache_read_tokens": self.cache_read_tokens,
        }

    def __add__(self, other: TokenStats) -> TokenStats:
        """Enable summing TokenStats."""
        return TokenStats(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_creation_tokens=self.cache_creation_tokens + other.cache_creation_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
        )
```

### Phase 2: Update RunResult with TokenStats

**File: `src/scylla/e2e/models.py`**

Replace `tokens_input` and `tokens_output` in `RunResult` with `token_stats`:
```python
@dataclass
class RunResult:
    # ... existing fields ...
    token_stats: TokenStats = field(default_factory=TokenStats)
    criteria_scores: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Keep legacy properties for backwards compatibility
    @property
    def tokens_input(self) -> int:
        return self.token_stats.total_input

    @property
    def tokens_output(self) -> int:
        return self.token_stats.output_tokens
```

### Phase 3: Update Claude Code Adapter to Extract Full Token Stats

**File: `src/scylla/adapters/claude_code.py`**

Update `_parse_token_usage()` to return `TokenStats`:
```python
def _parse_token_usage(self, stdout: str, stderr: str) -> TokenStats:
    try:
        data = json.loads(stdout.strip())
        usage = data.get("usage", {})
        return TokenStats(
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
            cache_read_tokens=usage.get("cache_read_input_tokens", 0),
        )
    except (json.JSONDecodeError, AttributeError):
        # Fallback to regex parsing...
        return TokenStats(input_tokens=..., output_tokens=...)
```

### Phase 4: Update Aggregation Models

**File: `src/scylla/e2e/models.py`**

Add `token_stats` to `SubTestResult`, `TierResult`, `ExperimentResult`:
```python
@dataclass
class SubTestResult:
    # ... existing fields ...
    token_stats: TokenStats = field(default_factory=TokenStats)

@dataclass
class TierResult:
    # ... existing fields ...
    token_stats: TokenStats = field(default_factory=TokenStats)

@dataclass
class ExperimentResult:
    # ... existing fields ...
    token_stats: TokenStats = field(default_factory=TokenStats)
```

### Phase 5: Update Subtest Aggregation

**File: `src/scylla/e2e/subtest_executor.py`**

In `_aggregate_results()`, aggregate token stats:
```python
from functools import reduce

token_stats = reduce(lambda a, b: a + b,
                     [r.token_stats for r in runs],
                     TokenStats())
```

Store criteria in RunResult:
```python
criteria_scores=judgment.get("criteria_scores", {}),
```

### Phase 6: Enhance Run Report

**File: `src/scylla/e2e/run_report.py` - `generate_run_report()`**

Update token display to show detailed breakdown:
```markdown
| Tokens | 82,293 in (82K cached) / 422 out / 27K created |
```

Or as a sub-table:
```markdown
## Token Usage

| Type | Count |
|------|-------|
| Input | 15 |
| Output | 422 |
| Cache Read | 82,278 |
| Cache Created | 27,655 |
| **Total** | **110,370** |
```

### Phase 7: Enhance Subtest Report

**File: `src/scylla/e2e/run_report.py` - `save_subtest_report()`**

Add after summary table:

```markdown
## Runs Overview

| Run | Score | Grade | Pass | Cost | In | Out | Cache R | Cache W |
|-----|-------|-------|------|------|-----|-----|---------|---------|
| 01  | 0.92  | A     | ✓    | $0.19| 15  | 422 | 82K     | 28K     |
| 02  | 0.88  | B+    | ✓    | $0.21| 20  | 450 | 85K     | 0       |

## Per-Criteria Scores (All Runs)

| Criterion | Run 01 | Run 02 | Best |
|-----------|--------|--------|------|
| correctness | 1.00 | 0.95 | 1.00 |
| completeness | 0.95 | 0.90 | 0.95 |

## Token Statistics

| Metric | Value |
|--------|-------|
| Total Input | 35 |
| Total Output | 872 |
| Cache Read | 167K |
| Cache Created | 28K |
```

### Phase 8: Enhance Tier Report

**File: `src/scylla/e2e/run_report.py` - `save_tier_report()`**

```markdown
## Subtests Overview

| Subtest | Score | Pass | Cost | In | Out | Cache R | Cache W | Best |
|---------|-------|------|------|-----|-----|---------|---------|------|
| 00      | 0.92  | 100% | $0.38| 35  | 872 | 167K    | 28K     | ★    |
| 01      | 0.88  | 80%  | $0.42| 40  | 950 | 180K    | 30K     |      |

## Per-Criteria Scores (Best Run per Subtest)

| Criterion | 00 | 01 | 02 | Best |
|-----------|----|----|----|----|
| correctness | 1.00 | 0.95 | 0.90 | 1.00 |

## Token Statistics

| Metric | Value |
|--------|-------|
| Total Input | 75 |
| Total Output | 1,822 |
| Cache Read | 347K |
| Cache Created | 58K |
```

### Phase 9: Enhance Experiment Report

**File: `src/scylla/e2e/run_report.py` - `save_experiment_report()`**

```markdown
## Tiers Overview

| Tier | Best | Score | Cost | In | Out | Cache R | Cache W | CoP |
|------|------|-------|------|-----|-----|---------|---------|-----|
| T0   | 04   | 0.92  | $3.77| 150 | 6K  | 1.2M    | 200K    | $4.10 |
| T1   | 02   | 0.95  | $5.20| 200 | 9K  | 1.8M    | 250K    | $5.47 |

## Per-Criteria Scores (Best Subtest per Tier)

| Criterion | T0 | T1 | Best |
|-----------|----|----|------|
| correctness | 1.00 | 0.98 | 1.00 |

## Token Statistics

| Metric | Value |
|--------|-------|
| Total Input | 350 |
| Total Output | 15K |
| Cache Read | 3M |
| Cache Created | 450K |
```

## Files to Modify

| File | Changes |
|------|---------|
| `src/scylla/e2e/models.py` | Add `TokenStats` dataclass; Update `RunResult`, `SubTestResult`, `TierResult`, `ExperimentResult` |
| `src/scylla/adapters/claude_code.py` | Update `_parse_token_usage()` to return `TokenStats` |
| `src/scylla/adapters/base.py` | Update `AdapterResult` to use `TokenStats` |
| `src/scylla/e2e/subtest_executor.py` | Aggregate token stats; Store criteria_scores in RunResult |
| `src/scylla/e2e/run_report.py` | Enhance all report levels with comparison tables and token stats |
| `src/scylla/e2e/runner.py` | Aggregate tier/experiment token stats |

## Migration Notes

- Keep backwards compatible properties (`tokens_input`, `tokens_output`) on RunResult
- Existing result.json files will still load (missing fields default to 0)
- New reports will show detailed token breakdown

## Testing

```bash
pixi run python scripts/run_e2e.py \
    --test test-001 \
    --tiers T0 \
    --subtests 2 \
    --runs 2 \
    --experiment-id report-enhancement-test
```

Verify:
- Detailed token stats (input, output, cache read, cache create) at all levels
- Comparison tables show all runs/subtests/tiers
- Per-criteria tables aggregate correctly
- Best scores highlighted with ★
