"""Tests for scripts/validate_model_configs.py."""

from pathlib import Path
from unittest import mock

import pytest
import yaml
from validate_model_configs import (
    _collect_mismatches,
    _confirm_rename,
    _fix_mismatch,
    _load_model_id,
    main,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_yaml(path: Path, model_id: str) -> None:
    """Write a minimal model YAML file."""
    path.write_text(yaml.dump({"model_id": model_id, "name": "Test Model"}))


# ---------------------------------------------------------------------------
# _load_model_id
# ---------------------------------------------------------------------------


class TestLoadModelId:
    """Tests for _load_model_id helper."""

    def test_returns_model_id(self, tmp_path: Path) -> None:
        """Returns the model_id string from a valid YAML file."""
        f = tmp_path / "mymodel.yaml"
        _write_yaml(f, "my-model-id")
        assert _load_model_id(f) == "my-model-id"

    def test_returns_none_for_missing_field(self, tmp_path: Path) -> None:
        """Returns None when model_id field is absent."""
        f = tmp_path / "nofield.yaml"
        f.write_text(yaml.dump({"name": "No model_id here"}))
        assert _load_model_id(f) is None

    def test_returns_none_for_invalid_yaml(self, tmp_path: Path) -> None:
        """Returns None when the file contains invalid YAML."""
        f = tmp_path / "bad.yaml"
        f.write_text("{{{{ not yaml")
        assert _load_model_id(f) is None

    def test_returns_none_for_non_dict_yaml(self, tmp_path: Path) -> None:
        """Returns None when YAML is valid but not a mapping."""
        f = tmp_path / "list.yaml"
        f.write_text(yaml.dump(["a", "b"]))
        assert _load_model_id(f) is None


# ---------------------------------------------------------------------------
# _collect_mismatches
# ---------------------------------------------------------------------------


class TestCollectMismatches:
    """Tests for _collect_mismatches helper."""

    def test_no_mismatches_when_filenames_match(self, tmp_path: Path) -> None:
        """Returns empty list when all filenames match their model_id."""
        _write_yaml(tmp_path / "my-model.yaml", "my-model")
        assert _collect_mismatches(tmp_path) == []

    def test_detects_mismatch(self, tmp_path: Path) -> None:
        """Returns one tuple when filename stem differs from model_id."""
        _write_yaml(tmp_path / "wrong-name.yaml", "correct-model-id")
        result = _collect_mismatches(tmp_path)
        assert len(result) == 1
        current, model_id, expected = result[0]
        assert current.name == "wrong-name.yaml"
        assert model_id == "correct-model-id"
        assert expected.name == "correct-model-id.yaml"

    def test_skips_underscore_prefixed_files(self, tmp_path: Path) -> None:
        """Skips fixture files prefixed with underscore."""
        _write_yaml(tmp_path / "_fixture.yaml", "some-other-id")
        assert _collect_mismatches(tmp_path) == []

    def test_skips_files_without_model_id(self, tmp_path: Path) -> None:
        """Skips YAML files that have no model_id field."""
        f = tmp_path / "no-model-id.yaml"
        f.write_text(yaml.dump({"name": "Nothing here"}))
        assert _collect_mismatches(tmp_path) == []

    def test_multiple_mismatches(self, tmp_path: Path) -> None:
        """Returns one entry per mismatched file."""
        _write_yaml(tmp_path / "wrong-a.yaml", "correct-a")
        _write_yaml(tmp_path / "wrong-b.yaml", "correct-b")
        result = _collect_mismatches(tmp_path)
        assert len(result) == 2

    def test_colon_in_model_id_normalized(self, tmp_path: Path) -> None:
        """No mismatch when colon-containing model_id normalizes to match filename."""
        # model_id with ':' should normalize to '-'; filename already normalized → no mismatch
        _write_yaml(tmp_path / "model-namespace-id.yaml", "model:namespace:id")
        assert _collect_mismatches(tmp_path) == []


# ---------------------------------------------------------------------------
# _confirm_rename
# ---------------------------------------------------------------------------


class TestConfirmRename:
    """Tests for _confirm_rename interactive prompt."""

    def test_returns_true_on_y(self, tmp_path: Path) -> None:
        """Returns True when user enters 'y'."""
        current = tmp_path / "old.yaml"
        target = tmp_path / "new.yaml"
        with mock.patch("builtins.input", return_value="y"):
            assert _confirm_rename(current, target) is True

    def test_returns_false_on_n(self, tmp_path: Path) -> None:
        """Returns False when user enters 'n'."""
        current = tmp_path / "old.yaml"
        target = tmp_path / "new.yaml"
        with mock.patch("builtins.input", return_value="n"):
            assert _confirm_rename(current, target) is False

    def test_returns_false_on_empty_input(self, tmp_path: Path) -> None:
        """Returns False when user presses Enter without typing (default N)."""
        current = tmp_path / "old.yaml"
        target = tmp_path / "new.yaml"
        with mock.patch("builtins.input", return_value=""):
            assert _confirm_rename(current, target) is False

    def test_returns_false_on_uppercase_n(self, tmp_path: Path) -> None:
        """Returns False when user enters uppercase 'N'."""
        current = tmp_path / "old.yaml"
        target = tmp_path / "new.yaml"
        with mock.patch("builtins.input", return_value="N"):
            assert _confirm_rename(current, target) is False


# ---------------------------------------------------------------------------
# _fix_mismatch
# ---------------------------------------------------------------------------


class TestFixMismatch:
    """Tests for _fix_mismatch rename executor."""

    def test_renames_file_when_yes(self, tmp_path: Path) -> None:
        """Renames file without prompting when yes=True."""
        current = tmp_path / "old.yaml"
        _write_yaml(current, "new-id")
        target = tmp_path / "new-id.yaml"
        assert _fix_mismatch(current, target, yes=True) is True
        assert not current.exists()
        assert target.exists()

    def test_renames_on_user_confirmation(self, tmp_path: Path) -> None:
        """Renames file when user confirms interactively."""
        current = tmp_path / "old.yaml"
        _write_yaml(current, "new-id")
        target = tmp_path / "new-id.yaml"
        with mock.patch("builtins.input", return_value="y"):
            assert _fix_mismatch(current, target, yes=False) is True
        assert not current.exists()
        assert target.exists()

    def test_skips_on_user_denial(self, tmp_path: Path) -> None:
        """Returns True (no error) but leaves file untouched when user denies."""
        current = tmp_path / "old.yaml"
        _write_yaml(current, "new-id")
        target = tmp_path / "new-id.yaml"
        with mock.patch("builtins.input", return_value="n"):
            result = _fix_mismatch(current, target, yes=False)
        assert result is True  # Skipped is not an error
        assert current.exists()  # Not renamed
        assert not target.exists()

    def test_returns_false_on_collision(self, tmp_path: Path) -> None:
        """Returns False when target path already exists (collision)."""
        current = tmp_path / "old.yaml"
        _write_yaml(current, "new-id")
        target = tmp_path / "new-id.yaml"
        _write_yaml(target, "new-id")  # Target already exists
        assert _fix_mismatch(current, target, yes=True) is False
        assert current.exists()  # Not renamed
        assert target.exists()


# ---------------------------------------------------------------------------
# main() integration tests
# ---------------------------------------------------------------------------


class TestMain:
    """Integration tests for the main() CLI entry point."""

    def _make_models_dir(self, tmp_path: Path) -> Path:
        """Create and return a temporary models directory."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        return models_dir

    def test_exits_0_when_no_mismatches(self, tmp_path: Path) -> None:
        """Exits 0 when all YAML filenames match their model_id."""
        models_dir = self._make_models_dir(tmp_path)
        _write_yaml(models_dir / "good-model.yaml", "good-model")
        with mock.patch("sys.argv", ["validate_model_configs.py", "--models-dir", str(models_dir)]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 0

    def test_exits_1_on_mismatch_without_fix(self, tmp_path: Path) -> None:
        """Exits 1 when mismatches found and --fix not passed."""
        models_dir = self._make_models_dir(tmp_path)
        _write_yaml(models_dir / "wrong.yaml", "correct-id")
        with mock.patch("sys.argv", ["validate_model_configs.py", "--models-dir", str(models_dir)]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1

    def test_fix_yes_renames_and_exits_0(self, tmp_path: Path) -> None:
        """Renames mismatched file and exits 0 when --fix --yes passed."""
        models_dir = self._make_models_dir(tmp_path)
        _write_yaml(models_dir / "wrong.yaml", "correct-id")
        with (
            mock.patch(
                "sys.argv",
                ["validate_model_configs.py", "--fix", "--yes", "--models-dir", str(models_dir)],
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()
        assert exc_info.value.code == 0
        assert not (models_dir / "wrong.yaml").exists()
        assert (models_dir / "correct-id.yaml").exists()

    def test_fix_collision_exits_2(self, tmp_path: Path) -> None:
        """Exits 2 when --fix encounters a target collision."""
        models_dir = self._make_models_dir(tmp_path)
        _write_yaml(models_dir / "wrong.yaml", "correct-id")
        _write_yaml(models_dir / "correct-id.yaml", "correct-id")  # Collision
        with (
            mock.patch(
                "sys.argv",
                ["validate_model_configs.py", "--fix", "--yes", "--models-dir", str(models_dir)],
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()
        assert exc_info.value.code == 2

    def test_missing_models_dir_exits_2(self, tmp_path: Path) -> None:
        """Exits 2 when the models directory does not exist."""
        nonexistent = tmp_path / "nonexistent"
        with (
            mock.patch(
                "sys.argv",
                ["validate_model_configs.py", "--models-dir", str(nonexistent)],
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()
        assert exc_info.value.code == 2

    def test_underscore_files_skipped_exits_0(self, tmp_path: Path) -> None:
        """Exits 0 when only underscore-prefixed files are present (skipped)."""
        models_dir = self._make_models_dir(tmp_path)
        _write_yaml(models_dir / "_fixture.yaml", "some-other-id")
        with mock.patch("sys.argv", ["validate_model_configs.py", "--models-dir", str(models_dir)]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 0

    def test_verbose_flag_runs_without_error(self, tmp_path: Path) -> None:
        """Exits 0 with --verbose when configs are valid."""
        models_dir = self._make_models_dir(tmp_path)
        _write_yaml(models_dir / "good-model.yaml", "good-model")
        with (
            mock.patch(
                "sys.argv",
                ["validate_model_configs.py", "--verbose", "--models-dir", str(models_dir)],
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()
        assert exc_info.value.code == 0

    def test_fix_interactive_confirm_renames(self, tmp_path: Path) -> None:
        """Renames file and exits 0 when --fix used with interactive confirmation."""
        models_dir = self._make_models_dir(tmp_path)
        _write_yaml(models_dir / "wrong.yaml", "correct-id")
        with (
            mock.patch(
                "sys.argv",
                ["validate_model_configs.py", "--fix", "--models-dir", str(models_dir)],
            ),
            mock.patch("builtins.input", return_value="y"),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()
        assert exc_info.value.code == 0
        assert (models_dir / "correct-id.yaml").exists()
