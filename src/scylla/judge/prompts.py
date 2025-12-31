"""Judge prompt templates for evaluation.

This module provides prompt templates for the judge system.

Python Justification: Required for string templating.
"""

from __future__ import annotations


JUDGE_PROMPT_TEMPLATE: str = """# Agent Work Evaluation

## Context

### Original Task
{task_prompt}

### Success Criteria
{criteria}

### Scoring Rubric
{rubric}

{tier_context}

BEGIN EVALUATION
"""


TIER_CONTEXT_TEMPLATES: dict[str, str] = {
    "T0": "## Tier Context: T0 (Vanilla)\n",
    "T1": "## Tier Context: T1 (Prompted)\n",
    "T2": "## Tier Context: T2 (Skills)\n",
    "T3": "## Tier Context: T3 (Tooling)\n",
    "T4": "## Tier Context: T4 (Delegation)\n",
    "T5": "## Tier Context: T5 (Hierarchy)\n",
    "T6": "## Tier Context: T6 (Hybrid)\n",
}


def get_tier_context(tier_id: str) -> str:
    """Get tier-specific context."""
    return TIER_CONTEXT_TEMPLATES.get(tier_id, "")


def build_judge_prompt(
    task_prompt: str,
    criteria: str,
    rubric: str,
    tier_id: str | None = None,
) -> str:
    """Build the complete judge prompt."""
    tier_context = get_tier_context(tier_id) if tier_id else ""

    return JUDGE_PROMPT_TEMPLATE.format(
        task_prompt=task_prompt,
        criteria=criteria,
        rubric=rubric,
        tier_context=tier_context,
    )
