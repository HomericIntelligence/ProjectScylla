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

Use this exact definition in rubric files by referencing this document:

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

Reference this document

```yaml
# rubric.yaml
requirements:
  # ... requirements ...

grading:
  pass_threshold: 0.60
  # Grade scale: See docs/design/grading-scale.md
```

## Related Documents

- [Rubric Schema](../../docs/design/rubric-schema.md) - Full rubric YAML specification
- [Metrics Definitions](metrics-definitions.md) - Quality and economic metrics
- [Evaluation Guidelines](evaluation-guidelines.md) - LLM-as-Judge methodology
