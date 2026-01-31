"""Figure generation for paper.

Each figure module provides generation functions that produce Vega-Lite
JSON specifications and CSV data files.
"""

import re

# Tier ordering (consistent across all figures and tables)
# NOTE: This is a fallback constant. Functions should derive tier order from data.
TIER_ORDER = ["T0", "T1", "T2", "T3", "T4", "T5", "T6"]


def derive_tier_order(df, tier_column: str = "tier") -> list[str]:
    """Derive tier order from data, sorted naturally (T0 < T1 < ... < T99).

    Args:
        df: DataFrame containing tier data
        tier_column: Name of the column containing tier IDs

    Returns:
        List of tier IDs in natural sorted order

    """
    tiers = sorted(
        df[tier_column].unique(),
        key=lambda t: int(re.search(r"\d+", t).group()) if re.search(r"\d+", t) else 0,
    )
    return list(tiers)


# Color palettes (consistent across all figures)
COLORS = {
    "models": {"Sonnet 4.5": "#4C78A8", "Haiku 4.5": "#E45756"},
    "tiers": {
        "T0": "#66c2a5",
        "T1": "#fc8d62",
        "T2": "#8da0cb",
        "T3": "#e78ac3",
        "T4": "#a6d854",
        "T5": "#ffd92f",
        "T6": "#e5c494",
    },
    "grades": {
        "S": "#FFD700",
        "A": "#2ecc71",
        "B": "#3498db",
        "C": "#f39c12",
        "D": "#e67e22",
        "F": "#e74c3c",
    },
    "judges": {
        "Opus 4.5": "#4C78A8",
        "Sonnet 4.5": "#E45756",
        "Haiku 4.5": "#72B7B2",
    },
    "criteria": {
        "functional": "#4C78A8",
        "code_quality": "#E45756",
        "proportionality": "#72B7B2",
        "build_pipeline": "#F58518",
        "overall_quality": "#54A24B",
    },
    "phases": {
        "Agent Execution": "#4C78A8",
        "Judge Evaluation": "#E45756",
    },
    "token_types": {
        "Input (Fresh)": "#4C78A8",
        "Input (Cached)": "#72B7B2",
        "Output": "#E45756",
        "Cache Creation": "#F58518",
    },
}

# Dynamic palette for unknown models/judges
_DYNAMIC_PALETTE = [
    "#4C78A8",  # Blue
    "#E45756",  # Red
    "#72B7B2",  # Teal
    "#F58518",  # Orange
    "#54A24B",  # Green
    "#B279A2",  # Purple
    "#FF9DA6",  # Pink
    "#9D755D",  # Brown
    "#BAB0AC",  # Gray
    "#EECA3B",  # Yellow
]


def get_color(category: str, key: str) -> str:
    """Get color for a key, using static colors or dynamic palette.

    Args:
        category: Color category ("models", "judges", "tiers", etc.)
        key: Key within category

    Returns:
        Hex color code

    """
    if category in COLORS and key in COLORS[category]:
        return COLORS[category][key]
    else:
        # Use deterministic hash to assign color from dynamic palette
        index = hash(key) % len(_DYNAMIC_PALETTE)
        return _DYNAMIC_PALETTE[index]


def get_color_scale(category: str, keys: list[str]) -> tuple[list[str], list[str]]:
    """Get color scale domain and range for Altair.

    Args:
        category: Color category ("models", "judges", "tiers", etc.)
        keys: List of keys to assign colors to

    Returns:
        Tuple of (domain, range) for alt.Scale()

    """
    domain = list(keys)
    range_ = [get_color(category, key) for key in keys]
    return domain, range_


def register_colors(category: str, mapping: dict[str, str]) -> None:
    """Register or update colors for a category at runtime.

    Allows dynamic registration of colors from data without hardcoding.

    Args:
        category: Color category to register/update
        mapping: Dictionary mapping keys to hex color codes

    Example:
        >>> register_colors("models", {"GPT-4": "#FF6B6B", "Claude": "#4ECDC4"})

    """
    if category not in COLORS:
        COLORS[category] = {}
    COLORS[category].update(mapping)


__all__ = [
    "COLORS",
    "TIER_ORDER",
    "derive_tier_order",
    "get_color",
    "get_color_scale",
    "register_colors",
]
