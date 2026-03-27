"""Build/lint/test pipeline execution for E2E evaluation.

This module runs language-specific build, format, test, and pre-commit
pipelines against agent workspaces, producing structured BuildPipelineResult
objects consumed by the LLM judge.

Extracted from llm_judge.py to isolate pipeline execution concerns.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path

from scylla.e2e.llm_judge_models import BuildPipelineResult

logger = logging.getLogger(__name__)


def _is_modular_repo(workspace: Path) -> bool:
    """Check if workspace is the modular/mojo monorepo.

    The modular repo has a specific structure:
    - bazelw script at root
    - mojo/ subdirectory with its own pixi.toml

    Args:
        workspace: Path to the workspace directory

    Returns:
        True if this is the modular repo, False otherwise.

    """
    return (workspace / "bazelw").exists() and (workspace / "mojo").is_dir()


def _run_mojo_build_step(workspace: Path, is_modular: bool) -> tuple[bool, bool, str]:
    """Run the Mojo build step.

    Args:
        workspace: Path to the workspace directory
        is_modular: Whether workspace is the modular/mojo monorepo

    Returns:
        Tuple of (passed, na, output)

    """
    try:
        if is_modular:
            build_result = subprocess.run(
                ["./bazelw", "build", "//mojo/..."],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minutes for large monorepo
            )
        else:
            build_result = subprocess.run(
                ["pixi", "run", "mojo", "build", "."],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=300,
            )
        return (
            build_result.returncode == 0,
            False,
            build_result.stdout + "\n" + build_result.stderr,
        )
    except subprocess.TimeoutExpired as e:
        return (
            False,
            False,
            f"Build timed out after {e.args[1] if len(e.args) > 1 else 'unknown'} seconds",
        )
    except FileNotFoundError as e:
        return False, False, f"Build tool not found: {e}"


def _run_mojo_format_step(workspace: Path, is_modular: bool) -> tuple[bool, bool, str]:
    """Run the Mojo format check step.

    Args:
        workspace: Path to the workspace directory
        is_modular: Whether workspace is the modular/mojo monorepo

    Returns:
        Tuple of (passed, na, output)

    """
    try:
        if is_modular:
            format_result = subprocess.run(
                ["./bazelw", "run", "format"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=120,
            )
        else:
            # Run from mojo/ subdirectory if it exists, otherwise from workspace root
            mojo_dir = workspace / "mojo"
            cwd = mojo_dir if mojo_dir.is_dir() else workspace
            format_result = subprocess.run(
                ["pixi", "run", "mojo", "format", "."],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=120,
            )
        return (
            format_result.returncode == 0,
            False,
            format_result.stdout + "\n" + format_result.stderr,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, False, f"Error: {e}"


def _run_mojo_test_step(workspace: Path, is_modular: bool) -> tuple[bool, bool, str]:
    """Run the Mojo test step.

    Args:
        workspace: Path to the workspace directory
        is_modular: Whether workspace is the modular/mojo monorepo

    Returns:
        Tuple of (passed, na, output)

    """
    try:
        if is_modular:
            mojo_dir = workspace / "mojo"
            test_result = subprocess.run(
                ["pixi", "run", "tests"],
                cwd=mojo_dir,
                capture_output=True,
                text=True,
                timeout=600,
            )
        else:
            test_result = subprocess.run(
                ["pixi", "run", "mojo", "test"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=600,
            )
        output = test_result.stdout + "\n" + test_result.stderr
        if "No tests found" in output or test_result.returncode == 5:
            return True, True, output
        return test_result.returncode == 0, False, output
    except FileNotFoundError:
        return True, True, "mojo test not available, skipping"
    except subprocess.TimeoutExpired as e:
        return False, False, f"Error: {e}"


def _run_precommit_step(
    workspace: Path, env: dict[str, str] | None = None
) -> tuple[bool, bool, str]:
    """Run the pre-commit hooks step.

    Args:
        workspace: Path to the workspace directory
        env: Optional environment variables for subprocess (None uses inherited env)

    Returns:
        Tuple of (passed, na, output)

    """
    try:
        precommit_result = subprocess.run(
            ["pre-commit", "run", "--all-files"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
        output = precommit_result.stdout + "\n" + precommit_result.stderr
        if ".pre-commit-config.yaml is not a file" in output:
            return True, True, output
        return precommit_result.returncode == 0, False, output
    except FileNotFoundError:
        return True, True, "pre-commit not available, skipping"
    except subprocess.TimeoutExpired as e:
        return False, False, f"Error: {e}"


def _run_mojo_pipeline(workspace: Path) -> BuildPipelineResult:
    """Run Mojo build/lint pipeline and capture results.

    Detects if workspace is the modular/mojo monorepo and uses appropriate commands:
    - Modular repo: Uses bazelw for build, ./bazelw run format for format check,
      and pixi run tests from mojo/ subdirectory
    - Standalone repo: Uses pixi run mojo commands from workspace root

    Args:
        workspace: Path to the workspace directory

    Returns:
        BuildPipelineResult with all tool outputs

    """
    is_modular = _is_modular_repo(workspace)

    build_passed, build_na, build_output = _run_mojo_build_step(workspace, is_modular)
    format_passed, format_na, format_output = _run_mojo_format_step(workspace, is_modular)
    test_passed, test_na, test_output = _run_mojo_test_step(workspace, is_modular)
    precommit_passed, precommit_na, precommit_output = _run_precommit_step(workspace)

    return BuildPipelineResult(
        language="mojo",
        build_passed=build_passed,
        build_na=build_na,
        build_output=build_output,
        format_passed=format_passed,
        format_na=format_na,
        format_output=format_output,
        test_passed=test_passed,
        test_na=test_na,
        test_output=test_output,
        precommit_passed=precommit_passed,
        precommit_na=precommit_na,
        precommit_output=precommit_output,
        all_passed=all([build_passed, format_passed, test_passed, precommit_passed]),
    )


def _get_pipeline_env() -> dict[str, str]:
    """Get environment for pipeline subprocess calls with PYTHONPYCACHEPREFIX.

    Sets PYTHONPYCACHEPREFIX to redirect __pycache__ creation away from workspace,
    preventing unfair penalization for build artifacts created by the framework.

    Returns:
        Environment dict with PYTHONPYCACHEPREFIX set.

    """
    env = os.environ.copy()
    env["PYTHONPYCACHEPREFIX"] = str(Path(tempfile.gettempdir()) / "scylla_pycache")
    return env


def _execute_python_scripts(workspace: Path, env: dict[str, str]) -> list[str]:
    """Execute Python scripts found in the workspace root for functional verification.

    Args:
        workspace: Path to the workspace directory
        env: Environment variables for subprocess

    Returns:
        List of output lines from script execution

    """
    output_lines: list[str] = []
    try:
        py_files = list(workspace.glob("*.py"))
        if py_files:
            output_lines.append("\n## Script Execution Results\n")
            for py_file in sorted(py_files):
                output_lines.append(f"\n### Running: python {py_file.name}")
                try:
                    exec_result = subprocess.run(
                        ["python", py_file.name],
                        cwd=workspace,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        env=env,
                    )
                    output_lines.append(f"Exit code: {exec_result.returncode}")
                    if exec_result.stdout:
                        output_lines.append(f"Output:\n{exec_result.stdout[:500]}")
                    if exec_result.stderr:
                        output_lines.append(f"Stderr:\n{exec_result.stderr[:500]}")
                except subprocess.TimeoutExpired:
                    output_lines.append("Execution timed out (30s)")
                except (OSError, subprocess.SubprocessError) as e:
                    output_lines.append(f"Execution error: {e}")
    except OSError as e:
        logger.warning(f"Error finding Python scripts: {e}")
    return output_lines


def _run_python_build_step(workspace: Path, env: dict[str, str]) -> tuple[bool, bool, str]:
    """Run the Python syntax check and script execution step.

    Args:
        workspace: Path to the workspace directory
        env: Environment variables for subprocess

    Returns:
        Tuple of (passed, na, output)

    """
    try:
        build_result = subprocess.run(
            ["python", "-m", "compileall", "-q", "."],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
        build_passed = build_result.returncode == 0

        output_lines: list[str] = []
        if build_passed:
            output_lines.append("Python syntax check passed")
            output_lines.extend(_execute_python_scripts(workspace, env))

        build_output = (
            "\n".join(output_lines)
            if output_lines
            else (build_result.stdout + "\n" + build_result.stderr)
        )
        return build_passed, False, build_output
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, False, f"Error: {e}"


def _run_python_format_step(workspace: Path, env: dict[str, str]) -> tuple[bool, bool, str]:
    """Run the Python format check step using ruff.

    Args:
        workspace: Path to the workspace directory
        env: Environment variables for subprocess

    Returns:
        Tuple of (passed, na, output)

    """
    try:
        format_result = subprocess.run(
            ["ruff", "check", "."],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        return (
            format_result.returncode == 0,
            False,
            format_result.stdout + "\n" + format_result.stderr,
        )
    except FileNotFoundError:
        return True, True, "ruff not available, skipping format check"
    except subprocess.TimeoutExpired as e:
        return False, False, f"Error: {e}"


def _run_python_test_step(workspace: Path, env: dict[str, str]) -> tuple[bool, bool, str]:
    """Run the Python test step using pytest.

    Args:
        workspace: Path to the workspace directory
        env: Environment variables for subprocess

    Returns:
        Tuple of (passed, na, output)

    """
    try:
        test_result = subprocess.run(
            ["pytest", "-v"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=600,
            env=env,
        )
        output = test_result.stdout + "\n" + test_result.stderr
        # pytest exit code 5 means no tests collected
        if test_result.returncode == 5:
            return True, True, output
        return test_result.returncode == 0, False, output
    except FileNotFoundError:
        return True, True, "pytest not available, skipping"
    except subprocess.TimeoutExpired as e:
        return False, False, f"Error: {e}"


def _run_python_pipeline(workspace: Path) -> BuildPipelineResult:
    """Run Python build/lint pipeline and capture results.

    Args:
        workspace: Path to the workspace directory

    Returns:
        BuildPipelineResult with all tool outputs

    """
    pipeline_env = _get_pipeline_env()

    build_passed, build_na, build_output = _run_python_build_step(workspace, pipeline_env)
    format_passed, format_na, format_output = _run_python_format_step(workspace, pipeline_env)
    test_passed, test_na, test_output = _run_python_test_step(workspace, pipeline_env)
    precommit_passed, precommit_na, precommit_output = _run_precommit_step(
        workspace, env=pipeline_env
    )

    return BuildPipelineResult(
        language="python",
        build_passed=build_passed,
        build_na=build_na,
        build_output=build_output,
        format_passed=format_passed,
        format_na=format_na,
        format_output=format_output,
        test_passed=test_passed,
        test_na=test_na,
        test_output=test_output,
        precommit_passed=precommit_passed,
        precommit_na=precommit_na,
        precommit_output=precommit_output,
        all_passed=all([build_passed, format_passed, test_passed, precommit_passed]),
    )


def _run_build_pipeline(workspace: Path, language: str = "python") -> BuildPipelineResult:
    """Run build/lint pipeline and capture results.

    Routes to language-specific pipeline based on language parameter.

    Args:
        workspace: Path to the workspace directory
        language: Programming language ("python" or "mojo")

    Returns:
        BuildPipelineResult with all tool outputs

    """
    if language == "python":
        return _run_python_pipeline(workspace)
    else:
        return _run_mojo_pipeline(workspace)


def _run_and_log_pipeline(
    workspace: Path, language: str, judge_dir: Path | None
) -> BuildPipelineResult:
    """Run the build pipeline and log results."""
    from scylla.e2e.pipeline_scripts import _save_pipeline_outputs

    logger.info(f"Running {language} build/lint/test pipeline")
    result = _run_build_pipeline(workspace, language=language)

    status_summary = result.get_status_summary()
    failed_steps = result.get_failure_summary()
    if failed_steps == "none":
        if result.has_na_items():
            logger.warning(f"Build pipeline: ⚠️  {status_summary}")
        else:
            logger.info(f"Build pipeline: {status_summary}")
    else:
        logger.warning(f"Build pipeline: {status_summary}")

    if judge_dir:
        run_dir = judge_dir.parent if judge_dir.parent.name.startswith("run_") else judge_dir
        _save_pipeline_outputs(run_dir, result, language=language)

    return result


def _format_pipeline_result(result: BuildPipelineResult | None) -> str | None:
    """Format a pipeline result into a context string."""
    if not result:
        return None
    status = "ALL PASSED ✓" if result.all_passed else "SOME FAILED ✗"
    return f"**Overall Status**: {status}\n\n{result.to_context_string()}"
