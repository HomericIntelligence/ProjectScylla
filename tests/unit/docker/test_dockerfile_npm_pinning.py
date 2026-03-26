"""Regression tests for Dockerfile npm package version pinning.

Verifies that all ``npm install -g`` commands in the Dockerfile use exact
version pinning (``@x.y.z``) and that a post-install audit fix step is
present to resolve transitive CVEs.  See issue #1542 for context.

No Docker daemon required — these are static-analysis assertions on the
Dockerfile text.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

DOCKERFILE = Path(__file__).parents[3] / "docker" / "Dockerfile"


def _get_dockerfile_text() -> str:
    """Return the full Dockerfile content as a single string."""
    return DOCKERFILE.read_text()


class TestNpmVersionPinning:
    """All npm install commands must use exact version pinning."""

    def test_all_npm_install_global_packages_are_pinned(self) -> None:
        """Every ``npm install -g <pkg>`` must specify an exact version with ``@x.y.z``.

        Unpinned installs pull the latest version at build time, which breaks
        reproducibility and can introduce regressions.
        """
        text = _get_dockerfile_text()
        # Match npm install -g lines (may be multi-line with backslash continuation)
        # We look for package references like @scope/pkg or pkg after -g
        pattern = re.compile(r"npm\s+install\s+(?:-g|--global)\s+([@\w/.-]+)", re.MULTILINE)
        matches = pattern.findall(text)

        assert matches, "No 'npm install -g' commands found in docker/Dockerfile"

        for pkg in matches:
            assert "@" in pkg and re.search(r"@\d+\.\d+\.\d+", pkg), (
                f"npm package '{pkg}' in docker/Dockerfile is not pinned to an "
                f"exact version. Use '{pkg}@x.y.z' for reproducible builds. "
                f"See issue #1542."
            )

    @pytest.mark.parametrize(
        "pkg_name",
        ["@anthropic-ai/claude-code"],
    )
    def test_known_packages_are_present(self, pkg_name: str) -> None:
        """Required npm packages must appear in the Dockerfile."""
        text = _get_dockerfile_text()
        assert pkg_name in text, f"Expected '{pkg_name}' to be installed in docker/Dockerfile"


class TestNpmAuditFix:
    """Post-install audit fix must be present for transitive CVE remediation."""

    def test_npm_audit_fix_present(self) -> None:
        """An ``npm audit fix`` step must follow the global npm install.

        This catches transitive dependency CVEs that the pinned package version
        may still carry.  See issue #1542.
        """
        text = _get_dockerfile_text()
        assert "npm audit fix" in text, (
            "docker/Dockerfile must include an 'npm audit fix' step after "
            "npm install to resolve transitive dependency CVEs. See issue #1542."
        )
