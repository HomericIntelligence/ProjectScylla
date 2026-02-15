"""Tests for template loader module."""

from pathlib import Path

import pytest

from scylla.e2e.template_loader import (
    TEMPLATE_DIR,
    load_template,
    render_template,
    write_script,
)


def test_template_dir_exists() -> None:
    """Template directory exists."""
    assert TEMPLATE_DIR.exists()
    assert TEMPLATE_DIR.is_dir()


def test_load_template() -> None:
    """Load a template successfully."""
    template = load_template("python_check.sh.template")
    assert template is not None
    content = template.template
    assert "#!/usr/bin/env bash" in content
    assert "$workspace" in content


def test_load_nonexistent_template() -> None:
    """Loading nonexistent template raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_template("nonexistent.sh.template")


def test_render_template() -> None:
    """Render a template with substitution."""
    script = render_template(
        "python_check.sh.template",
        workspace="/path/to/workspace",
    )
    assert "#!/usr/bin/env bash" in script
    assert 'WORKSPACE="/path/to/workspace"' in script
    assert "$workspace" not in script  # Should be substituted


def test_write_script(tmp_path: Path) -> None:
    """Write script to file with executable permissions."""
    output_file = tmp_path / "test_script.sh"
    result = write_script(
        output_file,
        "python_check.sh.template",
        workspace="/workspace",
    )

    assert result == output_file
    assert output_file.exists()
    assert output_file.stat().st_mode & 0o111  # Executable bits set

    content = output_file.read_text()
    assert 'WORKSPACE="/workspace"' in content


def test_write_script_non_executable(tmp_path: Path) -> None:
    """Write script without executable permissions."""
    output_file = tmp_path / "test_script.sh"
    write_script(
        output_file,
        "python_check.sh.template",
        executable=False,
        workspace="/workspace",
    )

    assert output_file.exists()
    assert not (output_file.stat().st_mode & 0o111)


@pytest.mark.parametrize(
    "template_name",
    [
        "python_check.sh.template",
        "python_format.sh.template",
        "python_test.sh.template",
        "mojo_build.sh.template",
        "mojo_build_modular.sh.template",
        "mojo_format.sh.template",
        "mojo_format_modular.sh.template",
        "mojo_format_standalone_subdir.sh.template",
        "mojo_test.sh.template",
        "mojo_test_modular.sh.template",
        "precommit.sh.template",
        "run_all_python.sh.template",
        "run_all_mojo.sh.template",
    ],
)
def test_all_templates_exist(template_name: str) -> None:
    """All expected templates exist."""
    template_path = TEMPLATE_DIR / template_name
    assert template_path.exists(), f"Missing template: {template_name}"


@pytest.mark.parametrize(
    "template_name",
    [
        "python_check.sh.template",
        "python_format.sh.template",
        "python_test.sh.template",
        "mojo_build.sh.template",
        "mojo_build_modular.sh.template",
        "mojo_format.sh.template",
        "mojo_format_modular.sh.template",
        "mojo_format_standalone_subdir.sh.template",
        "mojo_test.sh.template",
        "mojo_test_modular.sh.template",
        "precommit.sh.template",
        "run_all_python.sh.template",
        "run_all_mojo.sh.template",
    ],
)
def test_template_has_shebang(template_name: str) -> None:
    """All templates have proper bash shebang."""
    template = load_template(template_name)
    content = template.template
    assert content.startswith("#!/usr/bin/env bash"), f"{template_name} missing shebang"
