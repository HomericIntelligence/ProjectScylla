"""Ablation score metrics for component contribution analysis.

This module provides metrics for measuring the isolated contribution
of individual components to overall system performance, following
the ablation study methodology described in the research documentation.

Python Justification: Required for statistical calculations and data structures.

References:
- docs/research.md: Section 3.2 (Ablation Study Blueprint)
- .claude/shared/metrics-definitions.md: Ablation Score definition

"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ComponentRole(Enum):
    """Roles of components in the agent architecture."""

    # Core components
    TASK_DECOMPOSER = "task_decomposer"  # High-level planning
    ACTOR = "actor"  # Primary execution
    MONITOR = "monitor"  # Error detection
    EVALUATOR = "evaluator"  # Quality assessment
    ORCHESTRATOR = "orchestrator"  # Coordination

    # Tier-specific components
    SYSTEM_PROMPT = "system_prompt"  # T1
    SKILLS = "skills"  # T2
    TOOLS = "tools"  # T3
    DELEGATION = "delegation"  # T4
    HIERARCHY = "hierarchy"  # T5
    AGENTIC_RAG = "agentic_rag"  # T6


@dataclass
class AblationResult:
    """Result of ablating a single component.

    Attributes:
        component: The component that was removed.
        baseline_score: Performance with all components.
        ablated_score: Performance with component removed.
        ablation_score: Contribution of the component (baseline - ablated).
        relative_impact: Percentage impact on baseline performance.
        cost_baseline: Cost with all components.
        cost_ablated: Cost with component removed.
        cost_savings: Cost reduction from removing component.

    """

    component: ComponentRole
    baseline_score: float
    ablated_score: float
    ablation_score: float
    relative_impact: float
    cost_baseline: float = 0.0
    cost_ablated: float = 0.0
    cost_savings: float = 0.0


@dataclass
class AblationStudy:
    """Complete ablation study across multiple components.

    Attributes:
        tier_id: Tier being analyzed.
        baseline_score: Performance with all components.
        baseline_cost: Cost with all components.
        results: Ablation results for each component.
        critical_components: Components with highest impact.
        redundant_components: Components with negligible impact.

    """

    tier_id: str
    baseline_score: float
    baseline_cost: float
    results: list[AblationResult] = field(default_factory=list)
    critical_components: list[ComponentRole] = field(default_factory=list)
    redundant_components: list[ComponentRole] = field(default_factory=list)


def calculate_ablation_score(
    baseline_score: float,
    ablated_score: float,
) -> float:
    """Calculate the ablation score for a component.

    The ablation score measures the isolated contribution of a component
    to overall system performance. Positive values indicate the component
    improves performance; negative values indicate it hurts performance.

    Formula: baseline_score - ablated_score

    Args:
        baseline_score: Performance with all components present.
        ablated_score: Performance with the component removed.

    Returns:
        Ablation score (positive = helps, negative = hurts, ~0 = no effect).

    Reference:
        .claude/shared/metrics-definitions.md - Ablation Score

    """
    return baseline_score - ablated_score


def calculate_relative_impact(
    baseline_score: float,
    ablation_score: float,
) -> float:
    """Calculate relative impact as percentage of baseline.

    Args:
        baseline_score: Performance with all components.
        ablation_score: Contribution of the component.

    Returns:
        Relative impact as a decimal (0.1 = 10% of baseline).
        Returns 0.0 if baseline is zero.

    """
    if baseline_score == 0:
        return 0.0
    return ablation_score / baseline_score


def analyze_component(
    component: ComponentRole,
    baseline_score: float,
    ablated_score: float,
    baseline_cost: float = 0.0,
    ablated_cost: float = 0.0,
) -> AblationResult:
    """Analyze the contribution of a single component.

    Args:
        component: The component being analyzed.
        baseline_score: Performance with all components.
        ablated_score: Performance with component removed.
        baseline_cost: Cost with all components.
        ablated_cost: Cost with component removed.

    Returns:
        AblationResult with contribution metrics.

    """
    ablation = calculate_ablation_score(baseline_score, ablated_score)
    impact = calculate_relative_impact(baseline_score, ablation)
    cost_savings = baseline_cost - ablated_cost

    return AblationResult(
        component=component,
        baseline_score=baseline_score,
        ablated_score=ablated_score,
        ablation_score=ablation,
        relative_impact=impact,
        cost_baseline=baseline_cost,
        cost_ablated=ablated_cost,
        cost_savings=cost_savings,
    )


def run_ablation_study(
    tier_id: str,
    baseline_score: float,
    baseline_cost: float,
    component_results: dict[ComponentRole, tuple[float, float]],
    critical_threshold: float = 0.1,
    redundant_threshold: float = 0.01,
) -> AblationStudy:
    """Run a complete ablation study for a tier.

    Args:
        tier_id: Tier being analyzed.
        baseline_score: Performance with all components.
        baseline_cost: Cost with all components.
        component_results: Dict mapping component -> (ablated_score, ablated_cost).
        critical_threshold: Minimum relative impact for critical classification.
        redundant_threshold: Maximum relative impact for redundant classification.

    Returns:
        AblationStudy with complete analysis.

    """
    results: list[AblationResult] = []
    critical: list[ComponentRole] = []
    redundant: list[ComponentRole] = []

    for component, (ablated_score, ablated_cost) in component_results.items():
        result = analyze_component(
            component=component,
            baseline_score=baseline_score,
            ablated_score=ablated_score,
            baseline_cost=baseline_cost,
            ablated_cost=ablated_cost,
        )
        results.append(result)

        # Classify component
        if abs(result.relative_impact) >= critical_threshold:
            critical.append(component)
        elif abs(result.relative_impact) <= redundant_threshold:
            redundant.append(component)

    # Sort results by impact (highest first)
    results.sort(key=lambda r: abs(r.ablation_score), reverse=True)

    return AblationStudy(
        tier_id=tier_id,
        baseline_score=baseline_score,
        baseline_cost=baseline_cost,
        results=results,
        critical_components=critical,
        redundant_components=redundant,
    )


def compare_tier_ablations(
    studies: list[AblationStudy],
) -> dict[ComponentRole, list[float]]:
    """Compare ablation scores for components across tiers.

    Args:
        studies: List of ablation studies from different tiers.

    Returns:
        Dict mapping component -> list of ablation scores across tiers.

    """
    comparison: dict[ComponentRole, list[float]] = {}

    for study in studies:
        for result in study.results:
            if result.component not in comparison:
                comparison[result.component] = []
            comparison[result.component].append(result.ablation_score)

    return comparison
