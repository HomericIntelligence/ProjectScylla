"""Unit tests for command logger."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from scylla.e2e.command_logger import CommandLog, CommandLogger


class TestCommandLog:
    """Tests for CommandLog."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        log = CommandLog(
            timestamp="2026-01-01T12:00:00Z",
            command=["claude", "--print", "hello"],
            cwd="/workspace",
            env_vars={"PATH": "/usr/bin"},
            exit_code=0,
            stdout_file="cmd_0000_stdout.log",
            stderr_file="cmd_0000_stderr.log",
            duration_seconds=1.5,
        )

        d = log.to_dict()

        assert d["command"] == ["claude", "--print", "hello"]
        assert d["exit_code"] == 0
        assert d["duration_seconds"] == 1.5

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {
            "timestamp": "2026-01-01T12:00:00Z",
            "command": ["git", "status"],
            "cwd": "/repo",
            "env_vars": {},
            "exit_code": 0,
            "stdout_file": "stdout.log",
            "stderr_file": "stderr.log",
            "duration_seconds": 0.5,
        }

        log = CommandLog.from_dict(data)

        assert log.command == ["git", "status"]
        assert log.exit_code == 0


class TestCommandLogger:
    """Tests for CommandLogger."""

    def test_log_command(self) -> None:
        """Test logging a command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = CommandLogger(Path(tmpdir))

            log = logger.log_command(
                cmd=["echo", "hello"],
                stdout="hello\n",
                stderr="",
                exit_code=0,
                duration=0.1,
            )

            assert log.command == ["echo", "hello"]
            assert log.exit_code == 0
            assert len(logger.commands) == 1

            # Check stdout file was written
            stdout_file = Path(tmpdir) / log.stdout_file
            assert stdout_file.exists()
            assert stdout_file.read_text() == "hello\n"

    def test_save(self) -> None:
        """Test saving command log to JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = CommandLogger(Path(tmpdir))

            logger.log_command(
                cmd=["cmd1"],
                stdout="out1",
                stderr="",
                exit_code=0,
                duration=1.0,
            )
            logger.log_command(
                cmd=["cmd2"],
                stdout="out2",
                stderr="err2",
                exit_code=1,
                duration=2.0,
            )

            log_path = logger.save()

            assert log_path.exists()

            with open(log_path) as f:
                data = json.load(f)

            assert data["total_commands"] == 2
            assert len(data["commands"]) == 2

    def test_save_replay_script(self) -> None:
        """Test generating replay script."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = CommandLogger(Path(tmpdir))

            logger.log_command(
                cmd=["echo", "hello world"],
                stdout="hello world\n",
                stderr="",
                exit_code=0,
                duration=0.1,
                cwd="/test/dir",
            )

            script_path = logger.save_replay_script()

            assert script_path.exists()
            assert script_path.stat().st_mode & 0o100  # Executable

            content = script_path.read_text()
            assert "#!/bin/bash" in content
            assert "cd /test/dir" in content  # Path without spaces doesn't need quotes
            assert "echo 'hello world'" in content

    def test_load(self) -> None:
        """Test loading saved command log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and save logger
            logger1 = CommandLogger(Path(tmpdir))
            logger1.log_command(
                cmd=["test", "cmd"],
                stdout="output",
                stderr="",
                exit_code=0,
                duration=1.0,
            )
            logger1.save()

            # Load into new logger
            logger2 = CommandLogger.load(Path(tmpdir))

            assert len(logger2.commands) == 1
            assert logger2.commands[0].command == ["test", "cmd"]

    def test_env_var_redaction(self) -> None:
        """Test that sensitive env vars are redacted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import os

            # Temporarily set an API key
            original = os.environ.get("ANTHROPIC_API_KEY")
            os.environ["ANTHROPIC_API_KEY"] = "secret-key-12345"

            try:
                logger = CommandLogger(Path(tmpdir))
                log = logger.log_command(
                    cmd=["test"],
                    stdout="",
                    stderr="",
                    exit_code=0,
                    duration=0.1,
                )

                # API key should be redacted
                assert log.env_vars.get("ANTHROPIC_API_KEY") == "[REDACTED]"

            finally:
                if original:
                    os.environ["ANTHROPIC_API_KEY"] = original
                else:
                    os.environ.pop("ANTHROPIC_API_KEY", None)
