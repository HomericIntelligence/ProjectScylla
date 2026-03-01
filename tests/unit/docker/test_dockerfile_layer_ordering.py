"""Unit tests asserting correct layer ordering in docker/Dockerfile.

Verifies semantic ordering of Dockerfile instructions so that the build cache
is used efficiently and security/correctness invariants are maintained.  No
Docker daemon is required — these are static-analysis assertions on the
Dockerfile text.

Key ordering invariants tested:

Builder stage (Stage 1):
  1. Build-tool apt install before any pip install
  2. Hatchling (Layer 1) installed before dependencies (Layer 2)
  3. pyproject.toml copied before Layer 2 pip install (cache-key discipline)
  4. Layer 2 pip install before source COPY (Layer 3)
  5. Layer 3 source installed (no-deps) before runtime stage FROM

Runtime stage (Stage 2):
  6. COPY --from=builder before runtime apt install
  7. Runtime apt install before Node.js install
  8. Node.js install before Claude Code CLI npm install
  9. Non-root user created (groupadd/useradd) before USER directive
 10. COPY entrypoint.sh before USER scylla (chown on copy, not after)
 11. USER scylla before HEALTHCHECK and ENTRYPOINT
"""

from __future__ import annotations

from pathlib import Path

import pytest

DOCKERFILE = Path(__file__).parents[3] / "docker" / "Dockerfile"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def lines() -> list[str]:
    """Return Dockerfile content as a list of non-empty, non-comment lines."""
    return DOCKERFILE.read_text().splitlines()


def _first_line_containing(lines: list[str], *fragments: str) -> int | None:
    """Return the 0-based index of the first line that contains ALL fragments."""
    for i, line in enumerate(lines):
        if all(frag in line for frag in fragments):
            return i
    return None


def _all_lines_containing(lines: list[str], *fragments: str) -> list[int]:
    """Return 0-based indices of every line that contains ALL fragments."""
    return [i for i, line in enumerate(lines) if all(frag in line for frag in fragments)]


def _assert_before(
    earlier_idx: int | None,
    later_idx: int | None,
    earlier_desc: str,
    later_desc: str,
) -> None:
    """Assert that *earlier_idx* precedes *later_idx*, with helpful messages."""
    assert earlier_idx is not None, f"Could not find '{earlier_desc}' in docker/Dockerfile"
    assert later_idx is not None, f"Could not find '{later_desc}' in docker/Dockerfile"
    assert earlier_idx < later_idx, (
        f"Expected '{earlier_desc}' (line {earlier_idx + 1}) "
        f"to appear before '{later_desc}' (line {later_idx + 1}) "
        f"in docker/Dockerfile"
    )


# ---------------------------------------------------------------------------
# Stage identification helpers
# ---------------------------------------------------------------------------


def _from_line_indices(lines: list[str]) -> list[int]:
    """Return 0-based indices of all FROM lines."""
    return [i for i, line in enumerate(lines) if line.strip().startswith("FROM")]


# ---------------------------------------------------------------------------
# Multi-stage structure
# ---------------------------------------------------------------------------


class TestMultiStageStructure:
    """The Dockerfile must have exactly two stages: builder then runtime."""

    def test_two_from_lines_exist(self, lines: list[str]) -> None:
        """There must be exactly two FROM instructions (builder + runtime)."""
        from_indices = _from_line_indices(lines)
        assert len(from_indices) == 2, (
            f"Expected exactly 2 FROM lines in docker/Dockerfile, found {len(from_indices)}: "
            + str([lines[i] for i in from_indices])
        )

    def test_builder_stage_comes_first(self, lines: list[str]) -> None:
        """The 'AS builder' stage must be declared before the runtime stage."""
        builder_idx = _first_line_containing(lines, "AS builder")
        from_indices = _from_line_indices(lines)
        # Runtime FROM is the second FROM (no 'AS ...' alias, or at least not 'AS builder')
        assert builder_idx is not None, "No 'AS builder' stage found in docker/Dockerfile"
        assert len(from_indices) >= 2, "Expected at least 2 FROM lines"
        runtime_from_idx = from_indices[1]
        assert builder_idx < runtime_from_idx, (
            f"Builder stage (line {builder_idx + 1}) must appear before "
            f"runtime stage FROM (line {runtime_from_idx + 1})"
        )

    def test_runtime_stage_does_not_use_builder_alias(self, lines: list[str]) -> None:
        """The runtime (second) FROM must not carry an 'AS builder' alias."""
        from_indices = _from_line_indices(lines)
        assert len(from_indices) >= 2, "Expected at least 2 FROM lines"
        runtime_from_line = lines[from_indices[1]]
        assert "AS builder" not in runtime_from_line, (
            "The second FROM line must not use 'AS builder' — it is the runtime stage"
        )


# ---------------------------------------------------------------------------
# Builder stage ordering
# ---------------------------------------------------------------------------


class TestBuilderStageOrdering:
    """Layer ordering within Stage 1 (builder)."""

    def test_apt_build_deps_before_pip_install(self, lines: list[str]) -> None:
        """apt-get install of build tools must precede all pip install commands.

        Build tools (gcc, g++, build-essential) are needed to compile C
        extensions.  They must be installed before pip runs.

        Note: the RUN apt-get instruction is multi-line; we match on the
        Layer 1 comment which immediately follows the apt install block and
        precedes the first pip install.
        """
        # "Layer 1" comment appears right after the build-tools apt-get block
        # and before any pip install — a reliable single-line anchor.
        apt_idx = _first_line_containing(lines, "Layer 1: Build backend")
        pip_idx = _first_line_containing(lines, "pip install")
        _assert_before(
            apt_idx,
            pip_idx,
            "Layer 1: Build backend comment (follows apt-get install gcc block)",
            "pip install",
        )

    def test_hatchling_installed_before_dependencies(self, lines: list[str]) -> None:
        """Layer 1 (hatchling) must be installed before Layer 2 (project deps).

        hatchling is the build backend; it must be present before pip tries
        to install the project's own dependencies which use it.
        """
        hatchling_idx = _first_line_containing(lines, "hatchling")
        # Layer 2 is the dynamic install from pyproject.toml (contains tomllib/os.environ)
        layer2_idx = _first_line_containing(lines, "optional-dependencies")
        _assert_before(
            hatchling_idx,
            layer2_idx,
            "hatchling install (Layer 1)",
            "Layer 2 dependency install",
        )

    def test_pyproject_toml_copied_before_layer2_install(self, lines: list[str]) -> None:
        """pyproject.toml must be COPY'd before the Layer 2 pip install.

        This is the cache-key discipline: copying only pyproject.toml first
        means Docker can reuse the Layer 2 cache as long as pyproject.toml
        has not changed, even if source files changed.

        We anchor Layer 2 on the ``pip install --user`` line (which contains
        ``os.environ.get('EXTRAS'``) rather than on "optional-dependencies",
        which also appears in comments earlier in the file.
        """
        copy_toml_idx = _first_line_containing(lines, "COPY", "pyproject.toml")
        # The Layer 2 dynamic install snippet references os.environ.get on one
        # of its continuation lines — unique to the actual RUN command.
        layer2_idx = _first_line_containing(lines, "os.environ.get")
        _assert_before(
            copy_toml_idx,
            layer2_idx,
            "COPY pyproject.toml",
            "Layer 2 dependency install (os.environ.get line)",
        )

    def test_layer2_deps_installed_before_source_copy(self, lines: list[str]) -> None:
        """Layer 2 (deps) must come before Layer 3 (source COPY).

        Source changes must not invalidate the dependency install cache layer.
        """
        layer2_idx = _first_line_containing(lines, "optional-dependencies")
        source_copy_idx = _first_line_containing(lines, "COPY", "scylla/", "/opt/scylla/scylla/")
        _assert_before(
            layer2_idx,
            source_copy_idx,
            "Layer 2 dependency install",
            "COPY scylla/ source (Layer 3)",
        )

    def test_source_copy_before_nodeps_install(self, lines: list[str]) -> None:
        """Source must be COPY'd before the --no-deps package install.

        Layer 3 installs the scylla package itself (without pulling deps again).
        The source must be present on disk first.
        """
        source_copy_idx = _first_line_containing(lines, "COPY", "scylla/", "/opt/scylla/scylla/")
        nodeps_idx = _first_line_containing(lines, "--no-deps", "/opt/scylla/")
        _assert_before(
            source_copy_idx,
            nodeps_idx,
            "COPY scylla/ source (Layer 3)",
            "pip install --no-deps (Layer 3 package install)",
        )

    def test_layer3_install_before_runtime_from(self, lines: list[str]) -> None:
        """The Layer 3 source install must complete before the runtime FROM.

        All builder work must finish inside the builder stage.
        """
        nodeps_idx = _first_line_containing(lines, "--no-deps", "/opt/scylla/")
        from_indices = _from_line_indices(lines)
        assert len(from_indices) >= 2, "Expected at least 2 FROM lines"
        runtime_from_idx = from_indices[1]
        _assert_before(
            nodeps_idx,
            runtime_from_idx,
            "pip install --no-deps (Layer 3)",
            "runtime stage FROM",
        )


# ---------------------------------------------------------------------------
# Runtime stage ordering
# ---------------------------------------------------------------------------


class TestRuntimeStageOrdering:
    """Layer ordering within Stage 2 (runtime)."""

    def _runtime_from_idx(self, lines: list[str]) -> int:
        from_indices = _from_line_indices(lines)
        assert len(from_indices) >= 2, "Expected at least 2 FROM lines"
        return from_indices[1]

    def test_copy_from_builder_before_runtime_apt(self, lines: list[str]) -> None:
        """COPY --from=builder must come before the runtime apt-get install.

        Python packages must be available before the runtime apt layer runs,
        keeping the layer ordering predictable and cache-friendly.
        """
        copy_builder_idx = _first_line_containing(lines, "COPY --from=builder")
        runtime_from = self._runtime_from_idx(lines)
        # Find first apt-get install *after* the runtime FROM
        runtime_apt_idx = next(
            (i for i, line in enumerate(lines) if i > runtime_from and "apt-get install" in line),
            None,
        )
        _assert_before(
            copy_builder_idx,
            runtime_apt_idx,
            "COPY --from=builder",
            "runtime apt-get install",
        )

    def test_runtime_apt_before_nodejs(self, lines: list[str]) -> None:
        """Runtime apt-get install must precede the Node.js setup script.

        The runtime apt layer installs git, curl, ca-certificates — curl is
        needed to download the NodeSource setup script.

        Note: the RUN apt-get instruction is multi-line; git appears on the
        continuation line after ``apt-get install``.  We look for the
        ``apt-get update`` line that starts the runtime apt block (after the
        runtime FROM) rather than the ``apt-get install`` line to avoid the
        multi-line split.
        """
        runtime_from = self._runtime_from_idx(lines)
        # Find the first "apt-get update" *after* the runtime FROM — this
        # uniquely identifies the runtime apt block since the builder stage's
        # apt block uses "apt-get update && apt-get install" on the same line.
        runtime_apt_idx = next(
            (i for i, line in enumerate(lines) if i > runtime_from and "apt-get update" in line),
            None,
        )
        nodejs_idx = _first_line_containing(lines, "nodesource")
        _assert_before(
            runtime_apt_idx,
            nodejs_idx,
            "runtime apt-get update (git/curl/ca-certificates block)",
            "Node.js setup (nodesource)",
        )

    def test_nodejs_before_claude_code_cli(self, lines: list[str]) -> None:
        """Node.js must be installed before the Claude Code CLI npm install.

        npm is provided by Node.js; the npm install will fail without it.
        """
        nodejs_idx = _first_line_containing(lines, "nodesource")
        claude_idx = _first_line_containing(lines, "npm install", "claude-code")
        _assert_before(
            nodejs_idx,
            claude_idx,
            "Node.js install (nodesource)",
            "npm install @anthropic-ai/claude-code",
        )

    def test_user_created_before_user_directive(self, lines: list[str]) -> None:
        """groupadd/useradd must precede the USER directive.

        The OS user must exist before Docker switches to it.
        """
        useradd_idx = _first_line_containing(lines, "useradd")
        user_directive_idx = _first_line_containing(lines, "USER scylla")
        _assert_before(
            useradd_idx,
            user_directive_idx,
            "useradd (create scylla user)",
            "USER scylla directive",
        )

    def test_entrypoint_copied_before_user_switch(self, lines: list[str]) -> None:
        """COPY entrypoint.sh must precede the USER scylla directive.

        The entrypoint is copied with --chown=scylla:scylla, so it must be
        copied while still running as root (before the USER directive).
        """
        copy_ep_idx = _first_line_containing(lines, "COPY", "entrypoint.sh")
        user_directive_idx = _first_line_containing(lines, "USER scylla")
        _assert_before(
            copy_ep_idx,
            user_directive_idx,
            "COPY entrypoint.sh",
            "USER scylla directive",
        )

    def test_user_directive_before_healthcheck(self, lines: list[str]) -> None:
        """USER scylla must come before HEALTHCHECK.

        The health-check command runs as the active user; it should execute
        as the non-root scylla user, not as root.
        """
        user_directive_idx = _first_line_containing(lines, "USER scylla")
        healthcheck_idx = _first_line_containing(lines, "HEALTHCHECK")
        _assert_before(
            user_directive_idx,
            healthcheck_idx,
            "USER scylla directive",
            "HEALTHCHECK",
        )

    def test_user_directive_before_entrypoint(self, lines: list[str]) -> None:
        """USER scylla must come before the ENTRYPOINT instruction.

        The entry point executes as the active user; switching to non-root
        before declaring ENTRYPOINT makes the intent explicit.
        """
        user_directive_idx = _first_line_containing(lines, "USER scylla")
        entrypoint_idx = _first_line_containing(lines, "ENTRYPOINT")
        _assert_before(
            user_directive_idx,
            entrypoint_idx,
            "USER scylla directive",
            "ENTRYPOINT",
        )
