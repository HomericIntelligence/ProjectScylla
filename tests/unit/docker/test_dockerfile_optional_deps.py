"""Regression tests for Docker Layer 2 optional-dependency caching.

Verifies that the Dockerfile properly supports optional-dependency groups
via the EXTRAS build argument so they land in the cached Layer 2 rather
than bypassing it.  No Docker daemon required — these are static-analysis
assertions on the Dockerfile text.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

DOCKERFILE = Path(__file__).parents[3] / "docker" / "Dockerfile"


@pytest.fixture(scope="module")
def dockerfile_text() -> str:
    """Return the full Dockerfile content as a single string."""
    return DOCKERFILE.read_text()


@pytest.fixture(scope="module")
def dockerfile_lines() -> list[str]:
    """Return the Dockerfile content as a list of lines."""
    return DOCKERFILE.read_text().splitlines()


# ---------------------------------------------------------------------------
# ARG EXTRAS declaration
# ---------------------------------------------------------------------------


def test_arg_extras_declared(dockerfile_text: str) -> None:
    """ARG EXTRAS must be declared in the Dockerfile."""
    assert "ARG EXTRAS" in dockerfile_text, (
        "docker/Dockerfile must declare 'ARG EXTRAS' so the optional-dependency "
        "group build argument is available during the builder stage."
    )


def test_arg_extras_declared_before_layer3(dockerfile_lines: list[str]) -> None:
    """ARG EXTRAS must appear before Layer 3 (the source-code COPY/install)."""
    arg_line = next((i for i, line in enumerate(dockerfile_lines) if "ARG EXTRAS" in line), None)
    layer3_line = next(
        (
            i
            for i, line in enumerate(dockerfile_lines)
            if "Layer 3" in line or "pip install --user --no-cache-dir --no-deps" in line
        ),
        None,
    )
    assert arg_line is not None, "ARG EXTRAS not found in Dockerfile"
    assert layer3_line is not None, "Layer 3 marker not found in Dockerfile"
    assert arg_line < layer3_line, (
        f"ARG EXTRAS (line {arg_line + 1}) must appear before Layer 3 "
        f"(line {layer3_line + 1}) so it is in scope for the Layer 2 RUN command."
    )


# ---------------------------------------------------------------------------
# Layer 2 RUN command references optional-dependencies
# ---------------------------------------------------------------------------


def test_layer2_references_optional_dependencies(dockerfile_text: str) -> None:
    """Layer 2 pip install must reference 'optional-dependencies' for extras extraction."""
    assert "optional-dependencies" in dockerfile_text, (
        "docker/Dockerfile Layer 2 RUN command must reference 'optional-dependencies' "
        "so that [project.optional-dependencies] groups are extracted from pyproject.toml."
    )


def test_layer2_passes_extras_to_python(dockerfile_text: str) -> None:
    """The EXTRAS variable must be passed into the python3 -c invocation."""
    # The pattern EXTRAS="$EXTRAS" or EXTRAS=$EXTRAS in the RUN command
    assert re.search(r'EXTRAS=["\']?\$EXTRAS["\']?', dockerfile_text), (
        "docker/Dockerfile Layer 2 must pass EXTRAS=$EXTRAS into the python3 -c "
        "command so optional groups are conditionally included."
    )


def test_layer2_uses_os_environ_for_extras(dockerfile_text: str) -> None:
    """The python snippet must use os.environ (or os.getenv) to read EXTRAS."""
    assert re.search(r"os\.environ|os\.getenv", dockerfile_text), (
        "The python3 -c snippet in Layer 2 must read EXTRAS via os.environ/os.getenv "
        "so the build argument is properly consumed."
    )


# ---------------------------------------------------------------------------
# Default build is unchanged (empty EXTRAS produces runtime deps only)
# ---------------------------------------------------------------------------


def test_default_extras_is_empty_string(dockerfile_text: str) -> None:
    """ARG EXTRAS default must be empty string to preserve the current default build."""
    assert 'ARG EXTRAS=""' in dockerfile_text or "ARG EXTRAS=''" in dockerfile_text, (
        "ARG EXTRAS must default to empty string ('ARG EXTRAS=\"\"') so that "
        "a build without --build-arg EXTRAS=... is identical to the original image."
    )


# ---------------------------------------------------------------------------
# docker-compose.yml wires EXTRAS through
# ---------------------------------------------------------------------------


COMPOSE_FILE = Path(__file__).parents[3] / "docker" / "docker-compose.yml"


@pytest.fixture(scope="module")
def compose_text() -> str:
    """Return the docker-compose.yml content."""
    return COMPOSE_FILE.read_text()


def test_compose_passes_extras_build_arg(compose_text: str) -> None:
    """docker-compose.yml build section must pass EXTRAS as a build arg."""
    assert "EXTRAS" in compose_text, (
        "docker/docker-compose.yml must reference EXTRAS in the build args so that "
        "'EXTRAS=analysis docker-compose build' works without manual --build-arg."
    )
