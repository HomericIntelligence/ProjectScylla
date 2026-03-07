"""Tests for scripts/validate_config_schemas.py."""

import json
import textwrap
from pathlib import Path

import pytest

from scripts.validate_config_schemas import check_files, main, resolve_schema, validate_file

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent.parent


def _write_yaml(directory: Path, filename: str, content: str) -> Path:
    """Write a YAML file into *directory* and return its path."""
    path = directory / filename
    path.write_text(textwrap.dedent(content))
    return path


def _write_schema(directory: Path, filename: str, schema: dict[str, object]) -> Path:
    """Write a JSON schema file into *directory* and return its path."""
    path = directory / filename
    path.write_text(json.dumps(schema))
    return path


# Minimal valid schema for test use
_SIMPLE_SCHEMA: dict[str, object] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["name"],
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string"},
        "count": {"type": "integer"},
    },
}

# ---------------------------------------------------------------------------
# TestResolveSchema
# ---------------------------------------------------------------------------


class TestResolveSchema:
    """Tests for resolve_schema()."""

    def test_defaults_yaml_matches(self) -> None:
        """config/defaults.yaml should match defaults.schema.json."""
        path = _REPO_ROOT / "config" / "defaults.yaml"
        result = resolve_schema(path, _REPO_ROOT)
        assert result is not None
        assert result.name == "defaults.schema.json"

    def test_model_yaml_matches(self) -> None:
        """config/models/*.yaml should match model.schema.json."""
        path = _REPO_ROOT / "config" / "models" / "some-model.yaml"
        result = resolve_schema(path, _REPO_ROOT)
        assert result is not None
        assert result.name == "model.schema.json"

    def test_tier_fixture_yaml_matches(self) -> None:
        """tests/fixtures/config/tiers/*.yaml should match tier.schema.json."""
        path = _REPO_ROOT / "tests" / "fixtures" / "config" / "tiers" / "t0.yaml"
        result = resolve_schema(path, _REPO_ROOT)
        assert result is not None
        assert result.name == "tier.schema.json"

    def test_unknown_path_returns_none(self) -> None:
        """A path not matching any pattern should return None."""
        path = _REPO_ROOT / "config" / "unknown.yaml"
        assert resolve_schema(path, _REPO_ROOT) is None

    def test_non_yaml_model_file_returns_none(self) -> None:
        """A non-yaml file in config/models/ should not match."""
        path = _REPO_ROOT / "config" / "models" / "README.md"
        assert resolve_schema(path, _REPO_ROOT) is None

    def test_production_tier_yaml_matches(self) -> None:
        """config/tiers/*.yaml should match tier.schema.json."""
        path = _REPO_ROOT / "config" / "tiers" / "t0.yaml"
        result = resolve_schema(path, _REPO_ROOT)
        assert result is not None
        assert result.name == "tier.schema.json"

    @pytest.mark.parametrize(
        "rel_path",
        [
            "config/defaults.yaml",
            "config/models/claude-sonnet.yaml",
            "config/tiers/t0.yaml",
            "tests/fixtures/config/tiers/t1.yaml",
        ],
    )
    def test_all_supported_patterns_match(self, rel_path: str) -> None:
        """All documented path patterns should resolve to a schema."""
        path = _REPO_ROOT / rel_path
        assert resolve_schema(path, _REPO_ROOT) is not None


# ---------------------------------------------------------------------------
# TestValidateFile
# ---------------------------------------------------------------------------


class TestValidateFile:
    """Tests for validate_file()."""

    def test_valid_yaml_returns_no_errors(self, tmp_path: Path) -> None:
        """A YAML file conforming to the schema should produce no errors."""
        cfg = _write_yaml(tmp_path, "good.yaml", 'name: "hello"\n')
        errors = validate_file(cfg, _SIMPLE_SCHEMA)
        assert errors == []

    def test_missing_required_field_returns_error(self, tmp_path: Path) -> None:
        """Missing required field should be reported."""
        cfg = _write_yaml(tmp_path, "bad.yaml", "count: 5\n")
        errors = validate_file(cfg, _SIMPLE_SCHEMA)
        assert len(errors) >= 1
        assert any("name" in e for e in errors)

    def test_wrong_field_type_returns_error(self, tmp_path: Path) -> None:
        """Field with wrong type should produce an error containing the path."""
        cfg = _write_yaml(tmp_path, "bad_type.yaml", 'name: "ok"\ncount: "not-an-int"\n')
        errors = validate_file(cfg, _SIMPLE_SCHEMA)
        assert len(errors) >= 1
        assert any("count" in e for e in errors)

    def test_additional_property_returns_error(self, tmp_path: Path) -> None:
        """Extra field rejected by additionalProperties: false should be reported."""
        cfg = _write_yaml(tmp_path, "extra.yaml", 'name: "ok"\nextra_field: true\n')
        errors = validate_file(cfg, _SIMPLE_SCHEMA)
        assert len(errors) >= 1
        assert any("extra_field" in e for e in errors)

    def test_malformed_yaml_returns_error(self, tmp_path: Path) -> None:
        """Malformed YAML should return an error string without raising."""
        cfg = tmp_path / "bad.yaml"
        cfg.write_text("key: [unclosed\n")
        errors = validate_file(cfg, _SIMPLE_SCHEMA)
        assert len(errors) == 1
        assert "parse" in errors[0].lower() or "read" in errors[0].lower()

    def test_missing_file_returns_error(self, tmp_path: Path) -> None:
        """Non-existent file should return an error string."""
        cfg = tmp_path / "nonexistent.yaml"
        errors = validate_file(cfg, _SIMPLE_SCHEMA)
        assert len(errors) == 1

    def test_multiple_errors_all_returned(self, tmp_path: Path) -> None:
        """Multiple schema violations should all appear in the result."""
        cfg = _write_yaml(
            tmp_path,
            "multi.yaml",
            "count: 'bad'\nextra: true\n",  # missing 'name', wrong type, extra field
        )
        errors = validate_file(cfg, _SIMPLE_SCHEMA)
        assert len(errors) >= 2


# ---------------------------------------------------------------------------
# TestCheckFiles
# ---------------------------------------------------------------------------


class TestCheckFiles:
    """Tests for check_files()."""

    def _make_schema_root(self, tmp_path: Path) -> Path:
        """Create a fake repo root with schemas/ directory."""
        schemas_dir = tmp_path / "schemas"
        schemas_dir.mkdir()
        _write_schema(schemas_dir, "defaults.schema.json", _SIMPLE_SCHEMA)
        _write_schema(schemas_dir, "model.schema.json", _SIMPLE_SCHEMA)
        _write_schema(schemas_dir, "tier.schema.json", _SIMPLE_SCHEMA)
        return tmp_path

    def test_empty_file_list_returns_zero(self, tmp_path: Path) -> None:
        """No files should return exit code 0."""
        repo_root = self._make_schema_root(tmp_path)
        assert check_files([], repo_root) == 0

    def test_valid_file_returns_zero(self, tmp_path: Path) -> None:
        """A valid config file should return exit code 0."""
        repo_root = self._make_schema_root(tmp_path)
        cfg_dir = tmp_path / "config" / "models"
        cfg_dir.mkdir(parents=True)
        cfg = _write_yaml(cfg_dir, "model.yaml", 'name: "test-model"\n')
        assert check_files([cfg], repo_root) == 0

    def test_invalid_file_returns_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An invalid config should return exit code 1."""
        repo_root = self._make_schema_root(tmp_path)
        cfg_dir = tmp_path / "config" / "models"
        cfg_dir.mkdir(parents=True)
        cfg = _write_yaml(cfg_dir, "bad.yaml", "extra_field: true\n")
        assert check_files([cfg], repo_root) == 1
        captured = capsys.readouterr()
        assert "FAIL" in captured.err

    def test_all_errors_reported_not_just_first(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Both invalid files should appear in stderr, not just the first."""
        repo_root = self._make_schema_root(tmp_path)
        cfg_dir = tmp_path / "config" / "models"
        cfg_dir.mkdir(parents=True)
        bad_a = _write_yaml(cfg_dir, "bad_a.yaml", "extra_a: 1\n")
        bad_b = _write_yaml(cfg_dir, "bad_b.yaml", "extra_b: 2\n")
        result = check_files([bad_a, bad_b], repo_root)
        assert result == 1
        captured = capsys.readouterr()
        assert "bad_a.yaml" in captured.err
        assert "bad_b.yaml" in captured.err

    def test_unknown_schema_path_warns_and_skips(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A file with no matching schema should warn but not fail."""
        repo_root = self._make_schema_root(tmp_path)
        unknown = tmp_path / "some" / "other" / "file.yaml"
        unknown.parent.mkdir(parents=True)
        unknown.write_text('name: "ok"\n')
        result = check_files([unknown], repo_root)
        assert result == 0
        captured = capsys.readouterr()
        assert "WARNING" in captured.err

    def test_verbose_prints_pass_lines(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """With verbose=True, valid files should print PASS: lines to stdout."""
        repo_root = self._make_schema_root(tmp_path)
        cfg_dir = tmp_path / "config" / "models"
        cfg_dir.mkdir(parents=True)
        cfg = _write_yaml(cfg_dir, "good.yaml", 'name: "valid"\n')
        result = check_files([cfg], repo_root, verbose=True)
        assert result == 0
        captured = capsys.readouterr()
        assert "PASS" in captured.out
        assert "good.yaml" in captured.out

    def test_verbose_false_no_pass_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Without verbose, valid files should not produce stdout output."""
        repo_root = self._make_schema_root(tmp_path)
        cfg_dir = tmp_path / "config" / "models"
        cfg_dir.mkdir(parents=True)
        cfg = _write_yaml(cfg_dir, "good.yaml", 'name: "valid"\n')
        check_files([cfg], repo_root, verbose=False)
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_one_valid_one_invalid_returns_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Mix of valid and invalid should return exit code 1."""
        repo_root = self._make_schema_root(tmp_path)
        cfg_dir = tmp_path / "config" / "models"
        cfg_dir.mkdir(parents=True)
        good = _write_yaml(cfg_dir, "good.yaml", 'name: "ok"\n')
        bad = _write_yaml(cfg_dir, "bad.yaml", "extra: true\n")
        assert check_files([good, bad], repo_root) == 1


# ---------------------------------------------------------------------------
# TestDryRun
# ---------------------------------------------------------------------------


class TestDryRun:
    """Tests for --dry-run behaviour in check_files() and main()."""

    def _make_schema_root(self, tmp_path: Path) -> Path:
        """Create a fake repo root with schemas/ directory."""
        schemas_dir = tmp_path / "schemas"
        schemas_dir.mkdir()
        (schemas_dir / "defaults.schema.json").write_text(json.dumps(_SIMPLE_SCHEMA))
        (schemas_dir / "model.schema.json").write_text(json.dumps(_SIMPLE_SCHEMA))
        (schemas_dir / "tier.schema.json").write_text(json.dumps(_SIMPLE_SCHEMA))
        return tmp_path

    def test_dry_run_with_violations_returns_zero(self, tmp_path: Path) -> None:
        """dry_run=True should return 0 even when there are violations."""
        repo_root = self._make_schema_root(tmp_path)
        cfg_dir = tmp_path / "config" / "models"
        cfg_dir.mkdir(parents=True)
        bad = _write_yaml(cfg_dir, "bad.yaml", "extra_field: true\n")
        assert check_files([bad], repo_root, dry_run=True) == 0

    def test_dry_run_false_with_violations_returns_one(self, tmp_path: Path) -> None:
        """dry_run=False should return 1 when there are violations."""
        repo_root = self._make_schema_root(tmp_path)
        cfg_dir = tmp_path / "config" / "models"
        cfg_dir.mkdir(parents=True)
        bad = _write_yaml(cfg_dir, "bad.yaml", "extra_field: true\n")
        assert check_files([bad], repo_root, dry_run=False) == 1

    def test_dry_run_prints_errors(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """dry_run=True should still print errors to stderr."""
        repo_root = self._make_schema_root(tmp_path)
        cfg_dir = tmp_path / "config" / "models"
        cfg_dir.mkdir(parents=True)
        bad = _write_yaml(cfg_dir, "bad.yaml", "extra_field: true\n")
        check_files([bad], repo_root, dry_run=True)
        captured = capsys.readouterr()
        assert "FAIL" in captured.err

    def test_dry_run_no_violations_returns_zero(self, tmp_path: Path) -> None:
        """dry_run=True with a valid file should still return 0."""
        repo_root = self._make_schema_root(tmp_path)
        cfg_dir = tmp_path / "config" / "models"
        cfg_dir.mkdir(parents=True)
        good = _write_yaml(cfg_dir, "good.yaml", 'name: "ok"\n')
        assert check_files([good], repo_root, dry_run=True) == 0

    def test_dry_run_multiple_bad_files_all_reported(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """dry_run=True should report all invalid files, not just the first."""
        repo_root = self._make_schema_root(tmp_path)
        cfg_dir = tmp_path / "config" / "models"
        cfg_dir.mkdir(parents=True)
        bad_a = _write_yaml(cfg_dir, "bad_a.yaml", "extra_a: 1\n")
        bad_b = _write_yaml(cfg_dir, "bad_b.yaml", "extra_b: 2\n")
        result = check_files([bad_a, bad_b], repo_root, dry_run=True)
        assert result == 0
        captured = capsys.readouterr()
        assert "bad_a.yaml" in captured.err
        assert "bad_b.yaml" in captured.err

    def test_main_dry_run_flag_with_violations_exits_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """main() with --dry-run should exit 0 even when violations are found."""
        repo_root = self._make_schema_root(tmp_path)
        cfg_dir = tmp_path / "config" / "models"
        cfg_dir.mkdir(parents=True)
        bad = _write_yaml(cfg_dir, "bad.yaml", "extra_field: true\n")
        monkeypatch.setattr(
            "sys.argv",
            ["validate_config_schemas.py", "--dry-run", "--repo-root", str(repo_root), str(bad)],
        )
        assert main() == 0

    def test_main_no_dry_run_with_violations_exits_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """main() without --dry-run should exit 1 when violations are found."""
        repo_root = self._make_schema_root(tmp_path)
        cfg_dir = tmp_path / "config" / "models"
        cfg_dir.mkdir(parents=True)
        bad = _write_yaml(cfg_dir, "bad.yaml", "extra_field: true\n")
        monkeypatch.setattr(
            "sys.argv",
            ["validate_config_schemas.py", "--repo-root", str(repo_root), str(bad)],
        )
        assert main() == 1


# ---------------------------------------------------------------------------
# TestMainIntegration — real schema files
# ---------------------------------------------------------------------------


class TestMainIntegration:
    """Integration tests using actual schema and config files from the repo."""

    def test_defaults_yaml_validates(self) -> None:
        """The real config/defaults.yaml should pass schema validation."""
        defaults = _REPO_ROOT / "config" / "defaults.yaml"
        if not defaults.exists():
            pytest.skip("config/defaults.yaml not present")
        schema_path = _REPO_ROOT / "schemas" / "defaults.schema.json"
        schema = json.loads(schema_path.read_text())
        errors = validate_file(defaults, schema)
        assert errors == [], f"defaults.yaml failed: {errors}"

    def test_model_configs_validate(self) -> None:
        """All real config/models/*.yaml files should pass schema validation."""
        models_dir = _REPO_ROOT / "config" / "models"
        if not models_dir.exists():
            pytest.skip("config/models/ directory not present")
        schema_path = _REPO_ROOT / "schemas" / "model.schema.json"
        schema = json.loads(schema_path.read_text())
        model_files = [f for f in models_dir.glob("*.yaml") if not f.name.startswith("_")]
        if not model_files:
            pytest.skip("No model config files found")
        failures: list[str] = []
        for model_file in model_files:
            errors = validate_file(model_file, schema)
            if errors:
                failures.append(f"{model_file}: {errors}")
        assert not failures, "\n".join(failures)

    def test_tier_fixture_configs_validate(self) -> None:
        """All tier fixture YAML files should pass schema validation."""
        tiers_dir = _REPO_ROOT / "tests" / "fixtures" / "config" / "tiers"
        if not tiers_dir.exists():
            pytest.skip("tests/fixtures/config/tiers/ directory not present")
        schema_path = _REPO_ROOT / "schemas" / "tier.schema.json"
        schema = json.loads(schema_path.read_text())
        tier_files = list(tiers_dir.glob("*.yaml"))
        if not tier_files:
            pytest.skip("No tier fixture files found")
        failures: list[str] = []
        for tier_file in tier_files:
            errors = validate_file(tier_file, schema)
            if errors:
                failures.append(f"{tier_file}: {errors}")
        assert not failures, "\n".join(failures)

    def test_production_tier_configs_validate(self) -> None:
        """All production config/tiers/*.yaml files should pass schema validation."""
        tiers_dir = _REPO_ROOT / "config" / "tiers"
        if not tiers_dir.exists():
            pytest.skip("config/tiers/ directory not present")
        schema_path = _REPO_ROOT / "schemas" / "tier.schema.json"
        schema = json.loads(schema_path.read_text())
        tier_files = list(tiers_dir.glob("*.yaml"))
        if not tier_files:
            pytest.skip("No production tier config files found")
        failures: list[str] = []
        for tier_file in tier_files:
            errors = validate_file(tier_file, schema)
            if errors:
                failures.append(f"{tier_file}: {errors}")
        assert not failures, "\n".join(failures)
