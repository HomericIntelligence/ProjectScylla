# Grading Scale Definition

> Version 1.0 | Last Updated: 2026-01-02

This document defines the **single source of truth** for grading scales used across
all ProjectScylla rubrics. All `rubric.yaml` files reference this definition.

## Industry-Aligned Grade Scale

ProjectScylla uses an industry-aligned grading scale focused on **production readiness**
rather than academic performance. This approach was chosen based on industry standards
from SonarQube, LLM evaluation frameworks, and QA scorecard best practices.

### Grade Thresholds

| Grade | Threshold | Label | Description |
|-------|-----------|-------|-------------|
| S | 1.00 | Amazing | Exceptional work that goes above and beyond requirements |
| A | 0.80 | Excellent | Production ready, no significant issues |
| B | 0.60 | Good | Minor improvements possible, meets requirements |
| C | 0.40 | Acceptable | Functional with some issues, partial credit |
| D | 0.20 | Marginal | Significant issues, barely functional |
| F | 0.00 | Failing | Does not meet requirements |

### YAML Definition

Use this exact definition in rubric files (or reference this document):

```yaml
grading:
  pass_threshold: 0.60  # Minimum score to pass (Good)
  grade_scale:
    S: 1.00    # Amazing - above and beyond
    A: 0.80    # Excellent - production ready
    B: 0.60    # Good - minor improvements possible
    C: 0.40    # Acceptable - functional with issues
    D: 0.20    # Marginal - significant issues
    F: 0.0     # Failing - does not meet requirements
```

## Grade Assignment Logic

Grades are assigned using a **greater-than-or-equal** comparison in descending order:

```python
def assign_letter_grade(score: float) -> str:
    if score >= 1.00: return "S"   # Amazing
    if score >= 0.80: return "A"   # Excellent
    if score >= 0.60: return "B"   # Good
    if score >= 0.40: return "C"   # Acceptable
    if score >= 0.20: return "D"   # Marginal
    return "F"                      # Failing
```

## Pass/Fail Determination

A score is considered **passing** if it meets the `pass_threshold`:

- **Default pass threshold**: 0.60 (Good)
- Individual tests may override this in their `rubric.yaml`

### Pass Threshold Guidelines

| Threshold | Use Case |
|-----------|----------|
| 0.80 | High-stakes evaluations requiring production quality |
| 0.60 | Standard evaluations (default) |
| 0.40 | Lenient evaluations accepting partial implementations |

## Rationale

### Why Not Academic A-F (95/85/75/65)?

Academic grading scales have several issues for software evaluation:

1. **Grade inflation bias**: 95% for an A is unrealistic for complex tasks
2. **D grade is meaningless**: In industry, you pass or fail
3. **No "production ready" semantics**: Academic scales don't map to deployment decisions

### Industry Alignment

This scale aligns with industry practices:

- **SonarQube**: Quality gates with customizable pass/fail thresholds
- **LLM Evaluation**: 5-point scales (1-5) mapping to 0.0-1.0
- **QA Scorecards**: Pass thresholds with bonus sections for exceptional work
- **ISO 5055**: Pass/fail based on weakness density thresholds

### Score Interpretation

| Score Range | Interpretation | Action |
|-------------|----------------|--------|
| 1.00 | Perfect + bonus criteria | Ship immediately |
| 0.80-0.99 | Production ready | Ship with confidence |
| 0.60-0.79 | Meets requirements | Ship after minor fixes |
| 0.40-0.59 | Partial success | Rework required |
| 0.20-0.39 | Major issues | Significant rework |
| 0.00-0.19 | Failed | Start over |

## Usage in Rubric Files

### Option 1: Reference This Document (Recommended)

```yaml
# rubric.yaml
requirements:
  # ... requirements ...

grading:
  pass_threshold: 0.60
  # Grade scale: See .claude/shared/grading-scale.md
```

### Option 2: Inline Definition

If a test requires a non-standard scale, define it inline with justification:

```yaml
grading:
  pass_threshold: 0.80  # Stricter for security-critical tests
  grade_scale:
    A: 1.00
    A-: 0.80
    B: 0.60
    C: 0.40
    D: 0.20
    F: 0.0
```

## Related Documents

- [Rubric Schema](../../docs/design/rubric-schema.md) - Full rubric YAML specification
- [Metrics Definitions](metrics-definitions.md) - Quality and economic metrics
- [Evaluation Guidelines](evaluation-guidelines.md) - LLM-as-Judge methodology
