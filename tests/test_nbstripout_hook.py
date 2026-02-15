"""Tests for nbstripout pre-commit hook configuration.

This module validates that the nbstripout hook is properly configured and
working to strip outputs from Jupyter notebooks before commits.
"""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest


def create_notebook_with_outputs() -> dict[str, Any]:
    """Create a sample Jupyter notebook with outputs.

    Returns:
        dict: A Jupyter notebook structure with code cells containing outputs.

    """
    return {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["# Test Notebook"],
            },
            {
                "cell_type": "code",
                "execution_count": 1,
                "metadata": {},
                "outputs": [
                    {
                        "name": "stdout",
                        "output_type": "stream",
                        "text": ["Hello, world!\n"],
                    }
                ],
                "source": ['print("Hello, world!")'],
            },
            {
                "cell_type": "code",
                "execution_count": 2,
                "metadata": {},
                "outputs": [
                    {
                        "data": {"text/plain": ["42"]},
                        "execution_count": 2,
                        "metadata": {},
                        "output_type": "execute_result",
                    }
                ],
                "source": ["6 * 7"],
            },
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.10.0",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 4,
    }


def test_nbstripout_hook_exists() -> None:
    """Test that nbstripout hook is configured in .pre-commit-config.yaml."""
    config_path = Path(__file__).parent.parent / ".pre-commit-config.yaml"
    assert config_path.exists(), ".pre-commit-config.yaml not found"

    with open(config_path) as f:
        content = f.read()

    assert "nbstripout" in content, "nbstripout not found in pre-commit config"
    assert "https://github.com/kynan/nbstripout" in content, "nbstripout repo URL not found"
    # Ensure the hook is not commented out
    assert not content.count("# - repo: https://github.com/kynan/nbstripout"), (
        "nbstripout hook appears to be commented out"
    )


def test_nbstripout_strips_outputs() -> None:
    """Test that nbstripout removes outputs from notebook cells."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        notebook_path = tmppath / "test.ipynb"

        # Create notebook with outputs
        notebook = create_notebook_with_outputs()
        with open(notebook_path, "w") as f:
            json.dump(notebook, f)

        # Run nbstripout via pre-commit
        subprocess.run(
            [
                "pixi",
                "run",
                "pre-commit",
                "run",
                "nbstripout",
                "--files",
                str(notebook_path),
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
            check=False,
        )

        # Load stripped notebook
        with open(notebook_path) as f:
            stripped = json.load(f)

        # Verify outputs are stripped
        for cell in stripped["cells"]:
            if cell["cell_type"] == "code":
                assert cell["outputs"] == [], f"Cell outputs not stripped: {cell}"
                # Execution count should be None
                assert cell.get("execution_count") is None, f"Execution count not cleared: {cell}"


def test_nbstripout_strips_kernelspec() -> None:
    """Test that nbstripout removes kernelspec metadata."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        notebook_path = tmppath / "test.ipynb"

        # Create notebook with kernelspec
        notebook = create_notebook_with_outputs()
        with open(notebook_path, "w") as f:
            json.dump(notebook, f)

        # Run nbstripout via pre-commit
        subprocess.run(
            [
                "pixi",
                "run",
                "pre-commit",
                "run",
                "nbstripout",
                "--files",
                str(notebook_path),
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
            check=False,
        )

        # Load stripped notebook
        with open(notebook_path) as f:
            stripped = json.load(f)

        # Verify kernelspec is stripped (as configured with --extra-keys)
        assert "kernelspec" not in stripped["metadata"], "kernelspec metadata not stripped"


def test_nbstripout_preserves_language_info() -> None:
    """Test that nbstripout preserves language_info metadata.

    Only kernelspec should be removed based on our configuration.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        notebook_path = tmppath / "test.ipynb"

        # Create notebook with metadata
        notebook = create_notebook_with_outputs()
        with open(notebook_path, "w") as f:
            json.dump(notebook, f)

        # Run nbstripout via pre-commit
        subprocess.run(
            [
                "pixi",
                "run",
                "pre-commit",
                "run",
                "nbstripout",
                "--files",
                str(notebook_path),
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        # Load stripped notebook
        with open(notebook_path) as f:
            stripped = json.load(f)

        # Verify language_info is preserved
        assert "language_info" in stripped["metadata"], "language_info should be preserved"


def test_nbstripout_handles_empty_notebook() -> None:
    """Test that nbstripout handles notebooks without outputs gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        notebook_path = tmppath / "empty.ipynb"

        # Create minimal empty notebook
        notebook = {
            "cells": [],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 4,
        }
        with open(notebook_path, "w") as f:
            json.dump(notebook, f)

        # Run nbstripout via pre-commit
        result = subprocess.run(
            [
                "pixi",
                "run",
                "pre-commit",
                "run",
                "nbstripout",
                "--files",
                str(notebook_path),
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
            check=False,
        )

        # Should complete successfully
        assert result.returncode == 0, f"nbstripout failed: {result.stderr}"

        # Notebook should still be valid JSON
        with open(notebook_path) as f:
            stripped = json.load(f)

        assert stripped["cells"] == [], "Empty notebook cells should remain empty"


@pytest.mark.parametrize(
    "cell_type,has_outputs",
    [
        ("code", True),
        ("markdown", False),
    ],
)
def test_nbstripout_cell_types(cell_type: str, has_outputs: bool) -> None:
    """Test that nbstripout correctly handles different cell types.

    Args:
        cell_type: Type of notebook cell ('code' or 'markdown').
        has_outputs: Whether the cell type should have outputs.

    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        notebook_path = tmppath / "test.ipynb"

        # Create notebook with specific cell type
        cell: dict[str, Any] = {
            "cell_type": cell_type,
            "metadata": {},
            "source": ["test content"],
        }

        if cell_type == "code":
            cell["execution_count"] = 1
            cell["outputs"] = [{"name": "stdout", "output_type": "stream", "text": ["output\n"]}]

        notebook = {
            "cells": [cell],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 4,
        }

        with open(notebook_path, "w") as f:
            json.dump(notebook, f)

        # Run nbstripout
        subprocess.run(
            [
                "pixi",
                "run",
                "pre-commit",
                "run",
                "nbstripout",
                "--files",
                str(notebook_path),
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        # Load stripped notebook
        with open(notebook_path) as f:
            stripped = json.load(f)

        # Verify outputs handling based on cell type
        if has_outputs:
            assert "outputs" in stripped["cells"][0], "Code cell should have outputs key"
            assert stripped["cells"][0]["outputs"] == [], "Code cell outputs should be empty"
        else:
            assert "outputs" not in stripped["cells"][0], (
                "Markdown cell should not have outputs key"
            )
