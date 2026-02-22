"""Unit tests for credential_mount context manager and utilities."""

from pathlib import Path
from unittest.mock import patch

import pytest

from scylla.executor.credential_mount import (
    _cleanup_temp_dir,
    cleanup_stale_credential_dirs,
    temporary_credential_mount,
)


@pytest.fixture()
def fake_home(tmp_path: Path) -> Path:
    """Return a tmp_path that acts as the fake home directory."""
    return tmp_path


@pytest.fixture()
def home_with_credentials(fake_home: Path) -> Path:
    """Create a fake home with ~/.claude/.credentials.json present."""
    claude_dir = fake_home / ".claude"
    claude_dir.mkdir()
    creds = claude_dir / ".credentials.json"
    creds.write_text('{"token": "fake-token"}')
    return fake_home


def test_temporary_credential_mount_creates_and_cleans_up(
    home_with_credentials: Path,
) -> None:
    """Temp dir exists inside the with block and is removed afterwards."""
    with patch("scylla.executor.credential_mount.Path.home", return_value=home_with_credentials):
        with temporary_credential_mount() as creds_dir:
            assert creds_dir is not None
            assert creds_dir.exists()
            assert creds_dir.name.startswith(".scylla-temp-creds-")
            # Credentials file should be present inside
            assert (creds_dir / ".credentials.json").exists()

        # After the context manager exits, dir should be removed
        assert not creds_dir.exists()


def test_temporary_credential_mount_no_credentials(fake_home: Path) -> None:
    """Yields None when no credentials file exists."""
    with patch("scylla.executor.credential_mount.Path.home", return_value=fake_home):
        with temporary_credential_mount() as creds_dir:
            assert creds_dir is None


def test_cleanup_retries_on_failure(tmp_path: Path) -> None:
    """Cleanup retries when shutil.rmtree raises OSError."""
    temp_dir = tmp_path / "fake-creds"
    temp_dir.mkdir()

    call_count = 0

    def rmtree_fail_twice(path: Path) -> None:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise OSError("busy")
        # 3rd attempt succeeds — do nothing (dir already gone simulation)

    with patch("scylla.executor.credential_mount.shutil.rmtree", side_effect=rmtree_fail_twice):
        with patch("scylla.executor.credential_mount.time.sleep"):
            _cleanup_temp_dir(temp_dir, retries=3, delay=0.0)

    assert call_count == 3


def test_cleanup_logs_warning_on_final_failure(tmp_path: Path) -> None:
    """Logs a warning when all retries are exhausted."""
    temp_dir = tmp_path / "fake-creds"
    temp_dir.mkdir()

    with patch(
        "scylla.executor.credential_mount.shutil.rmtree",
        side_effect=OSError("busy"),
    ):
        with patch("scylla.executor.credential_mount.time.sleep"):
            with patch("scylla.executor.credential_mount.logger") as mock_logger:
                _cleanup_temp_dir(temp_dir, retries=3, delay=0.0)

    mock_logger.warning.assert_called_once()
    warning_args = mock_logger.warning.call_args
    # The path should appear in the warning message arguments
    assert str(temp_dir) in str(warning_args)


def test_cleanup_stale_credential_dirs(fake_home: Path) -> None:
    """cleanup_stale_credential_dirs removes all .scylla-temp-creds-* dirs."""
    # Create several stale dirs and one unrelated dir
    stale1 = fake_home / ".scylla-temp-creds-aabbccdd"
    stale2 = fake_home / ".scylla-temp-creds-11223344"
    unrelated = fake_home / ".some-other-dir"
    for d in (stale1, stale2, unrelated):
        d.mkdir()

    with patch("scylla.executor.credential_mount.Path.home", return_value=fake_home):
        count = cleanup_stale_credential_dirs()

    assert count == 2
    assert not stale1.exists()
    assert not stale2.exists()
    assert unrelated.exists()  # Should not be touched


def test_context_manager_cleans_up_on_exception(home_with_credentials: Path) -> None:
    """Temp dir is removed even when an exception is raised inside the with block."""
    captured_dir: Path | None = None

    with patch("scylla.executor.credential_mount.Path.home", return_value=home_with_credentials):
        with pytest.raises(RuntimeError, match="test error"):
            with temporary_credential_mount() as creds_dir:
                captured_dir = creds_dir
                raise RuntimeError("test error")

    assert captured_dir is not None
    assert not captured_dir.exists()
