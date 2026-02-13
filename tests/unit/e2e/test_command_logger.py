"""Unit tests for command logger."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

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

        d = log.model_dump()

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

        log = CommandLog.model_validate(data)

        assert log.command == ["git", "status"]
        assert log.exit_code == 0


class TestCommandLogger:
    """Tests for CommandLogger."""

    def test_log_command(self) -> None:
        """Test logging a command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = CommandLogger(log_dir=Path(tmpdir))

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
            logger = CommandLogger(log_dir=Path(tmpdir))

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
            logger = CommandLogger(log_dir=Path(tmpdir))

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
            logger1 = CommandLogger(log_dir=Path(tmpdir))
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
                logger = CommandLogger(log_dir=Path(tmpdir))
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

    def test_replay_script_file_path_detection(self) -> None:
        """Test that file paths in command args are detected and not extracted.

        Regression test for Bug 1: save_replay_script() should detect when
        the last argument is already a file path and not try to extract it
        to replay_prompt.md, avoiding overwriting existing files.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = CommandLogger(log_dir=Path(tmpdir))

            # Create a prompt file that should NOT be overwritten
            prompt_file = Path(tmpdir) / "prompt.md"
            original_content = "This is the actual task prompt content."
            prompt_file.write_text(original_content)

            # Log a claude command with the file path as the last argument
            # (simulating what subtest_executor.py does)
            logger.log_command(
                cmd=["claude", "--model", "sonnet", str(prompt_file.resolve())],
                stdout="Agent output",
                stderr="",
                exit_code=0,
                duration=1.5,
                cwd=tmpdir,
            )

            # Generate replay script
            script_path = logger.save_replay_script()

            # Bug 1 check: Original prompt.md should NOT be overwritten
            assert prompt_file.exists()
            assert prompt_file.read_text() == original_content

            # replay_prompt.md should NOT be created (arg was already a file path)
            replay_prompt = Path(tmpdir) / "replay_prompt.md"
            assert not replay_prompt.exists()

            # Replay script should reference the original file path
            script_content = script_path.read_text()
            assert str(prompt_file.resolve()) in script_content

    def test_replay_script_inline_prompt_extraction(self) -> None:
        """Test that inline prompts are correctly extracted to replay_prompt.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = CommandLogger(log_dir=Path(tmpdir))

            # Log a claude command with an inline prompt (>100 chars)
            inline_prompt = "This is a long inline prompt. " * 10
            logger.log_command(
                cmd=["claude", "--model", "sonnet", inline_prompt],
                stdout="Agent output",
                stderr="",
                exit_code=0,
                duration=1.5,
                cwd=tmpdir,
            )

            # Generate replay script
            script_path = logger.save_replay_script()

            # replay_prompt.md should be created with the inline prompt
            replay_prompt = Path(tmpdir) / "replay_prompt.md"
            assert replay_prompt.exists()
            assert replay_prompt.read_text() == inline_prompt

            # Replay script should reference replay_prompt.md
            script_content = script_path.read_text()
            assert "replay_prompt.md" in script_content
