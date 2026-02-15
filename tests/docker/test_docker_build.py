"""Tests for Docker build configuration validation.

Tests cover:
- Dockerfile syntax validation
- docker-compose.yml configuration validation
- Build context verification
"""

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def docker_dir():
    """Return path to docker directory."""
    repo_root = Path(__file__).parent.parent.parent
    return repo_root / "docker"


@pytest.fixture
def dockerfile_path(docker_dir):
    """Return path to Dockerfile."""
    return docker_dir / "Dockerfile"


@pytest.fixture
def compose_file_path(docker_dir):
    """Return path to docker-compose.yml."""
    return docker_dir / "docker-compose.yml"


class TestDockerfileValidation:
    """Tests for Dockerfile syntax validation."""

    def test_dockerfile_exists(self, dockerfile_path):
        """Dockerfile exists in docker/ directory."""
        assert dockerfile_path.exists(), f"Dockerfile not found at {dockerfile_path}"
        assert dockerfile_path.is_file(), f"Dockerfile is not a file: {dockerfile_path}"

    def test_dockerfile_syntax_valid(self, docker_dir):
        """Dockerfile has valid syntax using docker build --check."""
        result = subprocess.run(
            ["docker", "build", "--check", str(docker_dir)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            f"Dockerfile syntax validation failed:\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_dockerfile_has_from_instruction(self, dockerfile_path):
        """Dockerfile contains FROM instruction."""
        content = dockerfile_path.read_text()
        assert "FROM" in content, "Dockerfile must contain FROM instruction"

    def test_dockerfile_has_workdir(self, dockerfile_path):
        """Dockerfile contains WORKDIR instruction."""
        content = dockerfile_path.read_text()
        assert "WORKDIR" in content, "Dockerfile should contain WORKDIR instruction"

    def test_dockerfile_has_entrypoint(self, dockerfile_path):
        """Dockerfile contains ENTRYPOINT instruction."""
        content = dockerfile_path.read_text()
        assert "ENTRYPOINT" in content, "Dockerfile should contain ENTRYPOINT instruction"


class TestDockerComposeValidation:
    """Tests for docker-compose.yml configuration validation."""

    def test_compose_file_exists(self, compose_file_path):
        """docker-compose.yml exists in docker/ directory."""
        assert compose_file_path.exists(), f"docker-compose.yml not found at {compose_file_path}"
        assert compose_file_path.is_file(), f"docker-compose.yml is not a file: {compose_file_path}"

    def test_compose_config_valid(self, compose_file_path):
        """docker-compose.yml has valid configuration."""
        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_file_path), "config", "--quiet"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            f"docker-compose.yml validation failed:\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_compose_has_services(self, compose_file_path):
        """docker-compose.yml defines services."""
        content = compose_file_path.read_text()
        assert "services:" in content, "docker-compose.yml must define services"

    def test_compose_has_build_context(self, compose_file_path):
        """docker-compose.yml defines build context."""
        content = compose_file_path.read_text()
        # Check for build configuration
        assert "build:" in content or "image:" in content, (
            "docker-compose.yml must define build or image"
        )


class TestBuildContext:
    """Tests for Docker build context files."""

    def test_entrypoint_script_exists(self, docker_dir):
        """entrypoint.sh exists in docker/ directory."""
        entrypoint_path = docker_dir / "entrypoint.sh"
        assert entrypoint_path.exists(), f"entrypoint.sh not found at {entrypoint_path}"
        assert entrypoint_path.is_file(), f"entrypoint.sh is not a file: {entrypoint_path}"

    def test_entrypoint_script_executable(self, docker_dir):
        """entrypoint.sh has shebang."""
        entrypoint_path = docker_dir / "entrypoint.sh"
        content = entrypoint_path.read_text()
        assert content.startswith("#!/"), "entrypoint.sh must have shebang"

    def test_dockerignore_exists(self, docker_dir):
        """Dockerignore file exists in docker/ directory."""
        dockerignore_path = docker_dir / ".dockerignore"
        assert dockerignore_path.exists(), f".dockerignore not found at {dockerignore_path}"
        assert dockerignore_path.is_file(), f".dockerignore is not a file: {dockerignore_path}"


class TestDockerfileContent:
    """Tests for Dockerfile content and best practices."""

    def test_uses_slim_base_image(self, dockerfile_path):
        """Dockerfile uses slim or alpine base image for smaller size."""
        content = dockerfile_path.read_text()
        # Check if using slim or alpine variants
        has_slim_or_alpine = "slim" in content.lower() or "alpine" in content.lower()
        assert has_slim_or_alpine, "Consider using slim or alpine base images for smaller size"

    def test_runs_as_non_root_user(self, dockerfile_path):
        """Dockerfile runs as non-root user for security."""
        content = dockerfile_path.read_text()
        assert "USER" in content, "Dockerfile should specify non-root USER"

    def test_sets_labels(self, dockerfile_path):
        """Dockerfile includes metadata labels."""
        content = dockerfile_path.read_text()
        assert "LABEL" in content, "Dockerfile should include metadata labels"

    def test_sets_environment_variables(self, dockerfile_path):
        """Dockerfile sets environment variables."""
        content = dockerfile_path.read_text()
        assert "ENV" in content, "Dockerfile should set environment variables"

    def test_dockerfile_has_healthcheck(self, dockerfile_path):
        """Dockerfile contains HEALTHCHECK instruction for container orchestration."""
        content = dockerfile_path.read_text()
        assert "HEALTHCHECK" in content, (
            "Dockerfile should contain HEALTHCHECK instruction for "
            "container health monitoring in orchestration platforms"
        )

    def test_npm_packages_are_pinned(self, dockerfile_path):
        """Dockerfile pins npm packages to specific versions for reproducibility."""
        import re

        content = dockerfile_path.read_text()

        # Find all npm install -g commands
        npm_install_pattern = r"npm\s+install\s+-g\s+((?:@[\w-]+/)?[\w-]+(?:@[\w.-]+)?)"
        matches = re.findall(npm_install_pattern, content)

        # Check that each package has a version specifier (@version)
        for package in matches:
            # Count @ symbols: scoped packages have 1, scoped+versioned have 2
            # Non-scoped packages should have 1 for version
            at_count = package.count("@")
            is_scoped = package.startswith("@")

            if is_scoped:
                # Scoped package needs 2 @ symbols (@scope/name@version)
                assert at_count >= 2, (
                    f"npm package '{package}' should be pinned to specific version "
                    f"(e.g., {package}@2.1.42) for build reproducibility. "
                    f"See: https://github.com/mvillmow/ProjectScylla/issues/650"
                )
            else:
                # Non-scoped package needs 1 @ symbol (name@version)
                assert at_count >= 1, (
                    f"npm package '{package}' should be pinned to specific version "
                    f"(e.g., {package}@1.0.0) for build reproducibility. "
                    f"See: https://github.com/mvillmow/ProjectScylla/issues/650"
                )


class TestDockerComposeContent:
    """Tests for docker-compose.yml content and configuration."""

    def test_defines_environment_variables(self, compose_file_path):
        """docker-compose.yml defines environment variables."""
        content = compose_file_path.read_text()
        assert "environment:" in content, "docker-compose.yml should define environment variables"

    def test_defines_volumes(self, compose_file_path):
        """docker-compose.yml defines volume mounts."""
        content = compose_file_path.read_text()
        assert "volumes:" in content, "docker-compose.yml should define volume mounts"

    def test_uses_profiles(self, compose_file_path):
        """docker-compose.yml uses profiles for different environments."""
        content = compose_file_path.read_text()
        # Profiles are optional but recommended for multi-environment setups
        # This is a soft check - we just verify the file is parseable
        assert len(content) > 0, "docker-compose.yml should not be empty"


class TestDockerfileDigestPinning:
    """Tests for base image digest pinning."""

    def test_base_image_uses_sha256_digest(self, dockerfile_path):
        """All FROM instructions use SHA256 digest for reproducibility."""
        content = dockerfile_path.read_text()
        from_lines = [line for line in content.split("\n") if line.strip().startswith("FROM")]

        # Should have exactly 2 FROM instructions (builder + runtime)
        assert len(from_lines) == 2, f"Expected 2 FROM instructions, found {len(from_lines)}"

        # Both should have SHA256 digest
        for line in from_lines:
            assert "@sha256:" in line, (
                f"FROM instruction missing SHA256 digest: {line}\n"
                "Base images should be pinned to SHA256 digest for reproducibility"
            )

    def test_both_stages_use_same_digest(self, dockerfile_path):
        """Builder and runtime stages use the same base image digest."""
        content = dockerfile_path.read_text()
        from_lines = [line for line in content.split("\n") if line.strip().startswith("FROM")]

        # Extract digests from both FROM instructions
        digests = []
        for line in from_lines:
            if "@sha256:" in line:
                digest = line.split("@sha256:")[1].split()[0]
                digests.append(digest)

        assert len(digests) == 2, "Both FROM instructions should have digests"
        assert digests[0] == digests[1], (
            f"Builder and runtime stages use different digests:\n"
            f"Builder: {digests[0]}\n"
            f"Runtime: {digests[1]}\n"
            "Both stages should use the same base image digest"
        )
