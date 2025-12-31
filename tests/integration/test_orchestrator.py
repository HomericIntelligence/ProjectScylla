"""Integration tests for test orchestrator.

Python justification: Required for pytest testing framework.
"""

import tempfile
from pathlib import Path

import pytest

from scylla.orchestrator import OrchestratorConfig, EvalOrchestrator


class EvalOrchestratorConfig:
    """Tests for OrchestratorConfig."""

    def test_defaults(self) -> None:
        config = OrchestratorConfig()
        assert config.base_path == Path(".")
        assert config.runs_per_tier == 10
        assert config.tiers is None
        assert config.model is None
        assert config.quiet is False
        assert config.verbose is False

    def test_custom_values(self) -> None:
        config = OrchestratorConfig(
            base_path=Path("/tmp/test"),
            runs_per_tier=5,
            tiers=["T0", "T1"],
            model="test-model",
            quiet=True,
        )
        assert config.base_path == Path("/tmp/test")
        assert config.runs_per_tier == 5
        assert config.tiers == ["T0", "T1"]
        assert config.model == "test-model"
        assert config.quiet is True


class TestEvalOrchestrator:
    """Tests for EvalOrchestrator."""

    def test_init_default(self) -> None:
        orchestrator = EvalOrchestrator()
        assert orchestrator.config.base_path == Path(".")
        assert orchestrator.loader is not None
        assert orchestrator.progress is not None
        assert orchestrator.result_writer is not None

    def test_init_with_config(self) -> None:
        config = OrchestratorConfig(
            base_path=Path("/tmp/test"),
            quiet=True,
        )
        orchestrator = EvalOrchestrator(config)
        assert orchestrator.config.base_path == Path("/tmp/test")
        assert orchestrator.config.quiet is True

    def test_set_adapter(self) -> None:
        orchestrator = EvalOrchestrator()

        def mock_adapter(**kwargs):
            return {"tokens_in": 100, "tokens_out": 50}

        orchestrator.set_adapter(mock_adapter)
        assert orchestrator._adapter_func is mock_adapter

    def test_set_judge(self) -> None:
        orchestrator = EvalOrchestrator()

        def mock_judge(**kwargs):
            return {"passed": True, "score": 1.0}

        orchestrator.set_judge(mock_judge)
        assert orchestrator._judge_func is mock_judge


class EvalOrchestratorWithFixture:
    """Tests for orchestrator with proper test fixture."""

    @pytest.fixture
    def test_env(self, tmp_path: Path):
        """Create a test environment with config files."""
        # Create directory structure
        tests_dir = tmp_path / "tests" / "001-test"
        expected_dir = tests_dir / "expected"
        config_dir = tmp_path / "config"
        runs_dir = tmp_path / "runs"

        tests_dir.mkdir(parents=True)
        expected_dir.mkdir(parents=True)
        config_dir.mkdir(parents=True)
        runs_dir.mkdir(parents=True)

        # Create test.yaml
        test_yaml = tests_dir / "test.yaml"
        test_yaml.write_text("""
id: "001-test"
name: "Test Case"
description: "A test case for testing"
source:
  repo: "https://github.com/octocat/Hello-World"
  hash: "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"
task:
  prompt_file: "prompt.md"
  timeout_seconds: 60
tiers:
  - T0
validation:
  criteria_file: "expected/criteria.md"
  rubric_file: "expected/rubric.yaml"
""")

        # Create prompt.md
        prompt_md = tests_dir / "prompt.md"
        prompt_md.write_text("# Test Prompt\nDo something.")

        # Create criteria.md
        criteria_md = expected_dir / "criteria.md"
        criteria_md.write_text("# Criteria\n- Must work")

        # Create rubric.yaml
        rubric_yaml = expected_dir / "rubric.yaml"
        rubric_yaml.write_text("""
requirements:
  - id: "R001"
    description: "Must work"
    weight: 1.0
    evaluation: "binary"
grading:
  pass_threshold: 0.70
  grade_scale:
    A: 0.95
    B: 0.85
    C: 0.75
    D: 0.65
    F: 0.0
""")

        # Create defaults.yaml
        defaults_yaml = config_dir / "defaults.yaml"
        defaults_yaml.write_text("""
runs_per_tier: 9
timeout_seconds: 3600
max_cost_usd: 10.0
output:
  runs_dir: "runs"
  summaries_dir: "summaries"
  reports_dir: "reports"
""")

        return tmp_path

    def test_orchestrator_creates_with_fixture(self, test_env: Path) -> None:
        config = OrchestratorConfig(
            base_path=test_env,
            quiet=True,
        )
        orchestrator = EvalOrchestrator(config)
        assert orchestrator.config.base_path == test_env

    def test_orchestrator_loads_test(self, test_env: Path) -> None:
        config = OrchestratorConfig(
            base_path=test_env,
            quiet=True,
        )
        orchestrator = EvalOrchestrator(config)

        # Load test case through the loader
        test_case = orchestrator.loader.load_test("001-test")
        assert test_case.id == "001-test"
        assert test_case.name == "Test Case"
        assert test_case.source.repo == "https://github.com/octocat/Hello-World"

    def test_orchestrator_loads_rubric(self, test_env: Path) -> None:
        config = OrchestratorConfig(
            base_path=test_env,
            quiet=True,
        )
        orchestrator = EvalOrchestrator(config)

        rubric = orchestrator.loader.load_rubric("001-test")
        assert len(rubric.requirements) == 1
        assert rubric.requirements[0].id == "R001"
        assert rubric.grading.pass_threshold == 0.70
