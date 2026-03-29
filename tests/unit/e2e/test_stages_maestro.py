"""Unit tests for Agamemnon chaos failure injection stages in scylla/e2e/stages.py.

Tests cover:
- stage_inject_failure: no-op when disabled, injection when enabled, graceful degradation
- stage_clear_failure: no-op when no injection, clear when injection exists, graceful degradation
- RunContext.agamemnon_injection_id field (and backward-compat maestro_injection_id alias)
- Resume: _restore_run_context loads agamemnon_injection.json (with maestro_injection.json fallback)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scylla.agamemnon.models import AgamemnonConfig
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

# Backward-compat alias — still importable
from scylla.maestro.models import MaestroConfig


@pytest.fixture
def agamemnon_config() -> AgamemnonConfig:
    """AgamemnonConfig with enabled=True for testing."""
    return AgamemnonConfig(
        base_url="http://localhost:8080",
        enabled=True,
        timeout_seconds=5,
        health_check_timeout_seconds=2,
    )


@pytest.fixture
def maestro_config() -> MaestroConfig:
    """MaestroConfig (backward-compat alias for AgamemnonConfig) with enabled=True."""
    return MaestroConfig(
        base_url="http://localhost:8080",
        enabled=True,
        timeout_seconds=5,
        health_check_timeout_seconds=2,
    )


@pytest.fixture
def minimal_config() -> ExperimentConfig:
    """ExperimentConfig without agamemnon (disabled by default)."""
    return ExperimentConfig(
        experiment_id="test-agamemnon",
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
def agamemnon_config_obj(
    minimal_config: ExperimentConfig, agamemnon_config: AgamemnonConfig
) -> ExperimentConfig:
    """ExperimentConfig with agamemnon enabled."""
    return minimal_config.model_copy(update={"agamemnon": agamemnon_config})


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
    """RunContext with agamemnon disabled."""
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
def agamemnon_run_context(
    tmp_path: Path,
    agamemnon_config_obj: ExperimentConfig,
    minimal_subtest: SubTestConfig,
) -> RunContext:
    """RunContext with agamemnon enabled."""
    run_dir = tmp_path / "run_01"
    run_dir.mkdir(exist_ok=True)
    workspace = run_dir / "workspace"
    workspace.mkdir(exist_ok=True)

    return RunContext(
        config=agamemnon_config_obj,
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


# Backward-compat alias fixture
@pytest.fixture
def maestro_run_context(agamemnon_run_context: RunContext) -> RunContext:
    """Alias for agamemnon_run_context for backward-compat test naming."""
    return agamemnon_run_context


class TestRunContextInjectionField:
    """Tests for agamemnon_injection_id field on RunContext (and backward-compat alias)."""

    def test_defaults_to_none(self, run_context: RunContext) -> None:
        """agamemnon_injection_id defaults to None."""
        assert run_context.agamemnon_injection_id is None

    def test_can_be_set(self, run_context: RunContext) -> None:
        """agamemnon_injection_id can be assigned."""
        run_context.agamemnon_injection_id = "inj-123"
        assert run_context.agamemnon_injection_id == "inj-123"

    def test_maestro_injection_id_alias_reads_agamemnon(self, run_context: RunContext) -> None:
        """maestro_injection_id property returns same value as agamemnon_injection_id."""
        run_context.agamemnon_injection_id = "inj-abc"
        assert run_context.maestro_injection_id == "inj-abc"

    def test_maestro_injection_id_alias_writes_agamemnon(self, run_context: RunContext) -> None:
        """Writing to maestro_injection_id updates agamemnon_injection_id."""
        run_context.maestro_injection_id = "inj-xyz"
        assert run_context.agamemnon_injection_id == "inj-xyz"


class TestStageInjectFailure:
    """Tests for stage_inject_failure()."""

    def test_noop_when_agamemnon_is_none(self, run_context: RunContext) -> None:
        """No-op when config.agamemnon is None."""
        assert run_context.config.agamemnon is None
        stage_inject_failure(run_context)
        assert run_context.agamemnon_injection_id is None

    def test_noop_when_agamemnon_disabled(self, run_context: RunContext) -> None:
        """No-op when config.agamemnon.enabled is False."""
        run_context.config = run_context.config.model_copy(
            update={"agamemnon": AgamemnonConfig(enabled=False)}
        )
        stage_inject_failure(run_context)
        assert run_context.agamemnon_injection_id is None

    @patch("scylla.agamemnon.AgamemnonClient")
    def test_injects_failure_when_healthy(
        self, mock_client_cls: MagicMock, agamemnon_run_context: RunContext
    ) -> None:
        """Injects failure and stores injection_id when API is healthy."""
        from scylla.agamemnon.models import HealthResponse, InjectionResult

        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.health_check.return_value = HealthResponse(status="ok")
        mock_client.inject_failure.return_value = InjectionResult(
            injection_id="inj-abc", status="active"
        )

        stage_inject_failure(agamemnon_run_context)

        assert agamemnon_run_context.agamemnon_injection_id == "inj-abc"
        # Verify injection file was written with new filename
        injection_file = agamemnon_run_context.run_dir / "agamemnon_injection.json"
        assert injection_file.exists()
        data = json.loads(injection_file.read_text())
        assert data["injection_id"] == "inj-abc"

    @patch("scylla.agamemnon.AgamemnonClient")
    def test_skips_injection_when_unhealthy(
        self, mock_client_cls: MagicMock, agamemnon_run_context: RunContext
    ) -> None:
        """Skips injection when health check returns None."""
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.health_check.return_value = None

        stage_inject_failure(agamemnon_run_context)

        assert agamemnon_run_context.agamemnon_injection_id is None
        mock_client.inject_failure.assert_not_called()

    @patch("scylla.agamemnon.AgamemnonClient")
    def test_graceful_degradation_on_error(
        self, mock_client_cls: MagicMock, agamemnon_run_context: RunContext
    ) -> None:
        """Logs warning and continues when AgamemnonError is raised."""
        from scylla.agamemnon.errors import AgamemnonConnectionError

        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.health_check.side_effect = AgamemnonConnectionError("unreachable")

        # Should not raise
        stage_inject_failure(agamemnon_run_context)
        assert agamemnon_run_context.agamemnon_injection_id is None


class TestStageClearFailure:
    """Tests for stage_clear_failure()."""

    def test_noop_when_no_injection_id(self, run_context: RunContext) -> None:
        """No-op when agamemnon_injection_id is None."""
        stage_clear_failure(run_context)
        # Should complete without error

    def test_noop_when_agamemnon_config_is_none(self, run_context: RunContext) -> None:
        """No-op when config.agamemnon is None even if injection_id is set."""
        run_context.agamemnon_injection_id = "inj-123"
        stage_clear_failure(run_context)
        # injection_id is NOT cleared because config.agamemnon is None guard returns early
        assert run_context.agamemnon_injection_id == "inj-123"

    @patch("scylla.agamemnon.AgamemnonClient")
    def test_clears_failure(
        self, mock_client_cls: MagicMock, agamemnon_run_context: RunContext
    ) -> None:
        """Clears failure and removes injection file."""
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        agamemnon_run_context.agamemnon_injection_id = "inj-abc"
        # Create injection file
        injection_file = agamemnon_run_context.run_dir / "agamemnon_injection.json"
        injection_file.write_text(json.dumps({"injection_id": "inj-abc"}))

        stage_clear_failure(agamemnon_run_context)

        mock_client.clear_failure.assert_called_once_with("inj-abc")
        assert agamemnon_run_context.agamemnon_injection_id is None
        assert not injection_file.exists()

    @patch("scylla.agamemnon.AgamemnonClient")
    def test_graceful_degradation_on_clear_error(
        self, mock_client_cls: MagicMock, agamemnon_run_context: RunContext
    ) -> None:
        """Logs warning and continues when clear_failure raises AgamemnonError."""
        from scylla.agamemnon.errors import AgamemnonConnectionError

        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.clear_failure.side_effect = AgamemnonConnectionError("unreachable")

        agamemnon_run_context.agamemnon_injection_id = "inj-abc"

        # Should not raise
        stage_clear_failure(agamemnon_run_context)
        # injection_id is still cleared even on error
        assert agamemnon_run_context.agamemnon_injection_id is None


class TestRestoreRunContextInjection:
    """Tests for _restore_run_context agamemnon_injection_id restoration."""

    def test_restores_injection_id_from_agamemnon_file(self, run_context: RunContext) -> None:
        """Restores agamemnon_injection_id when resuming from FAILURE_INJECTED."""
        from scylla.e2e.subtest_executor import _restore_run_context

        # Write new-style injection file
        injection_file = run_context.run_dir / "agamemnon_injection.json"
        injection_file.write_text(json.dumps({"injection_id": "inj-resume-123"}))

        _restore_run_context(run_context, RunState.FAILURE_INJECTED.value)
        assert run_context.agamemnon_injection_id == "inj-resume-123"

    def test_restores_injection_id_from_maestro_fallback(self, run_context: RunContext) -> None:
        """Falls back to maestro_injection.json for pre-migration checkpoints."""
        from scylla.e2e.subtest_executor import _restore_run_context

        # Write old-style injection file (backward compat)
        injection_file = run_context.run_dir / "maestro_injection.json"
        injection_file.write_text(json.dumps({"injection_id": "inj-legacy-456"}))

        _restore_run_context(run_context, RunState.FAILURE_INJECTED.value)
        assert run_context.agamemnon_injection_id == "inj-legacy-456"

    def test_no_restore_past_failure_cleared(self, run_context: RunContext) -> None:
        """Does not restore injection_id when past FAILURE_CLEARED."""
        from scylla.e2e.subtest_executor import _restore_run_context

        # Write injection file (should not be read since we're past FAILURE_CLEARED)
        injection_file = run_context.run_dir / "agamemnon_injection.json"
        injection_file.write_text(json.dumps({"injection_id": "inj-should-not-load"}))

        _restore_run_context(run_context, RunState.DIFF_CAPTURED.value)
        assert run_context.agamemnon_injection_id is None

    def test_no_restore_without_injection_file(self, run_context: RunContext) -> None:
        """Does not set injection_id when file doesn't exist."""
        from scylla.e2e.subtest_executor import _restore_run_context

        _restore_run_context(run_context, RunState.FAILURE_INJECTED.value)
        assert run_context.agamemnon_injection_id is None


class TestExperimentConfigAgamemnon:
    """Tests for ExperimentConfig.agamemnon field serialization."""

    def test_agamemnon_defaults_to_none(self) -> None:
        """ExperimentConfig.agamemnon defaults to None."""
        config = ExperimentConfig(
            experiment_id="test",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("/tmp/prompt.md"),
            language="python",
        )
        assert config.agamemnon is None

    def test_to_dict_without_agamemnon(self) -> None:
        """to_dict omits agamemnon when None."""
        config = ExperimentConfig(
            experiment_id="test",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("/tmp/prompt.md"),
            language="python",
        )
        d = config.to_dict()
        assert "agamemnon" not in d

    def test_to_dict_with_agamemnon(self, agamemnon_config: AgamemnonConfig) -> None:
        """to_dict includes agamemnon when configured."""
        config = ExperimentConfig(
            experiment_id="test",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("/tmp/prompt.md"),
            language="python",
            agamemnon=agamemnon_config,
        )
        d = config.to_dict()
        assert "agamemnon" in d
        assert d["agamemnon"]["enabled"] is True
        assert d["agamemnon"]["base_url"] == "http://localhost:8080"

    def test_save_and_load_roundtrip(
        self, tmp_path: Path, agamemnon_config: AgamemnonConfig
    ) -> None:
        """ExperimentConfig with agamemnon survives save/load roundtrip."""
        config = ExperimentConfig(
            experiment_id="test",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("/tmp/prompt.md"),
            language="python",
            agamemnon=agamemnon_config,
        )
        config_path = tmp_path / "experiment.json"
        config.save(config_path)
        loaded = ExperimentConfig.load(config_path)
        assert loaded.agamemnon is not None
        assert loaded.agamemnon.enabled is True
        assert loaded.agamemnon.base_url == "http://localhost:8080"
        assert loaded.agamemnon.timeout_seconds == 5

    def test_load_without_agamemnon(self, tmp_path: Path) -> None:
        """ExperimentConfig.load works when agamemnon is absent from JSON."""
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
        assert loaded.agamemnon is None

    def test_backward_compat_maestro_field(self, maestro_config: MaestroConfig) -> None:
        """ExperimentConfig.maestro backward-compat field is still accepted."""
        config = ExperimentConfig(
            experiment_id="test",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("/tmp/prompt.md"),
            language="python",
            maestro=maestro_config,
        )
        # maestro field is accepted as AgamemnonConfig alias
        assert config.maestro is not None
        assert config.maestro.enabled is True
