"""Protocols for the reporting module."""

from pathlib import Path
from typing import Protocol

from scylla.reporting.markdown import ReportData


class ReportWriter(Protocol):
    """Protocol for report generator classes.

    Both ``MarkdownReportGenerator`` and ``JsonReportGenerator`` satisfy this
    protocol, and any future generator (e.g. HTML) only needs to implement
    these three methods to be accepted by ``FORMAT_GENERATORS``.
    """

    def __init__(self, base_dir: Path) -> None:
        """Initialise the generator with a base output directory."""
        ...

    def generate_report(self, data: ReportData) -> str:
        """Render *data* to a string in the target format.

        Args:
            data: Structured report data.

        Returns:
            The rendered report as a string.

        """
        ...

    def write_report(self, data: ReportData, output_path: Path | None = None) -> Path:
        """Write the rendered report to disk and return the file path.

        Args:
            data: Structured report data.
            output_path: Explicit destination path.  When ``None`` the
                generator chooses a convention-based path under its
                ``base_dir``.

        Returns:
            Path to the written file.

        """
        ...
