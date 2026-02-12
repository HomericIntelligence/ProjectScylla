"""Unit tests for data loader.

Note: These tests use the public API of the loader module.
Internal/private helper functions are not tested directly.
"""

import pytest


def test_loader_imports():
    """Test that loader module can be imported."""
    # Basic smoke test - can import the module
    import scylla.analysis.loader

    assert scylla.analysis.loader is not None


def test_load_run_signature():
    """Test load_run function has expected signature."""
    import inspect

    from scylla.analysis.loader import load_run

    # Verify function exists and has expected parameters
    sig = inspect.signature(load_run)
    params = list(sig.parameters.keys())

    # Should have parameters for experiment, tier, subtest, run_dir
    assert "run_dir" in params
    assert "experiment" in params
    assert "tier" in params
    assert "subtest" in params


def test_load_all_experiments_signature():
    """Test load_all_experiments function has expected signature."""
    import inspect

    from scylla.analysis.loader import load_all_experiments

    # Verify function exists
    sig = inspect.signature(load_all_experiments)
    assert sig is not None


def test_validate_numeric_with_valid_values():
    """Test validate_numeric with valid numeric inputs."""
    from scylla.analysis.loader import validate_numeric

    # Valid float
    assert validate_numeric(1.5, "test") == 1.5

    # Valid int (coerced to float)
    assert validate_numeric(42, "test") == 42.0

    # Valid string (coerced to float)
    assert validate_numeric("3.14", "test") == 3.14

    # Zero is valid
    assert validate_numeric(0, "test") == 0.0
    assert validate_numeric(0.0, "test") == 0.0


def test_validate_numeric_with_invalid_values():
    """Test validate_numeric with invalid inputs returns default."""
    import numpy as np

    from scylla.analysis.loader import validate_numeric

    # None returns default
    assert np.isnan(validate_numeric(None, "test", np.nan))
    assert validate_numeric(None, "test", 99.0) == 99.0

    # Invalid string returns default
    assert np.isnan(validate_numeric("invalid", "test", np.nan))

    # List/dict returns default
    assert np.isnan(validate_numeric([1, 2, 3], "test", np.nan))
    assert np.isnan(validate_numeric({"a": 1}, "test", np.nan))


def test_validate_numeric_with_special_values():
    """Test validate_numeric handles inf and nan."""
    import numpy as np

    from scylla.analysis.loader import validate_numeric

    # inf returns default
    assert np.isnan(validate_numeric(np.inf, "test", np.nan))
    assert validate_numeric(np.inf, "test", 0.0) == 0.0

    # -inf returns default
    assert np.isnan(validate_numeric(-np.inf, "test", np.nan))

    # nan returns default
    assert np.isnan(validate_numeric(np.nan, "test", np.nan))


def test_validate_bool_with_valid_values():
    """Test validate_bool with valid boolean inputs."""
    from scylla.analysis.loader import validate_bool

    # Native bool
    assert validate_bool(True, "test") is True
    assert validate_bool(False, "test") is False

    # String representations
    assert validate_bool("true", "test") is True
    assert validate_bool("True", "test") is True
    assert validate_bool("TRUE", "test") is True
    assert validate_bool("yes", "test") is True
    assert validate_bool("1", "test") is True

    assert validate_bool("false", "test") is False
    assert validate_bool("False", "test") is False
    assert validate_bool("no", "test") is False
    assert validate_bool("0", "test") is False

    # Numeric values (0=False, non-zero=True)
    assert validate_bool(1, "test") is True
    assert validate_bool(42, "test") is True
    assert validate_bool(0, "test") is False


def test_validate_bool_with_invalid_values():
    """Test validate_bool with invalid inputs returns default."""
    from scylla.analysis.loader import validate_bool

    # None returns default
    assert validate_bool(None, "test", False) is False
    assert validate_bool(None, "test", True) is True

    # Invalid string returns default
    assert validate_bool("maybe", "test", False) is False

    # List/dict returns default
    assert validate_bool([True], "test", False) is False
    assert validate_bool({"a": True}, "test", False) is False


def test_validate_int_with_valid_values():
    """Test validate_int with valid integer inputs."""
    from scylla.analysis.loader import validate_int

    # Valid int
    assert validate_int(42, "test") == 42

    # Valid float (truncated)
    assert validate_int(3.14, "test") == 3
    assert validate_int(3.9, "test") == 3

    # Valid string
    assert validate_int("123", "test") == 123

    # Zero is valid
    assert validate_int(0, "test") == 0

    # Negative is valid
    assert validate_int(-5, "test") == -5


def test_validate_int_with_invalid_values():
    """Test validate_int with invalid inputs returns default."""
    from scylla.analysis.loader import validate_int

    # None returns default
    assert validate_int(None, "test", -1) == -1
    assert validate_int(None, "test", 99) == 99

    # Invalid string returns default
    assert validate_int("invalid", "test", -1) == -1

    # List/dict returns default
    assert validate_int([1, 2, 3], "test", -1) == -1
    assert validate_int({"a": 1}, "test", -1) == -1


# Integration test removed - requires actual filesystem data.
# For integration testing, use functional tests in tests/functional/
# or run analysis pipeline on real data in ~/fullruns/


def test_model_id_to_display_removes_date_suffix():
    """Test that model_id_to_display removes date suffix from model IDs.

    Regression test for P0 bug where re.sub replaced pattern within full string,
    causing date suffix to leak through (e.g., "Sonnet 4.5-20250929").
    """
    from scylla.analysis.loader import model_id_to_display

    # Test date-suffixed models
    assert model_id_to_display("claude-sonnet-4-5-20250929") == "Sonnet 4.5"
    assert model_id_to_display("claude-opus-4-5-20251101") == "Opus 4.5"
    assert model_id_to_display("claude-haiku-3-5-20241022") == "Haiku 3.5"

    # Test without date suffix (should still work)
    assert model_id_to_display("claude-sonnet-3-5") == "Sonnet 3.5"
    assert model_id_to_display("claude-opus-4-0") == "Opus 4.0"

    # Test unknown model (should return as-is)
    assert model_id_to_display("gpt-4") == "gpt-4"
    assert model_id_to_display("unknown-model") == "unknown-model"


def test_dynamic_judge_discovery(tmp_path):
    """Test that judge loading discovers judge directories dynamically.

    Regression test for P1 bug where hardcoded loop [1,2,3] silently ignored
    judges 4+ and skipped missing judges 1-3.
    """
    from scylla.analysis.loader import load_run

    # Create mock run directory structure
    run_dir = tmp_path / "run_01"
    run_dir.mkdir()

    # Create run_result.json
    run_result = {
        "judge_score": 0.8,
        "judge_passed": True,
        "judge_grade": "A",
        "cost_usd": 0.05,
        "duration_seconds": 10.0,
        "agent_duration_seconds": 8.0,
        "judge_duration_seconds": 2.0,
        "token_stats": {
            "input_tokens": 1000,
            "output_tokens": 500,
            "cache_creation_tokens": 100,
            "cache_read_tokens": 200,
        },
        "exit_code": 0,
    }
    (run_dir / "run_result.json").write_text(__import__("json").dumps(run_result))

    # Create judge directory with non-sequential judges (01, 03, 05 - skip 02, 04)
    judge_dir = run_dir / "judge"
    judge_dir.mkdir()

    for judge_num in [1, 3, 5]:
        judge_subdir = judge_dir / f"judge_{judge_num:02d}"
        judge_subdir.mkdir()

        # Create judgment.json
        judgment = {
            "score": 0.7 + (judge_num * 0.05),
            "passed": True,
            "grade": "B",
            "is_valid": True,
            "reasoning": f"Judge {judge_num} reasoning",
            "criteria_scores": {},
        }
        (judge_subdir / "judgment.json").write_text(__import__("json").dumps(judgment))

        # Create MODEL.md with proper format
        (judge_subdir / "MODEL.md").write_text(f"**Model**: claude-opus-4-5-judge{judge_num}\n")

    # Load the run
    run_data = load_run(
        run_dir=run_dir,
        experiment="test-experiment",
        tier="T0",
        subtest="00",
        agent_model="Sonnet 4.5",
    )

    # Should discover all 3 judges (01, 03, 05), not just [1, 2, 3]
    assert len(run_data.judges) == 3

    # Verify judge numbers are correct
    judge_numbers = {judge.judge_number for judge in run_data.judges}
    assert judge_numbers == {1, 3, 5}

    # Verify scores match
    judge_scores = {judge.judge_number: judge.score for judge in run_data.judges}
    assert judge_scores[1] == pytest.approx(0.75, abs=0.01)
    assert judge_scores[3] == pytest.approx(0.85, abs=0.01)
    assert judge_scores[5] == pytest.approx(0.95, abs=0.01)


def test_load_run_with_missing_fields(tmp_path):
    """Test that load_run handles missing fields with NaN defaults."""
    from scylla.analysis.loader import load_run

    # Create minimal run directory
    run_dir = tmp_path / "run_01"
    run_dir.mkdir()

    # Create run_result.json with minimal fields (no scores, costs)
    run_result = {
        "judge_passed": False,
        "exit_code": 1,
    }
    (run_dir / "run_result.json").write_text(__import__("json").dumps(run_result))

    # No judges directory - should handle gracefully

    # Load the run
    run_data = load_run(
        run_dir=run_dir,
        experiment="test",
        tier="T0",
        subtest="00",
        agent_model="Sonnet 4.5",
    )

    # Verify NaN defaults for missing numeric fields
    import numpy as np

    assert np.isnan(run_data.score)
    assert np.isnan(run_data.cost_usd)
    assert np.isnan(run_data.duration_seconds)

    # Verify non-numeric defaults
    assert run_data.passed is False
    assert run_data.grade == "F"
    assert run_data.exit_code == 1
    assert len(run_data.judges) == 0


def test_load_run_with_malformed_json(tmp_path):
    """Test that load_run handles malformed JSON gracefully."""
    from scylla.analysis.loader import load_run

    # Create run directory with malformed JSON
    run_dir = tmp_path / "run_01"
    run_dir.mkdir()

    # Write malformed JSON
    (run_dir / "run_result.json").write_text("{invalid json")

    # Should raise JSONDecodeError
    with pytest.raises(__import__("json").JSONDecodeError):
        load_run(
            run_dir=run_dir,
            experiment="test",
            tier="T0",
            subtest="00",
            agent_model="Sonnet 4.5",
        )


def test_load_run_missing_file(tmp_path):
    """Test that load_run raises FileNotFoundError for missing run_result.json."""
    from scylla.analysis.loader import load_run

    # Create empty run directory (no run_result.json)
    run_dir = tmp_path / "run_01"
    run_dir.mkdir()

    # Should raise FileNotFoundError
    with pytest.raises(FileNotFoundError):
        load_run(
            run_dir=run_dir,
            experiment="test",
            tier="T0",
            subtest="00",
            agent_model="Sonnet 4.5",
        )


def test_load_judgment_with_criteria(tmp_path):
    """Test loading judgment with full criteria scores."""
    from scylla.analysis.loader import load_judgment

    # Create judgment directory
    judgment_path = tmp_path / "judgment.json"
    model_path = tmp_path / "MODEL.md"

    # Create comprehensive judgment with criteria
    judgment = {
        "score": 0.85,
        "passed": True,
        "grade": "A",
        "is_valid": True,
        "reasoning": "Well implemented",
        "criteria_scores": {
            "functional": {
                "achieved": 8.5,
                "max": 10.0,
                "score": 0.85,
                "items": {
                    "req1": {"achieved": 5, "max": 5, "reason": "Perfect"},
                    "req2": {"achieved": 3.5, "max": 5, "reason": "Good"},
                },
            },
            "code_quality": {
                "achieved": 9.0,
                "max": 10.0,
                "score": 0.90,
                "items": {},
            },
        },
    }
    judgment_path.write_text(__import__("json").dumps(judgment))
    model_path.write_text("**Model**: claude-opus-4-5-20251101\n")

    # Load judgment
    judge_eval = load_judgment(judgment_path, judge_number=1)

    # Verify top-level fields
    assert judge_eval.score == pytest.approx(0.85)
    assert judge_eval.passed is True
    assert judge_eval.grade == "A"
    # Note: load_judgment returns raw model ID, not display name
    assert judge_eval.judge_model == "claude-opus-4-5-20251101"
    assert judge_eval.judge_number == 1

    # Verify criteria
    assert len(judge_eval.criteria) == 2
    assert "functional" in judge_eval.criteria
    assert "code_quality" in judge_eval.criteria

    # Verify functional criterion
    func_crit = judge_eval.criteria["functional"]
    assert func_crit.achieved == pytest.approx(8.5)
    assert func_crit.max_points == pytest.approx(10.0)
    assert func_crit.score == pytest.approx(0.85)
    assert len(func_crit.items) == 2

    # Verify items
    assert "req1" in func_crit.items
    assert func_crit.items["req1"].achieved == pytest.approx(5)
    assert func_crit.items["req1"].max_points == pytest.approx(5)


def test_load_judgment_with_none_criteria(tmp_path):
    """Test loading judgment with None criteria (edge case)."""
    from scylla.analysis.loader import load_judgment

    judgment_path = tmp_path / "judgment.json"
    model_path = tmp_path / "MODEL.md"

    # Judgment with None criteria_scores
    judgment = {
        "score": 0.5,
        "passed": False,
        "grade": "F",
        "is_valid": True,
        "reasoning": "Failed",
        "criteria_scores": None,  # Edge case: None instead of dict
    }
    judgment_path.write_text(__import__("json").dumps(judgment))
    model_path.write_text("**Model**: claude-haiku-4-5-20241223\n")

    # Load judgment - should handle None gracefully
    judge_eval = load_judgment(judgment_path, judge_number=2)

    assert judge_eval.score == pytest.approx(0.5)
    assert len(judge_eval.criteria) == 0  # Should be empty dict


def test_load_experiment_skips_corrupted_runs(tmp_path):
    """Test that load_experiment skips corrupted runs with warnings."""
    from scylla.analysis.loader import load_experiment

    # Create experiment directory structure
    exp_dir = tmp_path / "test-experiment" / "2026-01-31T10-00-00-test"
    tier_dir = exp_dir / "T0" / "00"
    tier_dir.mkdir(parents=True)

    # Create 3 runs: 2 good, 1 corrupted
    for run_num in [1, 2, 3]:
        run_dir = tier_dir / f"run_{run_num:02d}"
        run_dir.mkdir()

        if run_num == 2:
            # Corrupted run - malformed JSON
            (run_dir / "run_result.json").write_text("{bad json")
        else:
            # Good run
            run_result = {
                "judge_score": 0.8,
                "judge_passed": True,
                "judge_grade": "A",
                "cost_usd": 0.05,
                "duration_seconds": 10.0,
                "token_stats": {},
                "exit_code": 0,
            }
            (run_dir / "run_result.json").write_text(__import__("json").dumps(run_result))

    # Load experiment - should skip corrupted run 2, load runs 1 and 3
    runs = load_experiment(exp_dir, agent_model="Sonnet 4.5")

    # Should have loaded 2 out of 3 runs
    assert len(runs) == 2

    # Verify run numbers
    run_numbers = {run.run_number for run in runs}
    assert run_numbers == {1, 3}


def test_parse_judge_model_handles_missing_file(tmp_path):
    """Test parse_judge_model raises FileNotFoundError for missing MODEL.md."""
    from scylla.analysis.loader import parse_judge_model

    # Non-existent file
    model_path = tmp_path / "MODEL.md"

    # Should raise FileNotFoundError
    with pytest.raises(FileNotFoundError):
        parse_judge_model(model_path)


def test_parse_judge_model_handles_invalid_format(tmp_path):
    """Test parse_judge_model raises ValueError for invalid format."""
    from scylla.analysis.loader import parse_judge_model

    # Create MODEL.md without proper format
    model_path = tmp_path / "MODEL.md"
    model_path.write_text("This is not the right format\n")

    # Should raise ValueError
    with pytest.raises(ValueError, match="Could not find model"):
        parse_judge_model(model_path)


def test_parse_judge_model_success(tmp_path):
    """Test parse_judge_model extracts model correctly."""
    from scylla.analysis.loader import parse_judge_model

    model_path = tmp_path / "MODEL.md"
    model_path.write_text("**Model**: claude-sonnet-4-5-20250929\n")

    result = parse_judge_model(model_path)
    assert result == "claude-sonnet-4-5-20250929"


def test_model_id_to_display_comprehensive():
    """Comprehensive test for model_id_to_display function."""
    from scylla.analysis.loader import model_id_to_display

    # Claude models with dates
    assert model_id_to_display("claude-sonnet-4-5-20250929") == "Sonnet 4.5"
    assert model_id_to_display("claude-opus-4-5-20251101") == "Opus 4.5"
    assert model_id_to_display("claude-haiku-4-5-20241223") == "Haiku 4.5"
    assert model_id_to_display("claude-haiku-3-5-20241022") == "Haiku 3.5"

    # Claude models without dates
    assert model_id_to_display("claude-sonnet-3-5") == "Sonnet 3.5"
    assert model_id_to_display("claude-opus-4-0") == "Opus 4.0"

    # Unknown models (pass through)
    assert model_id_to_display("gpt-4") == "gpt-4"
    assert model_id_to_display("gemini-pro") == "gemini-pro"
    assert model_id_to_display("unknown-model-123") == "unknown-model-123"

    # Edge cases
    assert model_id_to_display("") == ""
    assert model_id_to_display("claude") == "claude"


def test_schema_validation_valid_data(tmp_path):
    """Test that valid run_result.json passes schema validation."""
    from scylla.analysis.loader import load_run

    # Create run directory with valid data
    run_dir = tmp_path / "run_01"
    run_dir.mkdir()

    # Create valid run_result.json
    run_result = {
        "run_number": 1,
        "exit_code": 0,
        "token_stats": {
            "input_tokens": 1000,
            "output_tokens": 500,
            "cache_creation_tokens": 100,
            "cache_read_tokens": 200,
        },
        "tokens_input": 1200,
        "tokens_output": 500,
        "cost_usd": 0.05,
        "duration_seconds": 10.0,
        "agent_duration_seconds": 8.0,
        "judge_duration_seconds": 2.0,
        "judge_score": 0.85,
        "judge_passed": True,
        "judge_grade": "A",
        "judge_reasoning": "Good work",
        "judges": [
            {
                "model": "claude-opus-4-5-20251101",
                "score": 0.85,
                "passed": True,
                "grade": "A",
                "reasoning": "Good work",
                "judge_number": 1,
            }
        ],
        "workspace_path": "path/to/workspace",
        "logs_path": "path/to/logs",
        "command_log_path": "path/to/command_log.json",
        "criteria_scores": {},
    }
    (run_dir / "run_result.json").write_text(__import__("json").dumps(run_result))

    # Load run - should not raise any warnings
    run_data = load_run(
        run_dir=run_dir,
        experiment="test",
        tier="T0",
        subtest="00",
        agent_model="Sonnet 4.5",
    )

    # Verify data loaded correctly
    assert run_data.run_number == 1
    assert run_data.exit_code == 0
    assert run_data.score == 0.85
    assert run_data.passed is True


def test_schema_validation_invalid_grade(tmp_path, caplog):
    """Test that invalid grade triggers schema validation warning."""
    from scylla.analysis.loader import load_run

    # Create run directory with invalid grade
    run_dir = tmp_path / "run_01"
    run_dir.mkdir()

    # Create run_result.json with invalid grade (not S/A/B/C/D/F)
    run_result = {
        "run_number": 1,
        "exit_code": 0,
        "judge_grade": "X",  # Invalid grade
        "judge_passed": False,
    }
    (run_dir / "run_result.json").write_text(__import__("json").dumps(run_result))

    # Load run - should log warning but continue
    with caplog.at_level(__import__("logging").WARNING):
        run_data = load_run(
            run_dir=run_dir,
            experiment="test",
            tier="T0",
            subtest="00",
            agent_model="Sonnet 4.5",
        )

    # Verify warning was logged
    assert any("Schema validation failed" in record.message for record in caplog.records)

    # Verify data still loaded (graceful degradation)
    assert run_data.run_number == 1
    assert run_data.grade == "X"  # Data loaded despite validation failure


def test_schema_validation_missing_required_field(tmp_path, caplog):
    """Test that missing required field triggers schema validation warning."""
    from scylla.analysis.loader import load_run

    # Create run directory with missing run_number
    run_dir = tmp_path / "run_01"
    run_dir.mkdir()

    # Create run_result.json without required run_number
    run_result = {
        "exit_code": 0,
        "judge_passed": False,
    }
    (run_dir / "run_result.json").write_text(__import__("json").dumps(run_result))

    # Load run - should log warning but continue
    with caplog.at_level(__import__("logging").WARNING):
        run_data = load_run(
            run_dir=run_dir,
            experiment="test",
            tier="T0",
            subtest="00",
            agent_model="Sonnet 4.5",
        )

    # Verify warning was logged
    assert any("Schema validation failed" in record.message for record in caplog.records)

    # Verify data still loaded (graceful degradation)
    # run_number is parsed from directory name as fallback
    assert run_data.run_number == 1


def test_resolve_agent_model_from_experiment_json(tmp_path):
    """Test resolve_agent_model() reads from experiment.json first."""
    import json

    from scylla.analysis.loader import resolve_agent_model

    # Create experiment directory structure
    exp_dir = tmp_path / "test-experiment" / "2026-01-31T10-00-00-test"
    config_dir = exp_dir / "config"
    config_dir.mkdir(parents=True)

    # Create experiment.json with models list
    experiment_config = {
        "models": ["claude-sonnet-4-5-20250929", "claude-opus-4-5-20251101"],
        "other_config": "data",
    }
    (config_dir / "experiment.json").write_text(json.dumps(experiment_config))

    # Resolve agent model - should return first model as display name
    model = resolve_agent_model(exp_dir)
    assert model == "Sonnet 4.5"


def test_resolve_agent_model_from_model_md_fallback(tmp_path):
    """Test resolve_agent_model() falls back to MODEL.md if experiment.json missing."""
    from scylla.analysis.loader import resolve_agent_model

    # Create experiment directory without experiment.json
    exp_dir = tmp_path / "test-experiment" / "2026-01-31T10-00-00-test"
    tier_dir = exp_dir / "T0" / "00" / "run_01" / "agent"
    tier_dir.mkdir(parents=True)

    # Create MODEL.md
    (tier_dir / "MODEL.md").write_text("**Model**: claude-opus-4-5-20251101\n")

    # Resolve agent model - should find MODEL.md and return display name
    model = resolve_agent_model(exp_dir)
    assert model == "Opus 4.5"


def test_resolve_agent_model_raises_on_missing_data(tmp_path):
    """Test resolve_agent_model() raises ValueError when no model found."""
    from scylla.analysis.loader import resolve_agent_model

    # Create empty experiment directory
    exp_dir = tmp_path / "test-experiment" / "2026-01-31T10-00-00-test"
    exp_dir.mkdir(parents=True)

    # Should raise ValueError
    with pytest.raises(ValueError, match="Could not determine agent model"):
        resolve_agent_model(exp_dir)


def test_load_all_experiments_functionality(tmp_path):
    """Test load_all_experiments() loads multiple experiments from directory."""
    import json

    from scylla.analysis.loader import load_all_experiments

    # Create data directory with two experiments
    data_dir = tmp_path / "fullruns"
    data_dir.mkdir()

    # Experiment 1
    exp1_dir = data_dir / "experiment1" / "2026-01-31T10-00-00-run"
    config1_dir = exp1_dir / "config"
    config1_dir.mkdir(parents=True)
    experiment1_config = {"models": ["claude-sonnet-4-5-20250929"]}
    (config1_dir / "experiment.json").write_text(json.dumps(experiment1_config))

    # Create one run for experiment 1
    run1_dir = exp1_dir / "T0" / "00" / "run_01"
    run1_dir.mkdir(parents=True)
    run1_result = {
        "judge_score": 0.8,
        "judge_passed": True,
        "judge_grade": "A",
        "cost_usd": 0.05,
        "duration_seconds": 10.0,
        "token_stats": {},
        "exit_code": 0,
    }
    (run1_dir / "run_result.json").write_text(json.dumps(run1_result))

    # Experiment 2
    exp2_dir = data_dir / "experiment2" / "2026-01-31T11-00-00-run"
    config2_dir = exp2_dir / "config"
    config2_dir.mkdir(parents=True)
    experiment2_config = {"models": ["claude-haiku-4-5-20241223"]}
    (config2_dir / "experiment.json").write_text(json.dumps(experiment2_config))

    # Create one run for experiment 2
    run2_dir = exp2_dir / "T0" / "00" / "run_01"
    run2_dir.mkdir(parents=True)
    run2_result = {
        "judge_score": 0.6,
        "judge_passed": False,
        "judge_grade": "C",
        "cost_usd": 0.02,
        "duration_seconds": 8.0,
        "token_stats": {},
        "exit_code": 1,
    }
    (run2_dir / "run_result.json").write_text(json.dumps(run2_result))

    # Load all experiments
    experiments = load_all_experiments(data_dir)

    # Verify both experiments loaded
    assert len(experiments) == 2
    assert "experiment1" in experiments
    assert "experiment2" in experiments

    # Verify runs were loaded
    assert len(experiments["experiment1"]) == 1
    assert len(experiments["experiment2"]) == 1

    # Verify run data
    assert experiments["experiment1"][0].score == pytest.approx(0.8)
    assert experiments["experiment2"][0].score == pytest.approx(0.6)


def test_load_all_experiments_excludes_experiments(tmp_path):
    """Test load_all_experiments() excludes specified experiments."""
    import json

    from scylla.analysis.loader import load_all_experiments

    # Create data directory with two experiments
    data_dir = tmp_path / "fullruns"
    data_dir.mkdir()

    # Experiment 1 (will be excluded)
    exp1_dir = data_dir / "experiment1" / "2026-01-31T10-00-00-run"
    config1_dir = exp1_dir / "config"
    config1_dir.mkdir(parents=True)
    (config1_dir / "experiment.json").write_text(
        json.dumps({"models": ["claude-sonnet-4-5-20250929"]})
    )
    run1_dir = exp1_dir / "T0" / "00" / "run_01"
    run1_dir.mkdir(parents=True)
    (run1_dir / "run_result.json").write_text(
        json.dumps({"judge_score": 0.8, "judge_passed": True, "exit_code": 0})
    )

    # Experiment 2 (will be loaded)
    exp2_dir = data_dir / "experiment2" / "2026-01-31T11-00-00-run"
    config2_dir = exp2_dir / "config"
    config2_dir.mkdir(parents=True)
    (config2_dir / "experiment.json").write_text(
        json.dumps({"models": ["claude-haiku-4-5-20241223"]})
    )
    run2_dir = exp2_dir / "T0" / "00" / "run_01"
    run2_dir.mkdir(parents=True)
    (run2_dir / "run_result.json").write_text(
        json.dumps({"judge_score": 0.6, "judge_passed": False, "exit_code": 1})
    )

    # Load with exclusion
    experiments = load_all_experiments(data_dir, exclude=["experiment1"])

    # Verify only experiment2 loaded
    assert len(experiments) == 1
    assert "experiment1" not in experiments
    assert "experiment2" in experiments


def test_load_rubric_weights_from_rubric_yaml(tmp_path):
    """Test load_rubric_weights() parses category weights from rubric.yaml."""
    import yaml

    from scylla.analysis.loader import load_rubric_weights

    # Create experiment directory with rubric.yaml
    data_dir = tmp_path / "fullruns"
    exp_dir = data_dir / "experiment1" / "2026-01-31T10-00-00-run"
    exp_dir.mkdir(parents=True)

    # Create rubric.yaml with category weights
    rubric = {
        "categories": {
            "functional": {"weight": 10.0, "description": "Functional requirements"},
            "code_quality": {"weight": 5.0, "description": "Code quality"},
            "proportionality": {"weight": 3.0, "description": "Proportionality"},
        }
    }
    with (exp_dir / "rubric.yaml").open("w") as f:
        yaml.dump(rubric, f)

    # Load weights
    weights = load_rubric_weights(data_dir)

    # Verify weights loaded
    assert weights is not None
    assert weights["functional"] == pytest.approx(10.0)
    assert weights["code_quality"] == pytest.approx(5.0)
    assert weights["proportionality"] == pytest.approx(3.0)


def test_load_rubric_weights_returns_none_if_missing(tmp_path):
    """Test load_rubric_weights() returns None if no rubric.yaml found."""
    from scylla.analysis.loader import load_rubric_weights

    # Create empty data directory
    data_dir = tmp_path / "fullruns"
    data_dir.mkdir()

    # Load weights from empty directory
    weights = load_rubric_weights(data_dir)

    # Should return None
    assert weights is None


def test_load_rubric_weights_excludes_experiments(tmp_path):
    """Test load_rubric_weights() respects exclude list."""
    import yaml

    from scylla.analysis.loader import load_rubric_weights

    # Create two experiments
    data_dir = tmp_path / "fullruns"

    # Experiment 1 (will be excluded, has rubric)
    exp1_dir = data_dir / "experiment1" / "2026-01-31T10-00-00-run"
    exp1_dir.mkdir(parents=True)
    rubric1 = {"categories": {"functional": {"weight": 10.0}}}
    with (exp1_dir / "rubric.yaml").open("w") as f:
        yaml.dump(rubric1, f)

    # Experiment 2 (will be checked, has rubric)
    exp2_dir = data_dir / "experiment2" / "2026-01-31T11-00-00-run"
    exp2_dir.mkdir(parents=True)
    rubric2 = {"categories": {"code_quality": {"weight": 5.0}}}
    with (exp2_dir / "rubric.yaml").open("w") as f:
        yaml.dump(rubric2, f)

    # Load weights, excluding experiment1
    weights = load_rubric_weights(data_dir, exclude=["experiment1"])

    # Should load from experiment2 (first non-excluded)
    assert weights is not None
    assert "code_quality" in weights
    assert weights["code_quality"] == pytest.approx(5.0)
    assert "functional" not in weights
