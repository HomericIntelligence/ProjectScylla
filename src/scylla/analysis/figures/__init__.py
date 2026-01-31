"""Figure generation for paper.

Each figure module provides generation functions that produce Vega-Lite
JSON specifications and CSV data files.
"""

# Tier ordering (consistent across all figures and tables)
TIER_ORDER = ["T0", "T1", "T2", "T3", "T4", "T5", "T6"]

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
        "claude-opus-4-5-20251101": "#4C78A8",
        "claude-sonnet-4-5-20250129": "#E45756",
        "claude-haiku-4-5-20241223": "#72B7B2",
    },
    "criteria": {
        "functional": "#4C78A8",
        "code_quality": "#E45756",
        "proportionality": "#72B7B2",
        "build_pipeline": "#F58518",
        "overall_quality": "#54A24B",
    },
}

# Dynamic color palette for unknown keys (10 distinct colors)
_DYNAMIC_PALETTE = [
    "#4C78A8",  # Blue
    "#E45756",  # Red
    "#72B7B2",  # Teal
    "#F58518",  # Orange
    "#54A24B",  # Green
    "#EECA3B",  # Yellow
    "#B279A2",  # Purple
    "#FF9DA6",  # Pink
    "#9D755D",  # Brown
    "#BAB0AC",  # Gray
]


def get_color(category: str, key: str) -> str:
    """Get color for a specific key in a category.

    Args:
        category: Color category ("models", "tiers", "grades", "judges", "criteria")
        key: Key to look up

    Returns:
        Hex color code

    Examples:
        >>> get_color("models", "Sonnet 4.5")
        '#4C78A8'
        >>> get_color("models", "Opus 4.5")  # Unknown, uses palette
        '#72B7B2'

    """
    # Check if key exists in static colors
    if category in COLORS and key in COLORS[category]:
        return COLORS[category][key]

    # Use deterministic hash to assign from dynamic palette
    color_index = hash(f"{category}:{key}") % len(_DYNAMIC_PALETTE)
    return _DYNAMIC_PALETTE[color_index]


def get_color_scale(category: str, keys: list[str]) -> tuple[list[str], list[str]]:
    """Get Altair color scale (domain, range) for a list of keys.

    Args:
        category: Color category
        keys: List of keys to create scale for

    Returns:
        Tuple of (domain, range) for Altair Scale

    Examples:
        >>> domain, range_ = get_color_scale("models", ["Sonnet 4.5", "Haiku 4.5"])
        >>> domain
        ['Sonnet 4.5', 'Haiku 4.5']
        >>> range_
        ['#4C78A8', '#E45756']

    """
    domain = sorted(keys)
    range_ = [get_color(category, key) for key in domain]
    return domain, range_


__all__ = ["COLORS", "TIER_ORDER", "get_color", "get_color_scale"]
