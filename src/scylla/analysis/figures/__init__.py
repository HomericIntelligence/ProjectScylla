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


__all__ = ["COLORS", "TIER_ORDER", "get_color", "get_color_scale"]
