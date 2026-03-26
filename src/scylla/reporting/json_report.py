"""JSON report generator for evaluation results."""

import json
import math
from dataclasses import asdict
from pathlib import Path
from typing import Any

from scylla.reporting.markdown import ReportData


def _sanitize_for_json(obj: Any) -> Any:
    """Recursively replace float('inf'), float('-inf'), and float('nan') with None.

    JSON does not support these IEEE 754 special values, so they must be
    converted before serialization.

    Args:
        obj: Any Python object (typically the output of dataclasses.asdict)

    Returns:
        Sanitized object safe for json.dumps

    """
    if isinstance(obj, float):
        if math.isinf(obj) or math.isnan(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(item) for item in obj]
    return obj


class JsonReportGenerator:
    """Generates JSON evaluation reports."""

    def __init__(self, base_dir: Path) -> None:
        """Initialize JSON report generator.

        Args:
            base_dir: Base directory for reports (e.g., 'reports/')

        """
        self.base_dir = base_dir

    def get_report_dir(self, test_id: str) -> Path:
        """Get the directory path for a test report.

        Args:
            test_id: Test identifier

        Returns:
            Path to report directory

        """
        return self.base_dir / test_id

    def generate_report(self, data: ReportData) -> str:
        """Generate a complete JSON report string.

        Args:
            data: Report data

        Returns:
            JSON string with indentation

        """
        raw = asdict(data)
        sanitized = _sanitize_for_json(raw)
        return json.dumps(sanitized, indent=2)

    def write_report(self, data: ReportData, output_path: Path | None = None) -> Path:
        """Generate and write a JSON report to file.

        Args:
            data: Report data
            output_path: Explicit file path to write the report to. When
                provided, the report is written to this exact path instead of
                the convention-based ``{base_dir}/{test_id}/report.json``.

        Returns:
            Path to written report file.

        """
        if output_path is not None:
            report_path = output_path
        else:
            report_dir = self.get_report_dir(data.test_id)
            report_dir.mkdir(parents=True, exist_ok=True)
            report_path = report_dir / "report.json"

        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_content = self.generate_report(data)
        report_path.write_text(report_content)

        return report_path
