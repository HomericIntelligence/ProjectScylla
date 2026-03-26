"""Integration test verifying py.typed is included in the built wheel.

Builds the wheel from source and inspects the archive to confirm the
PEP 561 marker is present, matching the verification approach from issue #1584.
"""

from __future__ import annotations

import subprocess
import tempfile
import zipfile
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.integration
@pytest.mark.timeout(120)
def test_wheel_contains_py_typed() -> None:
    """A wheel built from the project must contain scylla/py.typed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.check_call(
            [
                "python",
                "-m",
                "build",
                "--wheel",
                "--outdir",
                tmpdir,
            ],
            cwd=str(_PROJECT_ROOT),
        )

        wheels = list(Path(tmpdir).glob("*.whl"))
        assert wheels, "No .whl file produced by build"

        whl = wheels[0]
        with zipfile.ZipFile(whl) as zf:
            names = zf.namelist()

        py_typed_entries = [n for n in names if n.endswith("py.typed")]
        assert py_typed_entries, f"py.typed not found in wheel {whl.name}. Contents:\n" + "\n".join(
            sorted(names)
        )
