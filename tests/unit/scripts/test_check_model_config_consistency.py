"""Tests for scripts/check_model_config_consistency.py."""

import textwrap
from pathlib import Path

import pytest

from scripts.check_model_config_consistency import check_configs, find_model_configs

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_yaml(directory: Path, filename: str, content: str) -> Path:
    """Write a YAML file into *directory* and return its path."""
    path = directory / filename
    path.write_text(textwrap.dedent(content))
    return path


VALID_CONTENT = """\
    model_id: "claude-sonnet-4-5-20250929"
    name: "Claude Sonnet 4.5"
    provider: "anthropic"
    adapter: "claude_code"
"""

# ---------------------------------------------------------------------------
# find_model_configs
# ---------------------------------------------------------------------------


class TestFindModelConfigs:
    """Tests for find_model_configs()."""

    def test_finds_yaml_files(self, tmp_path: Path) -> None:
        """Should discover YAML files in directory."""
        write_yaml(tmp_path, "model-a.yaml", VALID_CONTENT)
        write_yaml(tmp_path, "model-b.yaml", VALID_CONTENT)
        result = find_model_configs(tmp_path)
        names = [f.name for f in result]
        assert "model-a.yaml" in names
        assert "model-b.yaml" in names

    def test_excludes_underscore_prefixed_fixtures(self, tmp_path: Path) -> None:
        """Files prefixed with '_' should be excluded."""
        write_yaml(tmp_path, "_fixture.yaml", VALID_CONTENT)
        write_yaml(tmp_path, "real-model.yaml", VALID_CONTENT)
        result = find_model_configs(tmp_path)
        names = [f.name for f in result]
        assert "_fixture.yaml" not in names
        assert "real-model.yaml" in names

    def test_empty_directory_returns_empty_list(self, tmp_path: Path) -> None:
        """Empty directory should return empty list."""
        assert find_model_configs(tmp_path) == []

    def test_ignores_non_yaml_files(self, tmp_path: Path) -> None:
        """Non-YAML files should not be returned."""
        (tmp_path / "README.md").write_text("docs")
        write_yaml(tmp_path, "model.yaml", VALID_CONTENT)
        result = find_model_configs(tmp_path)
        assert len(result) == 1
        assert result[0].name == "model.yaml"

    def test_returns_sorted_list(self, tmp_path: Path) -> None:
        """Returned list should be sorted alphabetically."""
        write_yaml(tmp_path, "zzz-model.yaml", VALID_CONTENT)
        write_yaml(tmp_path, "aaa-model.yaml", VALID_CONTENT)
        result = find_model_configs(tmp_path)
        names = [f.name for f in result]
        assert names == sorted(names)


# ---------------------------------------------------------------------------
# check_configs — exit codes
# ---------------------------------------------------------------------------


class TestCheckConfigs:
    """Tests for check_configs()."""

    def test_clean_configs_exit_zero(self, tmp_path: Path) -> None:
        """Directory of matching configs should return exit code 0."""
        write_yaml(
            tmp_path,
            "claude-sonnet-4-5-20250929.yaml",
            'model_id: "claude-sonnet-4-5-20250929"\nname: "S"\nprovider: "a"\nadapter: "b"\n',
        )
        assert check_configs(tmp_path) == 0

    def test_mismatch_config_exits_one(self, tmp_path: Path) -> None:
        """A config whose filename stem does not match model_id should return 1."""
        write_yaml(
            tmp_path,
            "wrong-name.yaml",
            'model_id: "claude-opus-4-1"\nname: "O"\nprovider: "a"\nadapter: "b"\n',
        )
        assert check_configs(tmp_path) == 1

    def test_multiple_mismatches_all_reported(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """All mismatches should be reported, not just the first."""
        write_yaml(
            tmp_path,
            "bad-a.yaml",
            'model_id: "claude-opus-4-1"\nname: "A"\nprovider: "a"\nadapter: "b"\n',
        )
        write_yaml(
            tmp_path,
            "bad-b.yaml",
            'model_id: "claude-sonnet-4-5"\nname: "B"\nprovider: "a"\nadapter: "b"\n',
        )
        exit_code = check_configs(tmp_path)
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "bad-a.yaml" in captured.err
        assert "bad-b.yaml" in captured.err

    def test_underscore_prefixed_configs_skipped(self, tmp_path: Path) -> None:
        """Test fixtures (prefixed with '_') should be skipped silently."""
        # A fixture with a mismatching model_id should NOT cause failure
        write_yaml(
            tmp_path,
            "_test-model.yaml",
            'model_id: "something-completely-different"\nname: "T"\nprovider: "a"\nadapter: "b"\n',
        )
        assert check_configs(tmp_path) == 0

    def test_empty_directory_exit_zero(self, tmp_path: Path) -> None:
        """No YAML files in directory should not be an error."""
        assert check_configs(tmp_path) == 0

    def test_missing_directory_exits_one(self, tmp_path: Path) -> None:
        """Non-existent directory should return exit code 1."""
        nonexistent = tmp_path / "no-such-dir"
        assert check_configs(nonexistent) == 1

    def test_missing_model_id_field_exits_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A YAML without 'model_id' field should cause exit code 1."""
        write_yaml(
            tmp_path,
            "some-model.yaml",
            'name: "Nameless"\nprovider: "a"\nadapter: "b"\n',
        )
        exit_code = check_configs(tmp_path)
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "model_id" in captured.err

    def test_invalid_yaml_exits_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Malformed YAML should cause exit code 1 without crashing."""
        path = tmp_path / "bad.yaml"
        path.write_text("key: [unclosed bracket\n")
        exit_code = check_configs(tmp_path)
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "bad.yaml" in captured.err

    @pytest.mark.parametrize(
        "filename,model_id",
        [
            # Exact match
            ("claude-opus-4-1.yaml", "claude-opus-4-1"),
            # Colon-to-hyphen normalization (API versioned model IDs)
            ("claude-sonnet-3-7-20250219.yaml", "claude-sonnet-3-7-20250219"),
        ],
    )
    def test_valid_naming_patterns_pass(self, filename: str, model_id: str, tmp_path: Path) -> None:
        """Valid filename/model_id combinations should produce exit code 0."""
        write_yaml(
            tmp_path,
            filename,
            f'model_id: "{model_id}"\nname: "M"\nprovider: "a"\nadapter: "b"\n',
        )
        assert check_configs(tmp_path) == 0

    def test_verbose_prints_passing_files(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """With verbose=True, passing files should be printed to stdout."""
        write_yaml(
            tmp_path,
            "claude-opus-4-1.yaml",
            'model_id: "claude-opus-4-1"\nname: "O"\nprovider: "a"\nadapter: "b"\n',
        )
        exit_code = check_configs(tmp_path, verbose=True)
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "PASS" in captured.out
        assert "claude-opus-4-1.yaml" in captured.out
