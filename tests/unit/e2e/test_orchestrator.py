"""Integration tests for test orchestrator.

Python justification: Required for pytest testing framework.
"""

from pathlib import Path

import pytest

from scylla.orchestrator import EvalOrchestrator, OrchestratorConfig


class EvalOrchestratorConfig:
    """Tests for OrchestratorConfig."""

    def test_defaults(self) -> None:
        """Test Defaults."""
        config = OrchestratorConfig()
        assert config.base_path == Path(".")
        assert config.runs_per_tier == 10
        assert config.tiers is None
        assert config.model is None
        assert config.quiet is False
        assert config.verbose is False

    def test_custom_values(self) -> None:
        """Test Custom values."""
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
        """Test Init default."""
        orchestrator = EvalOrchestrator()
        assert orchestrator.config.base_path == Path(".")
        assert orchestrator.loader is not None
        assert orchestrator.progress is not None
        assert orchestrator.result_writer is not None

    def test_init_with_config(self) -> None:
        """Test Init with config."""
        config = OrchestratorConfig(
            base_path=Path("/tmp/test"),
            quiet=True,
        )
        orchestrator = EvalOrchestrator(config)
        assert orchestrator.config.base_path == Path("/tmp/test")
        assert orchestrator.config.quiet is True

    def test_set_adapter(self) -> None:
        """Test Set adapter."""
        orchestrator = EvalOrchestrator()

        def mock_adapter(**kwargs):
            return {"tokens_in": 100, "tokens_out": 50}

        orchestrator.set_adapter(mock_adapter)
        assert orchestrator._adapter_func is mock_adapter

    def test_set_judge(self) -> None:
        """Test Set judge."""
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
language: mojo
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
    S: 1.00
    A: 0.80
    B: 0.60
    C: 0.40
    D: 0.20
    F: 0.0
""")

        # Create defaults.yaml
        defaults_yaml = config_dir / "defaults.yaml"
        defaults_yaml.write_text("""
runs_per_tier: 10
timeout_seconds: 3600
max_cost_usd: 10.0
output:
  runs_dir: "runs"
  summaries_dir: "summaries"
  reports_dir: "reports"
""")

        return tmp_path

    def test_orchestrator_creates_with_fixture(self, test_env: Path) -> None:
        """Test Orchestrator creates with fixture."""
        config = OrchestratorConfig(
            base_path=test_env,
            quiet=True,
        )
        orchestrator = EvalOrchestrator(config)
        assert orchestrator.config.base_path == test_env

    def test_orchestrator_loads_test(self, test_env: Path) -> None:
        """Test Orchestrator loads test."""
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
        """Test Orchestrator loads rubric."""
        config = OrchestratorConfig(
            base_path=test_env,
            quiet=True,
        )
        orchestrator = EvalOrchestrator(config)

        rubric = orchestrator.loader.load_rubric("001-test")
        assert len(rubric.requirements) == 1
        assert rubric.requirements[0].id == "R001"
        assert rubric.grading.pass_threshold == 0.70


class TestEvalOrchestratorEndToEnd:
    """End-to-end tests with mock adapter and judge."""

    @pytest.fixture
    def test_env(self, tmp_path: Path) -> Path:
        """Create complete test environment."""
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
language: mojo
source:
  repo: "https://github.com/octocat/Hello-World"
  hash: "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"
task:
  prompt_file: "prompt.md"
  timeout_seconds: 60
tiers:
  - T0
  - T1
  - T2
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
    S: 1.00
    A: 0.80
    B: 0.60
    C: 0.40
    D: 0.20
    F: 0.0
""")

        # Create defaults.yaml
        defaults_yaml = config_dir / "defaults.yaml"
        defaults_yaml.write_text("""
runs_per_tier: 10
timeout_seconds: 3600
max_cost_usd: 10.0
output:
  runs_dir: "runs"
  summaries_dir: "summaries"
  reports_dir: "reports"
""")

        return tmp_path

    def test_run_single_with_mocks(self, test_env: Path) -> None:
        """Test complete single run flow with mock adapter/judge."""
        from unittest.mock import patch

        config = OrchestratorConfig(
            base_path=test_env,
            quiet=True,
        )
        orchestrator = EvalOrchestrator(config)

        # Set mock adapter
        def mock_adapter(**kwargs):
            return {
                "tokens_in": 1000,
                "tokens_out": 500,
                "cost_usd": 0.05,
                "exit_code": 0,
            }

        # Set mock judge
        def mock_judge(**kwargs):
            return {
                "passed": True,
                "score": 0.85,
                "grade": "B",
            }

        orchestrator.set_adapter(mock_adapter)
        orchestrator.set_judge(mock_judge)

        # Mock git operations to avoid network calls
        with patch.object(
            orchestrator.loader.__class__, "_load_yaml", wraps=orchestrator.loader._load_yaml
        ):
            with patch("scylla.executor.workspace.clone_repo"):
                with patch("scylla.executor.workspace.checkout_hash"):
                    result = orchestrator.run_single(
                        test_id="001-test",
                        model_id="test-model",
                        tier_id="T0",
                        run_number=1,
                    )

        # Verify result structure
        assert result.judgment.passed is True
        assert result.judgment.impl_rate == 0.85
        assert result.judgment.letter_grade == "B"
        assert result.metrics.cost_usd == 0.05
        assert result.execution.status == "completed"

    def test_run_single_result_file_written(self, test_env: Path) -> None:
        """Verify result.json is correctly written to disk."""
        import json
        from unittest.mock import patch

        config = OrchestratorConfig(
            base_path=test_env,
            quiet=True,
        )
        orchestrator = EvalOrchestrator(config)

        # Set simple mocks
        orchestrator.set_adapter(
            lambda **k: {"tokens_in": 100, "tokens_out": 50, "cost_usd": 0.01, "exit_code": 0}
        )
        orchestrator.set_judge(lambda **k: {"passed": True, "score": 0.9, "grade": "A"})

        with patch("scylla.executor.workspace.clone_repo"):
            with patch("scylla.executor.workspace.checkout_hash"):
                orchestrator.run_single(
                    test_id="001-test",
                    model_id="test-model",
                    tier_id="T0",
                    run_number=1,
                )

        # Find the result file
        runs_dir = test_env / "runs"
        result_files = list(runs_dir.rglob("result.json"))
        assert len(result_files) >= 1

        # Verify JSON content
        with open(result_files[0]) as f:
            data = json.load(f)

        assert data["test_id"] == "001-test"
        assert data["tier_id"] == "T0"
        assert data["judgment"]["passed"] is True

    def test_run_test_multi_tier(self, test_env: Path) -> None:
        """Test running same test across T0, T1, T2 tiers."""
        from unittest.mock import patch

        config = OrchestratorConfig(
            base_path=test_env,
            runs_per_tier=1,
            quiet=True,
        )
        orchestrator = EvalOrchestrator(config)

        # Set mocks
        orchestrator.set_adapter(
            lambda **k: {"tokens_in": 100, "tokens_out": 50, "cost_usd": 0.01, "exit_code": 0}
        )
        orchestrator.set_judge(lambda **k: {"passed": True, "score": 0.8, "grade": "B"})

        with patch("scylla.executor.workspace.clone_repo"):
            with patch("scylla.executor.workspace.checkout_hash"):
                results = orchestrator.run_test(
                    test_id="001-test",
                    models=["test-model"],
                    tiers=["T0", "T1", "T2"],
                    runs_per_tier=1,
                )

        # Verify we got 3 results (one per tier)
        assert len(results) == 3
        tier_ids = [r.tier_id for r in results]
        assert set(tier_ids) == {"T0", "T1", "T2"}

        # All results should have correct structure
        for result in results:
            assert result.test_id == "001-test"
            assert result.judgment.passed is True

    def test_run_single_with_failing_judge(self, test_env: Path) -> None:
        """Test when judge returns passed=False."""
        from unittest.mock import patch

        config = OrchestratorConfig(
            base_path=test_env,
            quiet=True,
        )
        orchestrator = EvalOrchestrator(config)

        # Mock with failing judgment
        orchestrator.set_adapter(
            lambda **k: {"tokens_in": 100, "tokens_out": 50, "cost_usd": 0.02, "exit_code": 0}
        )
        orchestrator.set_judge(lambda **k: {"passed": False, "score": 0.3, "grade": "F"})

        with patch("scylla.executor.workspace.clone_repo"):
            with patch("scylla.executor.workspace.checkout_hash"):
                result = orchestrator.run_single(
                    test_id="001-test",
                    model_id="test-model",
                    tier_id="T0",
                    run_number=1,
                )

        # Verify failed result
        assert result.judgment.passed is False
        assert result.judgment.impl_rate == 0.3
        assert result.judgment.letter_grade == "F"
        # Cost-of-pass should be infinity for failed runs
        assert result.grading.cost_of_pass == float("inf")

    def test_result_metrics_calculation(self, test_env: Path) -> None:
        """Verify composite score and cost-of-pass calculations."""
        from unittest.mock import patch

        config = OrchestratorConfig(
            base_path=test_env,
            quiet=True,
        )
        orchestrator = EvalOrchestrator(config)

        # Mock with specific values for calculation verification
        orchestrator.set_adapter(
            lambda **k: {"tokens_in": 100, "tokens_out": 50, "cost_usd": 0.10, "exit_code": 0}
        )
        orchestrator.set_judge(lambda **k: {"passed": True, "score": 0.80, "grade": "B"})

        with patch("scylla.executor.workspace.clone_repo"):
            with patch("scylla.executor.workspace.checkout_hash"):
                result = orchestrator.run_single(
                    test_id="001-test",
                    model_id="test-model",
                    tier_id="T0",
                    run_number=1,
                )

        # Verify composite score = (pass_rate + impl_rate) / 2 (50/50 weights)
        # = (1.0 + 0.80) / 2 = 0.90
        assert abs(result.grading.composite_score - 0.90) < 0.001

        # Verify cost-of-pass = cost_usd / pass_rate = 0.10 / 1.0 = 0.10
        assert abs(result.grading.cost_of_pass - 0.10) < 0.001
