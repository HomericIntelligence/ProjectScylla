# Metrics Integration Status

**Date**: 2026-02-01
**Related Issues**: #324, #325, #326, #327

---

## Integrated Metrics (✅ Complete)

### Pass-Rate (Score)
**Status**: ✅ Fully integrated
**Location**: `scripts/export_data.py`
**Coverage**:
- Normality tests (Shapiro-Wilk per model/tier)
- Omnibus tests (Kruskal-Wallis across tiers)
- Pairwise comparisons (Mann-Whitney U with Holm-Bonferroni)
- Effect sizes (Cliff's delta with bootstrap CIs)
- Correlations (with other metrics)

### Impl-Rate (Implementation Rate)
**Status**: ✅ Fully integrated (Issue #324)
**Location**: `scripts/export_data.py`
**Coverage**:
- Normality tests (Shapiro-Wilk per model/tier)
- Omnibus tests (Kruskal-Wallis across tiers)
- Pairwise comparisons (Mann-Whitney U with Holm-Bonferroni)
- Effect sizes (Cliff's delta with bootstrap CIs)
- Correlations (with score, cost, duration)

### CoP (Cost-of-Pass)
**Status**: ✅ Fully integrated (Issue #325)
**Location**: `scripts/export_data.py`
**Coverage**:
- Tier-level descriptive statistics (per model/tier)
- Frontier CoP (minimum CoP across tiers per model)
- Included in summary.json (by_model and by_tier)
- Included in statistical_results.json (tier_descriptives section)

---

## Pending Metrics (⏸️ Awaiting Data Extraction)

### R_Prog (Fine-Grained Progress Rate)
**Status**: ⏸️ Implementation exists, data extraction needed (Issue #326)
**Implementation**: `scylla/metrics/process.py::compute_r_prog()`
**Data Requirement**: ProgressTracker checkpoint files or logs from run artifacts
**Blocker**: Current run artifacts do not include ProgressTracker data

**Required for Integration**:
1. Extract ProgressTracker data from run artifacts (if available)
2. Add `r_prog` column to runs_df in `build_runs_df()`
3. Add R_Prog to statistical tests (normality, omnibus, pairwise, effect sizes)
4. Document data collection requirements for future experiments

**Formula**:
```
R_Prog = progress_steps_completed / expected_steps_total
```

**Interpretation**:
- R_Prog = 1.0: Completed all expected progress steps
- R_Prog = 0.5: Halfway through expected progress
- R_Prog < 1.0: Incomplete or stuck execution

---

### CFP (Change Fail Percentage)
**Status**: ⏸️ Implementation exists, data extraction needed (Issue #326)
**Implementation**: `scylla/metrics/process.py::compute_cfp()`
**Data Requirement**: Git commit history and revert tracking from run artifacts
**Blocker**: Current run artifacts do not include git history metadata

**Required for Integration**:
1. Extract git commit/revert data from run artifacts (if available)
2. Add `cfp` column to runs_df
3. Add CFP to statistical tests
4. Document git metadata collection for future experiments

**Formula**:
```
CFP = failed_changes / total_changes
```

**Interpretation**:
- CFP = 0.0: No failed changes (all commits successful)
- CFP = 0.2: 20% of changes reverted/failed
- CFP > 0.5: High failure rate (unstable execution)

---

### Strategic Drift
**Status**: ⏸️ Implementation exists, data extraction needed (Issue #326)
**Implementation**: `scylla/metrics/process.py::compute_strategic_drift()`
**Data Requirement**: ProgressTracker goal tracking data from run artifacts
**Blocker**: Current run artifacts do not include goal coherence tracking

**Required for Integration**:
1. Extract goal coherence data from ProgressTracker
2. Add `strategic_drift` column to runs_df
3. Add Strategic Drift to statistical tests
4. Document goal tracking requirements

**Formula**:
```
Strategic Drift = goal_deviations / total_decision_points
```

**Interpretation**:
- Strategic Drift = 0.0: Perfect goal coherence
- Strategic Drift = 0.1: 10% of decisions deviated from goal
- Strategic Drift > 0.5: High drift (losing focus)

---

### PR Revert Rate
**Status**: ⏸️ Implementation exists, data extraction needed (Issue #326)
**Implementation**: `scylla/metrics/process.py::compute_pr_revert_rate()`
**Data Requirement**: GitHub PR data from run artifacts
**Blocker**: Current run artifacts do not include PR metadata

**Required for Integration**:
1. Extract PR revert data from GitHub API or run logs
2. Add `pr_revert_rate` column to runs_df
3. Add PR Revert Rate to statistical tests
4. Document PR tracking requirements

**Formula**:
```
PR Revert Rate = reverted_prs / total_prs
```

**Interpretation**:
- PR Revert Rate = 0.0: No PR reversions
- PR Revert Rate = 0.1: 10% of PRs reverted
- PR Revert Rate > 0.3: High reversion rate (quality issues)

---

### TTFT (Time To First Token)
**Status**: ⏸️ Implementation exists, data extraction needed (Issue #327)
**Implementation**: `scylla/metrics/latency.py::LatencyTracker`
**Data Requirement**: Latency checkpoint files with TTFT timestamps
**Blocker**: Current run artifacts do not include detailed latency tracking

**Required for Integration**:
1. Extract TTFT data from latency checkpoint files
2. Add `ttft` column to runs_df
3. Add TTFT to statistical tests (tier comparisons)
4. Document latency tracking requirements

**Current Basic Support**: `duration_seconds` field exists in runs_df (total elapsed time)

**11 Phase Breakdown** (from LatencyTracker):
1. worktree_setup
2. agent_init
3. test_execution
4. judge_evaluation
5. agent_thinking
6. agent_tool_calls
7. judge_thinking
8. result_aggregation
9. report_generation
10. cleanup
11. total_elapsed

**Required for Full Integration**:
- Extract all 11 phase durations from run artifacts
- Add phase-level columns to runs_df
- Create stacked bar chart showing phase breakdowns per tier

---

## Integration Checklist

### For Each New Metric

- [ ] **Data Extraction**: Implement artifact parsing to extract metric
- [ ] **DataFrame Integration**: Add column to runs_df in `build_runs_df()`
- [ ] **Aggregation**: Add to subtests_df in `build_subtests_df()` (mean, median, std)
- [ ] **Normality Tests**: Add to `compute_statistical_results()` normality section
- [ ] **Omnibus Tests**: Add to `compute_statistical_results()` omnibus section
- [ ] **Pairwise Comparisons**: Add to `compute_statistical_results()` pairwise section
- [ ] **Effect Sizes**: Add to `compute_statistical_results()` effect_sizes section
- [ ] **Correlations**: Add relevant metric pairs to correlations section
- [ ] **Summary Statistics**: Add to summary.json (by_model, by_tier, overall_stats)
- [ ] **Test Coverage**: Create unit test verifying metric appears in all sections
- [ ] **Documentation**: Update this file with integration status

---

## Recommendations for Future Experiments

### To Enable Process Metrics

1. **ProgressTracker Integration**:
   ```python
   # In experiment runner, add checkpoint logging
   tracker = ProgressTracker()
   tracker.checkpoint("goal_set", metadata={"goal": task_description})
   tracker.checkpoint("step_completed", metadata={"step": i, "expected_total": n})
   tracker.save(run_dir / "progress_tracker.json")
   ```

2. **Git Metadata Collection**:
   ```bash
   # After each run, capture git history
   git log --oneline --all > ${RUN_DIR}/git_history.txt
   git reflog > ${RUN_DIR}/git_reflog.txt
   ```

3. **PR Metadata Collection**:
   ```bash
   # After PR operations, capture PR state
   gh pr list --json number,state,createdAt,mergedAt,revertedAt > ${RUN_DIR}/pr_metadata.json
   ```

### To Enable Latency Metrics

1. **Latency Tracker Integration**:
   ```python
   # In experiment runner, wrap each phase
   latency_tracker = LatencyTracker()
   with latency_tracker.phase("worktree_setup"):
       setup_worktree()
   with latency_tracker.phase("agent_init"):
       init_agent()
   # ... for all 11 phases
   latency_tracker.save(run_dir / "latency_tracker.json")
   ```

2. **TTFT Capture**:
   ```python
   # Capture first token timestamp explicitly
   start_time = time.time()
   first_token_time = None
   for token in agent.stream_response():
       if first_token_time is None:
           first_token_time = time.time()
           ttft = first_token_time - start_time
   ```

---

## Summary Table

| Metric | Status | In Pipeline | Data Available | Integration Ready |
|--------|--------|-------------|----------------|-------------------|
| Pass-Rate (Score) | ✅ Complete | YES | YES | N/A |
| Impl-Rate | ✅ Complete (#324) | YES | YES | N/A |
| CoP | ✅ Complete (#325) | YES | YES (computed) | N/A |
| Frontier CoP | ✅ Complete (#325) | YES | YES (computed) | N/A |
| Consistency | ✅ Computed | YES (subtests_df) | YES (computed) | Needs statistical tests |
| R_Prog | ⏸️ Pending (#326) | NO | NO | Needs data extraction |
| CFP | ⏸️ Pending (#326) | NO | NO | Needs data extraction |
| Strategic Drift | ⏸️ Pending (#326) | NO | NO | Needs data extraction |
| PR Revert Rate | ⏸️ Pending (#326) | NO | NO | Needs data extraction |
| TTFT | ⏸️ Pending (#327) | NO | NO | Needs data extraction |
| Phase Latency | ⏸️ Pending (#327) | NO | NO | Needs data extraction |
| Duration | ✅ Complete | YES | YES | Needs statistical tests |

**Key**: ✅ = Complete | ⏸️ = Pending | ❌ = Blocked
