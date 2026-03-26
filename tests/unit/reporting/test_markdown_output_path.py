"""Tests for MarkdownReportGenerator.write_report() output_path parameter."""

import tempfile
from pathlib import Path

import pytest

from scylla.reporting.markdown import (
    MarkdownReportGenerator,
    ReportData,
    create_report_data,
)


def _make_report_data() -> ReportData:
    """Create minimal ReportData for testing."""
    return create_report_data(
        test_id="001-test",
        test_name="Test Name",
        timestamp="2024-01-15T14:30:00Z",
    )


class TestWriteReportOutputPath:
    """Tests for the output_path parameter on write_report()."""

    def test_write_report_with_explicit_output_path(self) -> None:
        """When output_path is provided, write to that exact path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = MarkdownReportGenerator(Path(tmpdir))
            data = _make_report_data()
            target = Path(tmpdir) / "my-custom-report.md"

            result = generator.write_report(data, output_path=target)

            assert result == target
            assert target.exists()
            content = target.read_text()
            assert "# Evaluation Report:" in content

    def test_write_report_with_explicit_output_path_creates_parents(self) -> None:
        """Parent directories are created when output_path has non-existent parents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = MarkdownReportGenerator(Path(tmpdir))
            data = _make_report_data()
            target = Path(tmpdir) / "deep" / "nested" / "dir" / "report.md"

            result = generator.write_report(data, output_path=target)

            assert result == target
            assert target.exists()

    def test_write_report_with_explicit_output_path_custom_filename(self) -> None:
        """Custom filenames (not report.md) are honored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = MarkdownReportGenerator(Path(tmpdir))
            data = _make_report_data()
            target = Path(tmpdir) / "results-2024.md"

            result = generator.write_report(data, output_path=target)

            assert result.name == "results-2024.md"
            assert result.exists()

    def test_write_report_without_output_path_uses_convention(self) -> None:
        """Default behavior (no output_path) writes to {base_dir}/{test_id}/report.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = MarkdownReportGenerator(Path(tmpdir))
            data = _make_report_data()

            result = generator.write_report(data)

            expected = Path(tmpdir) / "001-test" / "report.md"
            assert result == expected
            assert result.exists()

    def test_write_report_output_path_none_uses_convention(self) -> None:
        """Explicitly passing output_path=None falls back to convention."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = MarkdownReportGenerator(Path(tmpdir))
            data = _make_report_data()

            result = generator.write_report(data, output_path=None)

            expected = Path(tmpdir) / "001-test" / "report.md"
            assert result == expected
            assert result.exists()

    @pytest.mark.parametrize(
        "filename",
        ["report.md", "custom.md", "evaluation-output.markdown", "results.txt"],
    )
    def test_write_report_various_filenames(self, filename: str) -> None:
        """Various filenames are all honored when passed as output_path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = MarkdownReportGenerator(Path(tmpdir))
            data = _make_report_data()
            target = Path(tmpdir) / filename

            result = generator.write_report(data, output_path=target)

            assert result.name == filename
            assert result.exists()
