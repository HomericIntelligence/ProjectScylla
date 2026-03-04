"""Tests for scripts/check_coverage.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from check_coverage import (
    check_coverage,
    get_module_threshold,
    load_coverage_config,
    parse_coverage_report,
)


# ---------------------------------------------------------------------------
# load_coverage_config
# ---------------------------------------------------------------------------


class TestLoadCoverageConfig:
    """Tests for load_coverage_config()."""

    def test_returns_defaults_when_file_missing(self, tmp_path: Path) -> None:
        """Returns default config when coverage.toml does not exist."""
        config = load_coverage_config(tmp_path / "nonexistent.toml")
        assert "coverage" in config
        assert config["coverage"]["target"] == 90.0
        assert config["coverage"]["minimum"] == 80.0

    def test_loads_valid_toml_file(self, tmp_path: Path) -> None:
        """Loads coverage config from a valid TOML file."""
        config_file = tmp_path / "coverage.toml"
        config_file.write_text("[coverage]\ntarget = 85.0\nminimum = 75.0\n")
        config = load_coverage_config(config_file)
        assert config["coverage"]["target"] == 85.0
        assert config["coverage"]["minimum"] == 75.0

    def test_returns_defaults_on_parse_error(self, tmp_path: Path) -> None:
        """Returns defaults when TOML file is malformed."""
        config_file = tmp_path / "bad.toml"
        config_file.write_bytes(b"\x00\x01invalid")
        config = load_coverage_config(config_file)
        assert "coverage" in config


# ---------------------------------------------------------------------------
# get_module_threshold
# ---------------------------------------------------------------------------


class TestGetModuleThreshold:
    """Tests for get_module_threshold()."""

    def test_returns_default_minimum_for_unknown_path(self) -> None:
        """Returns overall minimum for unrecognized path."""
        config = {"coverage": {"minimum": 70.0, "modules": {}}}
        result = get_module_threshold("unknown/path", config)
        assert result == 70.0

    def test_returns_exact_match_threshold(self) -> None:
        """Returns module-specific threshold for exact path match."""
        config = {
            "coverage": {
                "minimum": 70.0,
                "modules": {"scylla/metrics": {"minimum": 90.0}},
            }
        }
        result = get_module_threshold("scylla/metrics", config)
        assert result == 90.0

    def test_returns_prefix_match_threshold(self) -> None:
        """Returns threshold for longest prefix match."""
        config = {
            "coverage": {
                "minimum": 70.0,
                "modules": {"scylla": {"minimum": 80.0}},
            }
        }
        result = get_module_threshold("scylla/analysis", config)
        assert result == 80.0

    def test_missing_modules_key_returns_minimum(self) -> None:
        """Config without 'modules' key returns overall minimum."""
        config = {"coverage": {"minimum": 65.0}}
        result = get_module_threshold("any/path", config)
        assert result == 65.0

    def test_empty_config_returns_default(self) -> None:
        """Empty config returns fallback default of 80.0."""
        result = get_module_threshold("any/path", {})
        assert result == 80.0


# ---------------------------------------------------------------------------
# parse_coverage_report
# ---------------------------------------------------------------------------


class TestParseCoverageReport:
    """Tests for parse_coverage_report()."""

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        """Returns None when coverage.xml does not exist."""
        result = parse_coverage_report(tmp_path / "nonexistent.xml")
        assert result is None

    def test_parses_line_rate_from_xml(self, tmp_path: Path) -> None:
        """Parses line-rate attribute and returns percentage."""
        xml_content = '<?xml version="1.0" ?>\n<coverage line-rate="0.85"></coverage>\n'
        coverage_file = tmp_path / "coverage.xml"
        coverage_file.write_text(xml_content)
        result = parse_coverage_report(coverage_file)
        assert result == pytest.approx(85.0, abs=0.01)

    def test_returns_none_for_invalid_xml(self, tmp_path: Path) -> None:
        """Returns None for malformed XML."""
        coverage_file = tmp_path / "bad.xml"
        coverage_file.write_text("not xml at all")
        result = parse_coverage_report(coverage_file)
        assert result is None

    def test_returns_none_when_no_line_rate(self, tmp_path: Path) -> None:
        """Returns None when line-rate attribute is absent."""
        coverage_file = tmp_path / "coverage.xml"
        coverage_file.write_text('<?xml version="1.0" ?>\n<coverage></coverage>\n')
        result = parse_coverage_report(coverage_file)
        assert result is None


# ---------------------------------------------------------------------------
# check_coverage
# ---------------------------------------------------------------------------


class TestCheckCoverage:
    """Tests for check_coverage()."""

    def test_returns_true_when_meets_threshold(self, tmp_path: Path) -> None:
        """Returns True when coverage meets or exceeds threshold."""
        xml_content = '<?xml version="1.0" ?>\n<coverage line-rate="0.90"></coverage>\n'
        coverage_file = tmp_path / "coverage.xml"
        coverage_file.write_text(xml_content)
        result = check_coverage(80.0, "scylla/", coverage_file)
        assert result is True

    def test_returns_false_when_below_threshold(self, tmp_path: Path) -> None:
        """Returns False when coverage is below threshold."""
        xml_content = '<?xml version="1.0" ?>\n<coverage line-rate="0.70"></coverage>\n'
        coverage_file = tmp_path / "coverage.xml"
        coverage_file.write_text(xml_content)
        result = check_coverage(80.0, "scylla/", coverage_file)
        assert result is False

    def test_returns_true_when_coverage_unavailable(self, tmp_path: Path) -> None:
        """Returns True gracefully when coverage data is not available."""
        # File doesn't exist so parse_coverage_report returns None
        missing = tmp_path / "nonexistent.xml"
        result = check_coverage(80.0, "scylla/", missing)
        assert result is True
