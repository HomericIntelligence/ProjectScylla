"""Tests for scylla.__version__ including PackageNotFoundError fallback."""

import importlib
from importlib.metadata import PackageNotFoundError
from unittest.mock import patch


def test_version_is_nonempty_string() -> None:
    """__version__ is a non-empty string when the package is installed."""
    import scylla

    assert isinstance(scylla.__version__, str), "__version__ must be a string"
    assert scylla.__version__, "__version__ must be non-empty"


def test_version_fallback_on_package_not_found() -> None:
    """__version__ falls back to '0.0.0' when PackageNotFoundError is raised."""
    with patch(
        "importlib.metadata.version",
        side_effect=PackageNotFoundError("scylla"),
    ):
        import scylla as _scylla_mod

        importlib.reload(_scylla_mod)
        assert _scylla_mod.__version__ == "0.0.0", (
            f"Expected fallback '0.0.0', got {_scylla_mod.__version__!r}"
        )
