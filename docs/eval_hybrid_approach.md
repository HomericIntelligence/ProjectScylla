# Hybrid Evaluation Approach for AI Agent Testing

## Overview

ProjectScylla now uses a **hybrid evaluation system** that combines objective checklists with subjective engineering judgment, based on best practices from Anthropic's eval methodology.

## Motivation

From Anthropic's "Demystifying Evals for AI Agents":

> "Rather than relying on a single grader type, combine multiple grader types for open-ended evaluations. Code-based graders provide objectivity but lack nuance, while model-based graders offer flexibility but require calibration."

This hybrid approach addresses the limitations of both pure objective and pure subjective evaluation:

- **Pure Checklist Problem**: Too rigid, doesn't capture overall code quality or engineering judgment
- **Pure Subjective Problem**: High variance, non-deterministic, hard to calibrate

## System Architecture

### Two Scoring Types

#### 1. Checklist Categories (`scoring_type: "checklist"`)

**Purpose**: Objective, reproducible evaluation of binary or near-binary criteria

**Characteristics**:
- Measurable outcomes (file exists, tests pass, output matches)
- Minimal subjectivity
- Can be automated or easily verified
- Typically worth 0.5-1.0 points per item

**Examples**:
```yaml
functional:
  weight: 0.35
  scoring_type: "checklist"
  items:
    - id: F1
      check: "File hello.py exists"
      points: 1.0
    - id: F2
      check: "Script produces correct output"
      points: 1.0
```

#### 2. Subjective Categories (`scoring_type: "subjective"`)

**Purpose**: Model-based judgment requiring senior engineering expertise

**Characteristics**:
- Evaluates overall quality, maintainability, appropriateness
- Continuous scale (not just 0/0.5/1)
- Balances over-engineering vs under-engineering
- Typically worth 2.0+ points to match weight

**Example**:
```yaml
overall_quality:
  weight: 0.20
  scoring_type: "subjective"
  items:
    - id: OQ1
      check: "Overall engineering judgment: appropriateness, maintainability, clarity"
      points: 2.0
```

## Granular Scoring (Not Just 0, 0.5, 1.0)

### Key Principle: Proportional Awarding

**DO**: Award points proportional to how much of the criterion is satisfied
**DON'T**: Limit yourself to 0, 0.5, or 1.0

### Examples

#### Checklist Item (max = 1.0)
```
Criterion: "Code follows PEP8 formatting"
- 1.0: Perfect PEP8 compliance
- 0.85: Minor issues (1-2 trailing whitespace)
- 0.6: Multiple minor issues (inconsistent quotes, spacing)
- 0.3: Major violations (line length, indentation)
- 0.0: No PEP8 compliance
```

#### Subjective Item (max = 2.0)
```
Criterion: "Overall engineering judgment"
- 2.0: Exceptional - perfectly scoped, maintainable, clean
- 1.7: Excellent - minor improvements possible
- 1.4: Good - solid but has unnecessary complexity
- 1.0: Acceptable - functional with some quality concerns
- 0.6: Marginal - works but significant issues
- 0.3: Poor - barely functional
- 0.0: Unacceptable - broken or completely inappropriate
```

## Weight Distribution

### Recommended Weights for Simple Tasks (e.g., Hello World)

| Category | Weight | Scoring Type | Rationale |
|----------|--------|--------------|-----------|
| Functional | 35% | Checklist | Core functionality must work |
| Code Quality | 20% | Checklist | Objective quality measures |
| Proportionality | 15% | Checklist | Appropriate scope/complexity |
| Build Pipeline | 10% | Checklist | CI/CD compliance |
| Overall Quality | 20% | Subjective | Engineering judgment |

**Total subjective weight**: 20% (2 points out of 10)

This balances:
- **80% objective** (deterministic, low variance)
- **20% subjective** (captures nuance, senior eng judgment)

## Calculation Formula

### Per-Category Score

For each category:
```python
category_achieved = sum(item_points_awarded for item in items if not NA)
category_max = sum(item_max_points for item in items if not NA)
category_score = category_achieved / category_max
```

### Final Score

```python
final_score = sum(category_score * category_weight for category in categories)
```

### Example Calculation

```yaml
# Task with 10 total points
functional: 3.5/3.5 = 1.0 (weight 0.35) → 0.35
code_quality: 3.2/4.0 = 0.8 (weight 0.20) → 0.16
proportionality: 2.5/3.5 = 0.71 (weight 0.15) → 0.107
build_pipeline: 2/3 = 0.67 (weight 0.10) → 0.067
overall_quality: 1.7/2.0 = 0.85 (weight 0.20) → 0.17

final_score = 0.35 + 0.16 + 0.107 + 0.067 + 0.17 = 0.854 (A grade)
```

## Variance Reduction

### Expected Variance Levels

| Scoring Type | Variance Target | Mitigation |
|--------------|----------------|------------|
| Checklist (80%) | ±0.01-0.02 | Objective criteria, N/A handling |
| Subjective (20%) | ±0.03-0.05 | Clear rubric, calibration examples |
| **Overall** | **±0.02** | Weighted combination reduces impact |

### Key Insight from Anthropic

> "Build 'partial credit' into scoring for multi-component tasks—an agent that correctly identifies a problem but fails final resolution is meaningfully better than one that immediately fails."

This is why we use **granular scoring** (0.0-2.0 continuous) rather than binary pass/fail.

## Calibration Strategy

### 1. Anchored Examples (in system prompt)

Provide concrete score examples at multiple levels:
- 2.0, 1.7, 1.4, 1.0, 0.6, 0.3, 0.0

### 2. Read the Transcripts

From Anthropic:
> "'Read the transcripts' emerges as paramount—reviewing agent behavior reveals whether failures reflect genuine mistakes or flawed graders."

Always validate judge scores against actual agent output for calibration.

### 3. Human Expert Validation

Periodically compare judge scores against human expert evaluations, especially for subjective categories.

## Task-Specific Rubrics

Each test should have a rubric tailored to its complexity:

### Simple Task (Hello World)
- More checklist weight (80%)
- Single subjective item (20%)
- Focus on not over-engineering

### Complex Task (Multi-file refactoring)
- More subjective weight (30-40%)
- Multiple subjective items (architecture, design patterns, testing strategy)
- Partial credit for incremental progress

## Implementation Notes

### System Prompt Updates

The judge prompt now:
1. Explains both scoring types
2. Provides granular scoring guidelines
3. Gives anchored examples for subjective scoring
4. Emphasizes proportional awarding

### Rubric Format

```yaml
categories:
  category_name:
    weight: 0.20  # Must sum to 1.0
    scoring_type: "checklist" | "subjective"
    items:
      - id: UNIQUE_ID
        check: "Criterion description"
        points: 1.0  # Max achievable
        na_condition: "Optional N/A condition"
```

### Response Format

Judge returns structured JSON:
```json
{
  "score": 0.854,
  "passed": true,
  "grade": "A",
  "reasoning": "Overall summary",
  "categories": {
    "functional": {
      "achieved": 3.5,
      "max": 3.5,
      "score": 1.0,
      "items": {
        "F1": {"achieved": 1.0, "max": 1.0, "reason": "..."},
        "F2": {"achieved": 0.85, "max": 1.0, "reason": "..."}
      }
    },
    "overall_quality": {
      "achieved": 1.7,
      "max": 2.0,
      "score": 0.85,
      "items": {
        "OQ1": {"achieved": 1.7, "max": 2.0, "reason": "Excellent but minor verbosity"}
      }
    }
  }
}
```

## Benefits Over Previous System

| Aspect | Old System | New Hybrid System |
|--------|------------|-------------------|
| Variance (identical outputs) | 14% (0.74-0.88) | Target ±2% (0.83-0.87) |
| Environmental factors | Penalized agents | N/A excluded from scoring |
| Scoring granularity | 0, 0.5, 1 only | Full continuous 0.0-max |
| Engineering judgment | None | 20% weight, calibrated |
| Transparency | Vague "criteria_scores" | Explicit category breakdown |

## Future Enhancements

1. **pass@k metrics**: Track success rate across k attempts (Anthropic recommendation)
2. **Regression detection**: Alert when established tests drop below expected pass rate
3. **Human calibration loop**: Periodic validation against expert evaluations
4. **Task-specific thresholds**: Adjust weights based on task complexity

## References

- [Anthropic: Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [LLM-as-a-Judge Survey (2024)](https://arxiv.org/abs/2411.15594)
- [Confident AI: LLM-as-a-Judge Best Practices](https://www.confident-ai.com/blog/why-llm-as-a-judge-is-the-best-llm-evaluation-method)
