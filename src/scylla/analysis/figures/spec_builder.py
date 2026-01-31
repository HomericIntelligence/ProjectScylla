"""Vega-Lite specification builder utilities.

Provides helpers for creating publication-quality Vega-Lite charts with
consistent theming and color schemes.

Python Justification: altair is a Python-only library for Vega-Lite generation.
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd


def apply_publication_theme() -> None:
    """Register publication-quality theme for all charts."""
    theme = {
        "config": {
            "font": "serif",
            "axis": {
                "labelFontSize": 11,
                "titleFontSize": 13,
                "gridColor": "#e0e0e0",
                "domainColor": "#333333",
            },
            "legend": {
                "labelFontSize": 11,
                "titleFontSize": 12,
            },
            "title": {
                "fontSize": 14,
                "anchor": "start",
                "fontWeight": "normal",
            },
            "view": {
                "stroke": None,
                "continuousWidth": 400,
                "continuousHeight": 300,
            },
            "mark": {
                "tooltip": True,
            },
        }
    }

    alt.themes.register("publication", lambda: theme)
    alt.themes.enable("publication")


def save_figure(
    chart: alt.Chart,
    name: str,
    output_dir: Path,
    data: pd.DataFrame | None = None,
    render: bool = True,
    formats: list[str] | None = None,
) -> None:
    """Save chart as Vega-Lite JSON + CSV + optionally rendered images.

    Args:
        chart: Altair chart
        name: Figure name (without extension)
        output_dir: Output directory
        data: Optional DataFrame to save as CSV (if None, extracted from chart)
        render: Whether to render to raster/vector formats
        formats: List of formats to render ("png", "pdf", "svg")

    """
    if formats is None:
        formats = ["png", "pdf"]

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save Vega-Lite JSON spec
    spec_path = output_dir / f"{name}.vl.json"
    chart.save(str(spec_path))
    print(f"  Saved spec: {spec_path}")

    # Save data as CSV
    if data is not None:
        csv_path = output_dir / f"{name}.csv"
        data.to_csv(csv_path, index=False)
        print(f"  Saved data: {csv_path}")
    elif hasattr(chart, "data") and isinstance(chart.data, pd.DataFrame):
        csv_path = output_dir / f"{name}.csv"
        chart.data.to_csv(csv_path, index=False)
        print(f"  Saved data: {csv_path}")

    # Optionally render to images
    if render:
        for fmt in formats:
            try:
                img_path = output_dir / f"{name}.{fmt}"
                if fmt == "png":
                    chart.save(str(img_path), scale_factor=2.0)  # ~300 DPI
                else:
                    chart.save(str(img_path))
                print(f"  Rendered: {img_path}")
            except Exception as e:
                print(f"  Warning: Could not render {fmt}: {e}")
