"""Tests for scylla.e2e.repo_detection module."""

from pathlib import Path

from scylla.e2e.repo_detection import (
    is_gradle_repo,
    is_maven_repo,
    is_modular_repo,
    is_npm_repo,
    is_poetry_repo,
)


class TestIsModularRepo:
    """Tests for is_modular_repo function."""

    def test_modular_repo_detected(self, tmp_path: Path) -> None:
        """Test detection of modular/mojo monorepo."""
        # Create bazelw and mojo/ directory
        (tmp_path / "bazelw").touch()
        (tmp_path / "mojo").mkdir()

        assert is_modular_repo(tmp_path) is True

    def test_non_modular_repo(self, tmp_path: Path) -> None:
        """Test detection of non-modular repo."""
        assert is_modular_repo(tmp_path) is False

    def test_missing_bazelw(self, tmp_path: Path) -> None:
        """Test repo with mojo/ but no bazelw."""
        (tmp_path / "mojo").mkdir()

        assert is_modular_repo(tmp_path) is False

    def test_missing_mojo_dir(self, tmp_path: Path) -> None:
        """Test repo with bazelw but no mojo/."""
        (tmp_path / "bazelw").touch()

        assert is_modular_repo(tmp_path) is False


class TestIsMavenRepo:
    """Tests for is_maven_repo function."""

    def test_maven_repo_detected(self, tmp_path: Path) -> None:
        """Test detection of Maven project with pom.xml."""
        (tmp_path / "pom.xml").touch()

        assert is_maven_repo(tmp_path) is True

    def test_non_maven_repo(self, tmp_path: Path) -> None:
        """Test non-Maven repo without pom.xml."""
        assert is_maven_repo(tmp_path) is False


class TestIsGradleRepo:
    """Tests for is_gradle_repo function."""

    def test_gradle_groovy_detected(self, tmp_path: Path) -> None:
        """Test detection of Gradle project with build.gradle."""
        (tmp_path / "build.gradle").touch()

        assert is_gradle_repo(tmp_path) is True

    def test_gradle_kotlin_detected(self, tmp_path: Path) -> None:
        """Test detection of Gradle project with build.gradle.kts."""
        (tmp_path / "build.gradle.kts").touch()

        assert is_gradle_repo(tmp_path) is True

    def test_non_gradle_repo(self, tmp_path: Path) -> None:
        """Test non-Gradle repo without build files."""
        assert is_gradle_repo(tmp_path) is False


class TestIsNpmRepo:
    """Tests for is_npm_repo function."""

    def test_npm_repo_detected(self, tmp_path: Path) -> None:
        """Test detection of npm project with package.json."""
        (tmp_path / "package.json").touch()

        assert is_npm_repo(tmp_path) is True

    def test_non_npm_repo(self, tmp_path: Path) -> None:
        """Test non-npm repo without package.json."""
        assert is_npm_repo(tmp_path) is False


class TestIsPoetryRepo:
    """Tests for is_poetry_repo function."""

    def test_poetry_repo_detected(self, tmp_path: Path) -> None:
        """Test detection of Poetry project with pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.poetry]\nname = 'test'\n")

        assert is_poetry_repo(tmp_path) is True

    def test_non_poetry_repo_no_file(self, tmp_path: Path) -> None:
        """Test non-Poetry repo without pyproject.toml."""
        assert is_poetry_repo(tmp_path) is False

    def test_non_poetry_repo_wrong_content(self, tmp_path: Path) -> None:
        """Test pyproject.toml without [tool.poetry] section."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[build-system]\nrequires = ['setuptools']\n")

        assert is_poetry_repo(tmp_path) is False
