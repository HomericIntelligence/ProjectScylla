"""Tests for judge rerun functionality."""

import json
from pathlib import Path

from scylla.e2e.rerun_judges import _is_valid_judgment, _regenerate_consensus


def test_is_valid_judgment_missing_file(tmp_path: Path) -> None:
    """Test _is_valid_judgment with missing file."""
    judgment_file = tmp_path / "judgment.json"
    assert not _is_valid_judgment(judgment_file)


def test_is_valid_judgment_with_score_and_valid_true(tmp_path: Path) -> None:
    """Test _is_valid_judgment with score and is_valid=True."""
    judgment_file = tmp_path / "judgment.json"
    judgment_file.write_text(
        json.dumps(
            {
                "score": 0.8,
                "passed": True,
                "grade": "B",
                "reasoning": "Good work",
                "is_valid": True,
            }
        )
    )
    assert _is_valid_judgment(judgment_file)


def test_is_valid_judgment_with_score_and_valid_false(tmp_path: Path) -> None:
    """Test _is_valid_judgment with score but is_valid=False."""
    judgment_file = tmp_path / "judgment.json"
    judgment_file.write_text(
        json.dumps(
            {
                "score": 0.0,
                "passed": False,
                "grade": "F",
                "reasoning": "Heuristic fallback",
                "is_valid": False,
            }
        )
    )
    assert not _is_valid_judgment(judgment_file)


def test_is_valid_judgment_backward_compat_no_is_valid_field(tmp_path: Path) -> None:
    """Test _is_valid_judgment with score but no is_valid field (backward compat)."""
    judgment_file = tmp_path / "judgment.json"
    judgment_file.write_text(
        json.dumps(
            {
                "score": 0.9,
                "passed": True,
                "grade": "A",
                "reasoning": "Excellent",
            }
        )
    )
    # Should return True when is_valid is missing (backward compatibility)
    assert _is_valid_judgment(judgment_file)


def test_is_valid_judgment_no_score(tmp_path: Path) -> None:
    """Test _is_valid_judgment with no score field."""
    judgment_file = tmp_path / "judgment.json"
    judgment_file.write_text(json.dumps({"reasoning": "No score"}))
    assert not _is_valid_judgment(judgment_file)


def test_is_valid_judgment_invalid_json(tmp_path: Path) -> None:
    """Test _is_valid_judgment with invalid JSON."""
    judgment_file = tmp_path / "judgment.json"
    judgment_file.write_text("not valid json {")
    assert not _is_valid_judgment(judgment_file)


def test_regenerate_consensus_all_valid_judges(tmp_path: Path) -> None:
    """Test _regenerate_consensus with all valid judges."""
    run_dir = tmp_path / "run_01"
    judge_dir = run_dir / "judge"

    # Create two valid judge results
    for i in range(1, 3):
        judge_subdir = judge_dir / f"judge_{i:02d}"
        judge_subdir.mkdir(parents=True)
        judgment_file = judge_subdir / "judgment.json"
        judgment_file.write_text(
            json.dumps(
                {
                    "score": 0.8 + (i * 0.05),
                    "passed": True,
                    "grade": "B",
                    "reasoning": f"Judge {i} reasoning",
                    "is_valid": True,
                    "criteria_scores": {"accuracy": {"score": 0.9, "explanation": "Good"}},
                }
            )
        )

    models = ["claude-sonnet-4-5", "claude-opus-4-6"]
    assert _regenerate_consensus(run_dir, models)

    # Check that consensus was written with is_valid=True
    result_file = judge_dir / "result.json"
    assert result_file.exists()
    consensus = json.loads(result_file.read_text())
    assert "score" in consensus
    assert consensus["is_valid"] is True
    assert consensus["criteria_scores"] is not None
    # Average of 0.85 and 0.9
    assert abs(consensus["score"] - 0.875) < 0.001


def test_regenerate_consensus_with_invalid_judge(tmp_path: Path) -> None:
    """Test _regenerate_consensus with one invalid judge (heuristic fallback)."""
    run_dir = tmp_path / "run_01"
    judge_dir = run_dir / "judge"

    # Judge 1: valid
    judge_1_dir = judge_dir / "judge_01"
    judge_1_dir.mkdir(parents=True)
    (judge_1_dir / "judgment.json").write_text(
        json.dumps(
            {
                "score": 0.9,
                "passed": True,
                "grade": "A",
                "reasoning": "Valid judgment",
                "is_valid": True,
                "criteria_scores": {"accuracy": {"score": 0.95, "explanation": "Great"}},
            }
        )
    )

    # Judge 2: invalid (heuristic fallback)
    judge_2_dir = judge_dir / "judge_02"
    judge_2_dir.mkdir(parents=True)
    (judge_2_dir / "judgment.json").write_text(
        json.dumps(
            {
                "score": 0.0,
                "passed": False,
                "grade": "F",
                "reasoning": "Heuristic fallback: agent crashed",
                "is_valid": False,
            }
        )
    )

    models = ["claude-sonnet-4-5", "claude-haiku-4-5"]
    assert _regenerate_consensus(run_dir, models)

    # Check consensus - should only use valid judge for score but mark consensus as invalid
    result_file = judge_dir / "result.json"
    consensus = json.loads(result_file.read_text())
    assert consensus["score"] == 0.9  # Only from valid judge
    assert consensus["is_valid"] is False  # One judge was invalid
    # Should use reasoning from closest judge (only valid judge with score 0.9)
    assert consensus["reasoning"] == "Valid judgment"
    assert consensus["criteria_scores"]["accuracy"]["score"] == 0.95


def test_regenerate_consensus_all_invalid_judges(tmp_path: Path) -> None:
    """Test _regenerate_consensus when all judges are invalid."""
    run_dir = tmp_path / "run_01"
    judge_dir = run_dir / "judge"

    # Both judges invalid
    for i in range(1, 3):
        judge_subdir = judge_dir / f"judge_{i:02d}"
        judge_subdir.mkdir(parents=True)
        (judge_subdir / "judgment.json").write_text(
            json.dumps(
                {
                    "score": 0.0,
                    "passed": False,
                    "grade": "F",
                    "reasoning": f"Heuristic fallback {i}",
                    "is_valid": False,
                }
            )
        )

    models = ["claude-haiku-4-5", "claude-haiku-4-5"]
    # Should return False when all judges are invalid
    assert not _regenerate_consensus(run_dir, models)


def test_regenerate_consensus_no_judges(tmp_path: Path) -> None:
    """Test _regenerate_consensus with no judge results."""
    run_dir = tmp_path / "run_01"
    run_dir.mkdir()

    models = ["claude-sonnet-4-5"]
    assert not _regenerate_consensus(run_dir, models)


def test_regenerate_consensus_backward_compat_no_is_valid(tmp_path: Path) -> None:
    """Test _regenerate_consensus with old judgments missing is_valid field."""
    run_dir = tmp_path / "run_01"
    judge_dir = run_dir / "judge"

    # Create judge result without is_valid field (old format)
    judge_subdir = judge_dir / "judge_01"
    judge_subdir.mkdir(parents=True)
    (judge_subdir / "judgment.json").write_text(
        json.dumps(
            {
                "score": 0.75,
                "passed": True,
                "grade": "C",
                "reasoning": "Old format judgment",
            }
        )
    )

    models = ["claude-sonnet-4-5"]
    assert _regenerate_consensus(run_dir, models)

    # Should treat missing is_valid as True
    result_file = judge_dir / "result.json"
    consensus = json.loads(result_file.read_text())
    assert consensus["score"] == 0.75
    assert consensus["is_valid"] is True  # Defaults to True


def test_is_valid_judgment_with_fallback_true(tmp_path: Path) -> None:
    """Test _is_valid_judgment rejects old fallback judgments with fallback=true."""
    judgment_file = tmp_path / "judgment.json"
    judgment_file.write_text(
        json.dumps(
            {
                "score": 0.70,
                "passed": True,
                "grade": "C",
                "reasoning": "Rate limit fallback",
                "is_valid": True,
                "fallback": True,
            }
        )
    )
    # Should reject even though is_valid=True
    assert not _is_valid_judgment(judgment_file)


def test_is_valid_judgment_with_fallback_false(tmp_path: Path) -> None:
    """Test _is_valid_judgment accepts judgments with fallback=false."""
    judgment_file = tmp_path / "judgment.json"
    judgment_file.write_text(
        json.dumps(
            {
                "score": 0.85,
                "passed": True,
                "grade": "B",
                "reasoning": "Valid judgment",
                "is_valid": True,
                "fallback": False,
            }
        )
    )
    # Should accept since fallback=false
    assert _is_valid_judgment(judgment_file)


def test_regenerate_consensus_rejects_fallback_judgments(tmp_path: Path) -> None:
    """Test _regenerate_consensus only uses non-fallback judges for scoring."""
    run_dir = tmp_path / "run_01"
    judge_dir = run_dir / "judge"

    # Judge 1: valid, non-fallback
    judge_1_dir = judge_dir / "judge_01"
    judge_1_dir.mkdir(parents=True)
    (judge_1_dir / "judgment.json").write_text(
        json.dumps(
            {
                "score": 0.9,
                "passed": True,
                "grade": "A",
                "reasoning": "Valid judgment",
                "is_valid": True,
                "fallback": False,
            }
        )
    )

    # Judge 2: fallback (should be excluded)
    judge_2_dir = judge_dir / "judge_02"
    judge_2_dir.mkdir(parents=True)
    (judge_2_dir / "judgment.json").write_text(
        json.dumps(
            {
                "score": 0.70,
                "passed": True,
                "grade": "C",
                "reasoning": "Rate limit fallback",
                "is_valid": True,
                "fallback": True,
            }
        )
    )

    models = ["claude-opus-4-6", "claude-sonnet-4-5"]
    assert _regenerate_consensus(run_dir, models)

    # Check consensus - should only use non-fallback judge
    result_file = judge_dir / "result.json"
    consensus = json.loads(result_file.read_text())
    assert consensus["score"] == 0.9  # Only from judge 1
    assert consensus["is_valid"] is False  # One judge was invalid (fallback)


def test_regenerate_consensus_all_fallback_judges(tmp_path: Path) -> None:
    """Test _regenerate_consensus returns False when all judges are fallback."""
    run_dir = tmp_path / "run_01"
    judge_dir = run_dir / "judge"

    # Both judges are fallback
    for i in range(1, 3):
        judge_subdir = judge_dir / f"judge_{i:02d}"
        judge_subdir.mkdir(parents=True)
        (judge_subdir / "judgment.json").write_text(
            json.dumps(
                {
                    "score": 0.70,
                    "passed": True,
                    "grade": "C",
                    "reasoning": f"Rate limit fallback {i}",
                    "is_valid": True,
                    "fallback": True,
                }
            )
        )

    models = ["claude-sonnet-4-5", "claude-haiku-4-5"]
    # Should return False when all judges are fallback
    assert not _regenerate_consensus(run_dir, models)


def test_regenerate_consensus_representative_reasoning(tmp_path: Path) -> None:
    """Test _regenerate_consensus picks reasoning from judge closest to consensus."""
    run_dir = tmp_path / "run_01"
    judge_dir = run_dir / "judge"

    # Judge 1: score=0.5
    judge_1_dir = judge_dir / "judge_01"
    judge_1_dir.mkdir(parents=True)
    (judge_1_dir / "judgment.json").write_text(
        json.dumps(
            {
                "score": 0.5,
                "passed": False,
                "grade": "F",
                "reasoning": "Agent failed completely",
                "is_valid": True,
            }
        )
    )

    # Judge 2: score=0.85 (closest to consensus of 0.675)
    judge_2_dir = judge_dir / "judge_02"
    judge_2_dir.mkdir(parents=True)
    (judge_2_dir / "judgment.json").write_text(
        json.dumps(
            {
                "score": 0.85,
                "passed": True,
                "grade": "B",
                "reasoning": "Agent mostly succeeded",
                "is_valid": True,
                "criteria_scores": {"accuracy": {"score": 0.9, "explanation": "Good"}},
            }
        )
    )

    models = ["claude-sonnet-4-5", "claude-opus-4-6"]
    assert _regenerate_consensus(run_dir, models)

    # Check consensus - should use judge 2's reasoning (closer to 0.675 consensus)
    result_file = judge_dir / "result.json"
    consensus = json.loads(result_file.read_text())
    assert abs(consensus["score"] - 0.675) < 0.001  # Average of 0.5 and 0.85
    assert consensus["reasoning"] == "Agent mostly succeeded"
    assert consensus["criteria_scores"]["accuracy"]["score"] == 0.9
