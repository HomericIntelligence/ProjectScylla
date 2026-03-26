"""Unit tests for Maestro failure injection stages in scylla/e2e/stages.py.

Tests cover:
- stage_inject_failure: no-op when disabled, injection when enabled, graceful degradation
- stage_clear_failure: no-op when no injection, clear when injection exists, graceful degradation
- RunContext.maestro_injection_id field
- Resume: _restore_run_context loads maestro_injection.json
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scylla.e2e.models import (
    ExperimentConfig,
    RunState,
    SubTestConfig,
    TierConfig,
    TierID,
)
from scylla.e2e.stages import (
    RunContext,
    stage_clear_failure,
    stage_inject_failure,
)
from scylla.maestro.models import MaestroConfig


@pytest.fixture
def maestro_config() -> MaestroConfig:
    """MaestroConfig with enabled=True for testing."""
    return MaestroConfig(
        base_url="http://localhost:23000",
        enabled=True,
        timeout_seconds=5,
        health_check_timeout_seconds=2,
    )


@pytest.fixture
def minimal_config() -> ExperimentConfig:
    """ExperimentConfig without maestro (disabled by default)."""
    return ExperimentConfig(
        experiment_id="test-maestro",
        task_repo="https://github.com/test/repo",
        task_commit="abc123",
        task_prompt_file=Path("/tmp/prompt.md"),
        language="python",
        models=["claude-sonnet-4-6"],
        runs_per_subtest=1,
        judge_models=["claude-opus-4-6"],
        timeout_seconds=60,
    )


@pytest.fixture
def maestro_config_obj(
    minimal_config: ExperimentConfig, maestro_config: MaestroConfig
) -> ExperimentConfig:
    """ExperimentConfig with maestro enabled."""
    return minimal_config.model_copy(update={"maestro": maestro_config})


@pytest.fixture
def minimal_subtest() -> SubTestConfig:
    """Minimal SubTestConfig."""
    return SubTestConfig(
        id="00-empty",
        name="Empty",
        description="Empty subtest",
    )


@pytest.fixture
def run_context(
    tmp_path: Path,
    minimal_config: ExperimentConfig,
    minimal_subtest: SubTestConfig,
) -> RunContext:
    """RunContext with maestro disabled."""
    run_dir = tmp_path / "run_01"
    run_dir.mkdir()
    workspace = run_dir / "workspace"
    workspace.mkdir()

    return RunContext(
        config=minimal_config,
        tier_id=TierID.T0,
        tier_config=TierConfig(tier_id=TierID.T0, subtests=[minimal_subtest]),
        subtest=minimal_subtest,
        baseline=None,
        run_number=1,
        run_dir=run_dir,
        workspace=workspace,
        experiment_dir=tmp_path,
        tier_manager=MagicMock(),
        workspace_manager=MagicMock(),
        adapter=MagicMock(),
        task_prompt="Fix the bug",
    )


@pytest.fixture
def maestro_run_context(
    tmp_path: Path,
    maestro_config_obj: ExperimentConfig,
    minimal_subtest: SubTestConfig,
) -> RunContext:
    """RunContext with maestro enabled."""
    run_dir = tmp_path / "run_01"
    run_dir.mkdir(exist_ok=True)
    workspace = run_dir / "workspace"
    workspace.mkdir(exist_ok=True)

    return RunContext(
        config=maestro_config_obj,
        tier_id=TierID.T0,
        tier_config=TierConfig(tier_id=TierID.T0, subtests=[minimal_subtest]),
        subtest=minimal_subtest,
        baseline=None,
        run_number=1,
        run_dir=run_dir,
        workspace=workspace,
        experiment_dir=tmp_path,
        tier_manager=MagicMock(),
        workspace_manager=MagicMock(),
        adapter=MagicMock(),
        task_prompt="Fix the bug",
    )


class TestRunContextMaestroField:
    """Tests for maestro_injection_id field on RunContext."""

    def test_defaults_to_none(self, run_context: RunContext) -> None:
        """maestro_injection_id defaults to None."""
        assert run_context.maestro_injection_id is None

    def test_can_be_set(self, run_context: RunContext) -> None:
        """maestro_injection_id can be assigned."""
        run_context.maestro_injection_id = "inj-123"
        assert run_context.maestro_injection_id == "inj-123"


class TestStageInjectFailure:
    """Tests for stage_inject_failure()."""

    def test_noop_when_maestro_is_none(self, run_context: RunContext) -> None:
        """No-op when config.maestro is None."""
        assert run_context.config.maestro is None
        stage_inject_failure(run_context)
        assert run_context.maestro_injection_id is None

    def test_noop_when_maestro_disabled(self, run_context: RunContext) -> None:
        """No-op when config.maestro.enabled is False."""
        run_context.config = run_context.config.model_copy(
            update={"maestro": MaestroConfig(enabled=False)}
        )
        stage_inject_failure(run_context)
        assert run_context.maestro_injection_id is None

    @patch("scylla.maestro.MaestroClient")
    def test_injects_failure_when_healthy(
        self, mock_client_cls: MagicMock, maestro_run_context: RunContext
    ) -> None:
        """Injects failure and stores injection_id when API is healthy."""
        from scylla.maestro.models import HealthResponse, InjectionResult

        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.health_check.return_value = HealthResponse(status="ok")
        mock_client.inject_failure.return_value = InjectionResult(
            injection_id="inj-abc", status="active"
        )

        stage_inject_failure(maestro_run_context)

        assert maestro_run_context.maestro_injection_id == "inj-abc"
        # Verify injection file was written
        injection_file = maestro_run_context.run_dir / "maestro_injection.json"
        assert injection_file.exists()
        data = json.loads(injection_file.read_text())
        assert data["injection_id"] == "inj-abc"

    @patch("scylla.maestro.MaestroClient")
    def test_skips_injection_when_unhealthy(
        self, mock_client_cls: MagicMock, maestro_run_context: RunContext
    ) -> None:
        """Skips injection when health check returns None."""
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.health_check.return_value = None

        stage_inject_failure(maestro_run_context)

        assert maestro_run_context.maestro_injection_id is None
        mock_client.inject_failure.assert_not_called()

    @patch("scylla.maestro.MaestroClient")
    def test_graceful_degradation_on_error(
        self, mock_client_cls: MagicMock, maestro_run_context: RunContext
    ) -> None:
        """Logs warning and continues when MaestroError is raised."""
        from scylla.maestro.errors import MaestroConnectionError

        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.health_check.side_effect = MaestroConnectionError("unreachable")

        # Should not raise
        stage_inject_failure(maestro_run_context)
        assert maestro_run_context.maestro_injection_id is None


class TestStageClearFailure:
    """Tests for stage_clear_failure()."""

    def test_noop_when_no_injection_id(self, run_context: RunContext) -> None:
        """No-op when maestro_injection_id is None."""
        stage_clear_failure(run_context)
        # Should complete without error

    def test_noop_when_maestro_config_is_none(self, run_context: RunContext) -> None:
        """No-op when config.maestro is None even if injection_id is set."""
        run_context.maestro_injection_id = "inj-123"
        stage_clear_failure(run_context)
        # injection_id is NOT cleared because config.maestro is None guard returns early
        assert run_context.maestro_injection_id == "inj-123"

    @patch("scylla.maestro.MaestroClient")
    def test_clears_failure(
        self, mock_client_cls: MagicMock, maestro_run_context: RunContext
    ) -> None:
        """Clears failure and removes injection file."""
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        maestro_run_context.maestro_injection_id = "inj-abc"
        # Create injection file
        injection_file = maestro_run_context.run_dir / "maestro_injection.json"
        injection_file.write_text(json.dumps({"injection_id": "inj-abc"}))

        stage_clear_failure(maestro_run_context)

        mock_client.clear_failure.assert_called_once_with("inj-abc")
        assert maestro_run_context.maestro_injection_id is None
        assert not injection_file.exists()

    @patch("scylla.maestro.MaestroClient")
    def test_graceful_degradation_on_clear_error(
        self, mock_client_cls: MagicMock, maestro_run_context: RunContext
    ) -> None:
        """Logs warning and continues when clear_failure raises MaestroError."""
        from scylla.maestro.errors import MaestroConnectionError

        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.clear_failure.side_effect = MaestroConnectionError("unreachable")

        maestro_run_context.maestro_injection_id = "inj-abc"

        # Should not raise
        stage_clear_failure(maestro_run_context)
        # injection_id is still cleared even on error
        assert maestro_run_context.maestro_injection_id is None


class TestRestoreRunContextMaestro:
    """Tests for _restore_run_context maestro_injection_id restoration."""

    def test_restores_injection_id_from_disk(self, run_context: RunContext) -> None:
        """Restores maestro_injection_id when resuming from FAILURE_INJECTED."""
        from scylla.e2e.subtest_executor import _restore_run_context

        # Write injection file
        injection_file = run_context.run_dir / "maestro_injection.json"
        injection_file.write_text(json.dumps({"injection_id": "inj-resume-123"}))

        _restore_run_context(run_context, RunState.FAILURE_INJECTED.value)
        assert run_context.maestro_injection_id == "inj-resume-123"

    def test_no_restore_past_failure_cleared(self, run_context: RunContext) -> None:
        """Does not restore injection_id when past FAILURE_CLEARED."""
        from scylla.e2e.subtest_executor import _restore_run_context

        # Write injection file (should not be read since we're past FAILURE_CLEARED)
        injection_file = run_context.run_dir / "maestro_injection.json"
        injection_file.write_text(json.dumps({"injection_id": "inj-should-not-load"}))

        _restore_run_context(run_context, RunState.DIFF_CAPTURED.value)
        assert run_context.maestro_injection_id is None

    def test_no_restore_without_injection_file(self, run_context: RunContext) -> None:
        """Does not set injection_id when file doesn't exist."""
        from scylla.e2e.subtest_executor import _restore_run_context

        _restore_run_context(run_context, RunState.FAILURE_INJECTED.value)
        assert run_context.maestro_injection_id is None


class TestExperimentConfigMaestro:
    """Tests for ExperimentConfig.maestro field serialization."""

    def test_maestro_defaults_to_none(self) -> None:
        """ExperimentConfig.maestro defaults to None."""
        config = ExperimentConfig(
            experiment_id="test",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("/tmp/prompt.md"),
            language="python",
        )
        assert config.maestro is None

    def test_to_dict_without_maestro(self) -> None:
        """to_dict omits maestro when None."""
        config = ExperimentConfig(
            experiment_id="test",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("/tmp/prompt.md"),
            language="python",
        )
        d = config.to_dict()
        assert "maestro" not in d

    def test_to_dict_with_maestro(self, maestro_config: MaestroConfig) -> None:
        """to_dict includes maestro when configured."""
        config = ExperimentConfig(
            experiment_id="test",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("/tmp/prompt.md"),
            language="python",
            maestro=maestro_config,
        )
        d = config.to_dict()
        assert "maestro" in d
        assert d["maestro"]["enabled"] is True
        assert d["maestro"]["base_url"] == "http://localhost:23000"

    def test_save_and_load_roundtrip(self, tmp_path: Path, maestro_config: MaestroConfig) -> None:
        """ExperimentConfig with maestro survives save/load roundtrip."""
        config = ExperimentConfig(
            experiment_id="test",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("/tmp/prompt.md"),
            language="python",
            maestro=maestro_config,
        )
        config_path = tmp_path / "experiment.json"
        config.save(config_path)
        loaded = ExperimentConfig.load(config_path)
        assert loaded.maestro is not None
        assert loaded.maestro.enabled is True
        assert loaded.maestro.base_url == "http://localhost:23000"
        assert loaded.maestro.timeout_seconds == 5

    def test_load_without_maestro(self, tmp_path: Path) -> None:
        """ExperimentConfig.load works when maestro is absent from JSON."""
        config = ExperimentConfig(
            experiment_id="test",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("/tmp/prompt.md"),
            language="python",
        )
        config_path = tmp_path / "experiment.json"
        config.save(config_path)
        loaded = ExperimentConfig.load(config_path)
        assert loaded.maestro is None
