"""Tests for judge container orchestration.

Python justification: Required for pytest testing framework.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from scylla.executor.docker import ContainerResult
from scylla.executor.judge_container import (
    JudgeContainerConfig,
    JudgeContainerManager,
    JudgeResult,
)


class TestJudgeContainerConfig:
    """Tests for JudgeContainerConfig dataclass."""

    def test_minimal_config(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        output = tmp_path / "output"

        config = JudgeContainerConfig(
            agent_workspace=workspace,
            output_dir=output,
        )

        assert config.agent_workspace == workspace
        assert config.output_dir == output
        assert config.judge_model == "claude-opus-4-5-20251101"
        assert config.timeout_seconds == 600
        assert config.image == "scylla-runner:latest"

    def test_full_config(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        output = tmp_path / "output"
        rubric = tmp_path / "rubric.yaml"
        rubric.write_text("test: rubric")

        config = JudgeContainerConfig(
            agent_workspace=workspace,
            output_dir=output,
            judge_model="custom-model",
            rubric_path=rubric,
            timeout_seconds=300,
            image="custom-image:v1",
        )

        assert config.judge_model == "custom-model"
        assert config.rubric_path == rubric
        assert config.timeout_seconds == 300


class TestJudgeResult:
    """Tests for JudgeResult dataclass."""

    def test_create_result(self) -> None:
        result = JudgeResult(
            container_id="abc123",
            exit_code=0,
            stdout="output",
            stderr="",
            tokens_input=1000,
            tokens_output=500,
            cost_usd=0.05,
        )

        assert result.container_id == "abc123"
        assert result.exit_code == 0
        assert result.tokens_input == 1000
        assert result.cost_usd == 0.05

    def test_default_values(self) -> None:
        result = JudgeResult(
            container_id="abc123",
            exit_code=0,
            stdout="",
            stderr="",
        )

        assert result.timed_out is False
        assert result.tokens_input == 0
        assert result.tokens_output == 0
        assert result.cost_usd == 0.0


class TestJudgeContainerManagerInit:
    """Tests for JudgeContainerManager initialization."""

    def test_init_with_executor(self) -> None:
        mock_executor = MagicMock()
        manager = JudgeContainerManager(executor=mock_executor)
        assert manager.executor == mock_executor

    @patch("scylla.executor.judge_container.DockerExecutor")
    def test_init_creates_executor(self, mock_executor_class: MagicMock) -> None:
        manager = JudgeContainerManager()
        mock_executor_class.assert_called_once()


class TestJudgeContainerManagerGenerateName:
    """Tests for container name generation."""

    def test_unique_names(self) -> None:
        mock_executor = MagicMock()
        manager = JudgeContainerManager(executor=mock_executor)

        name1 = manager._generate_container_name()
        name2 = manager._generate_container_name()

        assert name1.startswith("scylla-judge-")
        assert name2.startswith("scylla-judge-")
        assert name1 != name2


class TestJudgeContainerManagerBuildEnvironment:
    """Tests for environment variable building."""

    def test_basic_environment(self, tmp_path: Path) -> None:
        mock_executor = MagicMock()
        manager = JudgeContainerManager(executor=mock_executor)

        config = JudgeContainerConfig(
            agent_workspace=tmp_path,
            output_dir=tmp_path / "output",
        )

        env = manager._build_environment(config)

        assert env["ROLE"] == "judge"
        assert env["MODEL"] == "claude-opus-4-5-20251101"
        assert env["WORKSPACE_PATH"] == "/workspace"
        assert env["OUTPUT_PATH"] == "/output"

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    def test_includes_api_key(self, tmp_path: Path) -> None:
        mock_executor = MagicMock()
        manager = JudgeContainerManager(executor=mock_executor)

        config = JudgeContainerConfig(
            agent_workspace=tmp_path,
            output_dir=tmp_path / "output",
        )

        env = manager._build_environment(config)

        assert env["ANTHROPIC_API_KEY"] == "test-key"

    def test_includes_rubric_path(self, tmp_path: Path) -> None:
        mock_executor = MagicMock()
        manager = JudgeContainerManager(executor=mock_executor)

        rubric = tmp_path / "rubric.yaml"
        rubric.write_text("test")

        config = JudgeContainerConfig(
            agent_workspace=tmp_path,
            output_dir=tmp_path / "output",
            rubric_path=rubric,
        )

        env = manager._build_environment(config)

        assert "RUBRIC_PATH" in env
        assert "rubric.yaml" in env["RUBRIC_PATH"]


class TestJudgeContainerManagerBuildVolumes:
    """Tests for volume mount building."""

    def test_basic_volumes(self, tmp_path: Path) -> None:
        mock_executor = MagicMock()
        manager = JudgeContainerManager(executor=mock_executor)

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        output = tmp_path / "output"

        config = JudgeContainerConfig(
            agent_workspace=workspace,
            output_dir=output,
        )

        volumes = manager._build_volumes(config)

        # Workspace should be read-only
        workspace_key = str(workspace.resolve())
        assert workspace_key in volumes
        assert volumes[workspace_key]["mode"] == "ro"

        # Output should be read-write
        output_key = str(output.resolve())
        assert output_key in volumes
        assert volumes[output_key]["mode"] == "rw"


class TestJudgeContainerManagerCreateContainerConfig:
    """Tests for creating container configuration."""

    def test_creates_valid_config(self, tmp_path: Path) -> None:
        mock_executor = MagicMock()
        manager = JudgeContainerManager(executor=mock_executor)

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        output = tmp_path / "output"

        config = JudgeContainerConfig(
            agent_workspace=workspace,
            output_dir=output,
        )

        container_config = manager.create_container_config(config)

        assert container_config.image == "scylla-runner:latest"
        assert container_config.name.startswith("scylla-judge-")
        assert container_config.network == "none"
        assert output.exists()  # Output dir should be created


class TestJudgeContainerManagerRunJudge:
    """Tests for running judge container."""

    def test_run_success(self, tmp_path: Path) -> None:
        mock_executor = MagicMock()
        mock_executor.run.return_value = ContainerResult(
            container_id="judge-123",
            exit_code=0,
            stdout="TOKENS_INPUT: 1000\nTOKENS_OUTPUT: 500\nCOST_USD: 0.05\n",
            stderr="",
            timed_out=False,
        )

        manager = JudgeContainerManager(executor=mock_executor)

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        config = JudgeContainerConfig(
            agent_workspace=workspace,
            output_dir=tmp_path / "output",
        )

        result = manager.run_judge(config)

        assert result.exit_code == 0
        assert result.container_id == "judge-123"
        assert result.tokens_input == 1000
        assert result.tokens_output == 500
        assert result.cost_usd == 0.05

    def test_run_timeout(self, tmp_path: Path) -> None:
        mock_executor = MagicMock()
        mock_executor.run.return_value = ContainerResult(
            container_id="judge-123",
            exit_code=-1,
            stdout="",
            stderr="timeout",
            timed_out=True,
        )

        manager = JudgeContainerManager(executor=mock_executor)

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        config = JudgeContainerConfig(
            agent_workspace=workspace,
            output_dir=tmp_path / "output",
        )

        result = manager.run_judge(config)

        assert result.timed_out is True
        assert result.exit_code == -1


class TestJudgeContainerManagerParseTokenUsage:
    """Tests for token usage parsing."""

    def test_parse_all_fields(self) -> None:
        mock_executor = MagicMock()
        manager = JudgeContainerManager(executor=mock_executor)

        output = """
Some output
TOKENS_INPUT: 1500
TOKENS_OUTPUT: 750
COST_USD: 0.0825
More output
"""
        tokens_in, tokens_out, cost = manager._parse_token_usage(output)

        assert tokens_in == 1500
        assert tokens_out == 750
        assert cost == 0.0825

    def test_parse_missing_fields(self) -> None:
        mock_executor = MagicMock()
        manager = JudgeContainerManager(executor=mock_executor)

        output = "No token info here"
        tokens_in, tokens_out, cost = manager._parse_token_usage(output)

        assert tokens_in == 0
        assert tokens_out == 0
        assert cost == 0.0

    def test_parse_malformed_values(self) -> None:
        mock_executor = MagicMock()
        manager = JudgeContainerManager(executor=mock_executor)

        output = """
TOKENS_INPUT: not_a_number
TOKENS_OUTPUT: 500
COST_USD: invalid
"""
        tokens_in, tokens_out, cost = manager._parse_token_usage(output)

        assert tokens_in == 0
        assert tokens_out == 500
        assert cost == 0.0


class TestJudgeContainerManagerLifecycle:
    """Tests for container lifecycle management."""

    def test_stop_judge(self) -> None:
        mock_executor = MagicMock()
        manager = JudgeContainerManager(executor=mock_executor)
        manager._active_containers.append("judge-123")

        manager.stop_judge("judge-123")

        mock_executor.stop.assert_called_once_with("judge-123")
        assert "judge-123" not in manager._active_containers

    def test_cleanup_judge(self) -> None:
        mock_executor = MagicMock()
        manager = JudgeContainerManager(executor=mock_executor)
        manager._active_containers.append("judge-123")

        manager.cleanup_judge("judge-123")

        mock_executor.remove.assert_called_once_with("judge-123", force=False)
        assert "judge-123" not in manager._active_containers

    def test_cleanup_all(self) -> None:
        mock_executor = MagicMock()
        manager = JudgeContainerManager(executor=mock_executor)
        manager._active_containers = ["judge-1", "judge-2", "judge-3"]

        manager.cleanup_all()

        assert mock_executor.remove.call_count == 3

    def test_is_judge_running(self) -> None:
        mock_executor = MagicMock()
        mock_executor.is_running.return_value = True
        manager = JudgeContainerManager(executor=mock_executor)

        result = manager.is_judge_running("judge-123")

        assert result is True
        mock_executor.is_running.assert_called_once_with("judge-123")

    def test_get_judge_logs(self) -> None:
        mock_executor = MagicMock()
        mock_executor.logs.return_value = ("stdout", "stderr")
        manager = JudgeContainerManager(executor=mock_executor)

        stdout, stderr = manager.get_judge_logs("judge-123", tail=100)

        assert stdout == "stdout"
        assert stderr == "stderr"
        mock_executor.logs.assert_called_once_with("judge-123", tail=100)
