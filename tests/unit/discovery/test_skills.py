"""Tests for scylla.discovery.skills module."""

from pathlib import Path

import pytest

from scylla.discovery.skills import (
    CATEGORY_MAPPINGS,
    discover_skills,
    get_skill_category,
    organize_skills,
)


@pytest.fixture
def mock_skill_dirs(tmp_path: Path) -> Path:
    """Create mock skill directories and files."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    # GitHub skills
    (skills_dir / "gh-review-pr").mkdir()
    (skills_dir / "gh-review-pr" / "skill.md").write_text("# Review PR skill")

    (skills_dir / "gh-create-pr-linked").mkdir()
    (skills_dir / "gh-create-pr-linked" / "skill.md").write_text("# Create PR skill")

    # Mojo skills
    (skills_dir / "mojo-format").mkdir()
    (skills_dir / "mojo-format" / "skill.md").write_text("# Format Mojo code")

    (skills_dir / "mojo-test-runner").mkdir()
    (skills_dir / "mojo-test-runner" / "skill.md").write_text("# Run Mojo tests")

    # Workflow skills
    (skills_dir / "phase-plan-generate").mkdir()
    (skills_dir / "phase-plan-generate" / "skill.md").write_text("# Generate plan")

    # Quality skills
    (skills_dir / "quality-run-linters").mkdir()
    (skills_dir / "quality-run-linters" / "skill.md").write_text("# Run linters")

    # Agent skills
    (skills_dir / "agent-run-orchestrator").mkdir()
    (skills_dir / "agent-run-orchestrator" / "skill.md").write_text("# Run orchestrator")

    # Documentation skills
    (skills_dir / "doc-generate-adr").mkdir()
    (skills_dir / "doc-generate-adr" / "skill.md").write_text("# Generate ADR")

    # CICD skills
    (skills_dir / "run-precommit").mkdir()
    (skills_dir / "run-precommit" / "skill.md").write_text("# Run pre-commit")

    # Worktree skills
    (skills_dir / "worktree-create").mkdir()
    (skills_dir / "worktree-create" / "skill.md").write_text("# Create worktree")

    # Other skills (no category prefix)
    (skills_dir / "custom-skill").mkdir()
    (skills_dir / "custom-skill" / "skill.md").write_text("# Custom skill")

    # Skill file (not directory)
    (skills_dir / "standalone-skill.md").write_text("# Standalone skill")

    # Template file (should be ignored)
    (skills_dir / "TEMPLATE-skill.md").write_text("# Template")

    # Hidden directory (should be ignored)
    (skills_dir / ".hidden").mkdir()

    return skills_dir


@pytest.fixture
def empty_skills_dir(tmp_path: Path) -> Path:
    """Create empty skills directory."""
    skills_dir = tmp_path / "empty_skills"
    skills_dir.mkdir()
    return skills_dir


class TestGetSkillCategory:
    """Tests for get_skill_category function."""

    def test_github_explicit_mapping(self) -> None:
        """Test explicit GitHub skill mapping."""
        assert get_skill_category("gh-review-pr") == "github"
        assert get_skill_category("gh-create-pr-linked") == "github"
        assert get_skill_category("gh-implement-issue") == "github"

    def test_mojo_explicit_mapping(self) -> None:
        """Test explicit Mojo skill mapping."""
        assert get_skill_category("mojo-format") == "mojo"
        assert get_skill_category("mojo-test-runner") == "mojo"
        assert get_skill_category("validate-mojo-patterns") == "mojo"

    def test_workflow_explicit_mapping(self) -> None:
        """Test explicit workflow skill mapping."""
        assert get_skill_category("phase-plan-generate") == "workflow"
        assert get_skill_category("phase-implement") == "workflow"

    def test_quality_explicit_mapping(self) -> None:
        """Test explicit quality skill mapping."""
        assert get_skill_category("quality-run-linters") == "quality"
        assert get_skill_category("quality-coverage-report") == "quality"

    def test_worktree_explicit_mapping(self) -> None:
        """Test explicit worktree skill mapping."""
        assert get_skill_category("worktree-create") == "worktree"
        assert get_skill_category("worktree-cleanup") == "worktree"

    def test_documentation_explicit_mapping(self) -> None:
        """Test explicit documentation skill mapping."""
        assert get_skill_category("doc-generate-adr") == "documentation"
        assert get_skill_category("doc-validate-markdown") == "documentation"

    def test_agent_explicit_mapping(self) -> None:
        """Test explicit agent skill mapping."""
        assert get_skill_category("agent-run-orchestrator") == "agent"
        assert get_skill_category("agent-validate-config") == "agent"

    def test_cicd_explicit_mapping(self) -> None:
        """Test explicit CICD skill mapping."""
        assert get_skill_category("run-precommit") == "cicd"
        assert get_skill_category("verify-pr-ready") == "cicd"

    def test_github_prefix_fallback(self) -> None:
        """Test GitHub prefix fallback for unmapped skills."""
        assert get_skill_category("gh-new-skill") == "github"
        assert get_skill_category("gh-custom") == "github"

    def test_mojo_prefix_fallback(self) -> None:
        """Test Mojo prefix fallback for unmapped skills."""
        assert get_skill_category("mojo-new-feature") == "mojo"

    def test_phase_prefix_fallback(self) -> None:
        """Test phase prefix fallback for unmapped skills."""
        assert get_skill_category("phase-custom") == "workflow"

    def test_quality_prefix_fallback(self) -> None:
        """Test quality prefix fallback for unmapped skills."""
        assert get_skill_category("quality-new-check") == "quality"

    def test_worktree_prefix_fallback(self) -> None:
        """Test worktree prefix fallback for unmapped skills."""
        assert get_skill_category("worktree-new-operation") == "worktree"

    def test_doc_prefix_fallback(self) -> None:
        """Test doc prefix fallback for unmapped skills."""
        assert get_skill_category("doc-new-generator") == "documentation"

    def test_agent_prefix_fallback(self) -> None:
        """Test agent prefix fallback for unmapped skills."""
        assert get_skill_category("agent-new-tool") == "agent"

    def test_other_category(self) -> None:
        """Test skills without recognized prefix map to 'other'."""
        assert get_skill_category("custom-skill") == "other"
        assert get_skill_category("unknown") == "other"
        assert get_skill_category("random-name") == "other"


class TestDiscoverSkills:
    """Tests for discover_skills function."""

    def test_discover_all_categories(self, mock_skill_dirs: Path) -> None:
        """Discover skills across all categories."""
        skills_by_category = discover_skills(mock_skill_dirs)

        # Check structure includes all categories
        expected_categories = list(CATEGORY_MAPPINGS.keys()) + ["other"]
        assert all(cat in skills_by_category for cat in expected_categories)

    def test_discover_github_skills(self, mock_skill_dirs: Path) -> None:
        """Discover GitHub skills."""
        skills_by_category = discover_skills(mock_skill_dirs)

        github_skills = skills_by_category["github"]
        assert len(github_skills) == 2

        names = {skill.name for skill in github_skills}
        assert "gh-review-pr" in names
        assert "gh-create-pr-linked" in names

    def test_discover_mojo_skills(self, mock_skill_dirs: Path) -> None:
        """Discover Mojo skills."""
        skills_by_category = discover_skills(mock_skill_dirs)

        mojo_skills = skills_by_category["mojo"]
        assert len(mojo_skills) == 2

        names = {skill.name for skill in mojo_skills}
        assert "mojo-format" in names
        assert "mojo-test-runner" in names

    def test_discover_workflow_skills(self, mock_skill_dirs: Path) -> None:
        """Discover workflow skills."""
        skills_by_category = discover_skills(mock_skill_dirs)

        workflow_skills = skills_by_category["workflow"]
        assert len(workflow_skills) == 1
        assert workflow_skills[0].name == "phase-plan-generate"

    def test_discover_other_category(self, mock_skill_dirs: Path) -> None:
        """Discover skills in 'other' category."""
        skills_by_category = discover_skills(mock_skill_dirs)

        other_skills = skills_by_category["other"]
        # custom-skill and standalone-skill
        assert len(other_skills) == 2

        names = {skill.name if skill.is_dir() else skill.stem for skill in other_skills}
        assert "custom-skill" in names
        assert "standalone-skill" in names

    def test_discover_ignores_templates(self, mock_skill_dirs: Path) -> None:
        """Discover skills ignores template files."""
        skills_by_category = discover_skills(mock_skill_dirs)

        all_skills = [skill for skills in skills_by_category.values() for skill in skills]
        all_names = {skill.name if skill.is_dir() else skill.stem for skill in all_skills}

        assert "TEMPLATE-skill" not in all_names

    def test_discover_ignores_hidden_dirs(self, mock_skill_dirs: Path) -> None:
        """Discover skills ignores hidden directories."""
        skills_by_category = discover_skills(mock_skill_dirs)

        all_skills = [skill for skills in skills_by_category.values() for skill in skills]
        all_names = {skill.name for skill in all_skills}

        assert ".hidden" not in all_names

    def test_discover_empty_directory(self, empty_skills_dir: Path) -> None:
        """Discover skills in empty directory."""
        skills_by_category = discover_skills(empty_skills_dir)

        # Should return empty lists for all categories
        expected_categories = list(CATEGORY_MAPPINGS.keys()) + ["other"]
        assert all(cat in skills_by_category for cat in expected_categories)
        assert all(len(skills_by_category[cat]) == 0 for cat in expected_categories)

    def test_discover_skill_files(self, mock_skill_dirs: Path) -> None:
        """Discover standalone skill files."""
        skills_by_category = discover_skills(mock_skill_dirs)

        # standalone-skill.md should be discovered
        other_skills = skills_by_category["other"]
        file_skills = [skill for skill in other_skills if skill.is_file()]
        assert len(file_skills) == 1
        assert file_skills[0].stem == "standalone-skill"

    def test_discover_mixed_dirs_and_files(self, tmp_path: Path) -> None:
        """Discover mix of skill directories and files."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create a directory skill
        (skills_dir / "gh-skill-dir").mkdir()
        # Create a file skill
        (skills_dir / "gh-skill-file.md").write_text("# File skill")

        skills_by_category = discover_skills(skills_dir)
        github_skills = skills_by_category["github"]

        assert len(github_skills) == 2
        names = {skill.name if skill.is_dir() else skill.stem for skill in github_skills}
        assert "gh-skill-dir" in names
        assert "gh-skill-file" in names


class TestOrganizeSkills:
    """Tests for organize_skills function."""

    def test_organize_creates_directories(self, mock_skill_dirs: Path, tmp_path: Path) -> None:
        """Organize skills creates category subdirectories."""
        dest_dir = tmp_path / "organized"

        organize_skills(mock_skill_dirs, dest_dir)

        # Check category directories exist
        expected_categories = list(CATEGORY_MAPPINGS.keys()) + ["other"]
        for category in expected_categories:
            category_dir = dest_dir / category
            assert category_dir.exists()
            assert category_dir.is_dir()

    def test_organize_copies_directories(self, mock_skill_dirs: Path, tmp_path: Path) -> None:
        """Organize skills copies skill directories."""
        dest_dir = tmp_path / "organized"

        stats = organize_skills(mock_skill_dirs, dest_dir)

        # Check GitHub skills
        assert "gh-review-pr" in stats["github"]
        assert (dest_dir / "github" / "gh-review-pr").exists()
        assert (dest_dir / "github" / "gh-review-pr" / "skill.md").exists()

    def test_organize_copies_files(self, mock_skill_dirs: Path, tmp_path: Path) -> None:
        """Organize skills copies skill files."""
        dest_dir = tmp_path / "organized"

        stats = organize_skills(mock_skill_dirs, dest_dir)

        # Check standalone skill file
        assert "standalone-skill" in stats["other"]
        assert (dest_dir / "other" / "standalone-skill.md").exists()

    def test_organize_preserves_content(self, mock_skill_dirs: Path, tmp_path: Path) -> None:
        """Organize skills preserves file content."""
        dest_dir = tmp_path / "organized"

        organize_skills(mock_skill_dirs, dest_dir)

        # Read original and copied file
        original = (mock_skill_dirs / "gh-review-pr" / "skill.md").read_text()
        copied = (dest_dir / "github" / "gh-review-pr" / "skill.md").read_text()

        assert original == copied

    def test_organize_returns_stats(self, mock_skill_dirs: Path, tmp_path: Path) -> None:
        """Organize skills returns correct statistics."""
        dest_dir = tmp_path / "organized"

        stats = organize_skills(mock_skill_dirs, dest_dir)

        # Check structure
        expected_categories = list(CATEGORY_MAPPINGS.keys()) + ["other"]
        assert all(cat in stats for cat in expected_categories)

        # Check GitHub stats
        assert len(stats["github"]) == 2
        assert "gh-review-pr" in stats["github"]
        assert "gh-create-pr-linked" in stats["github"]

        # Check Mojo stats
        assert len(stats["mojo"]) == 2
        assert "mojo-format" in stats["mojo"]
        assert "mojo-test-runner" in stats["mojo"]

    def test_organize_empty_directory(self, empty_skills_dir: Path, tmp_path: Path) -> None:
        """Organize empty skills directory."""
        dest_dir = tmp_path / "organized"

        stats = organize_skills(empty_skills_dir, dest_dir)

        # Directories should be created
        expected_categories = list(CATEGORY_MAPPINGS.keys()) + ["other"]
        for category in expected_categories:
            assert (dest_dir / category).exists()

        # Stats should be empty
        assert all(len(stats[cat]) == 0 for cat in expected_categories)

    def test_organize_overwrites_existing(self, mock_skill_dirs: Path, tmp_path: Path) -> None:
        """Organize skills overwrites existing files."""
        dest_dir = tmp_path / "organized"

        # First organization
        organize_skills(mock_skill_dirs, dest_dir)

        # Modify a file
        (dest_dir / "github" / "gh-review-pr" / "skill.md").write_text("# Modified")

        # Second organization
        organize_skills(mock_skill_dirs, dest_dir)

        # Original content should be restored
        content = (dest_dir / "github" / "gh-review-pr" / "skill.md").read_text()
        assert content == "# Review PR skill"

    def test_organize_multiple_skills_same_category(self, tmp_path: Path) -> None:
        """Organize multiple skills in same category."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create three GitHub skills
        (skills_dir / "gh-skill1").mkdir()
        (skills_dir / "gh-skill2").mkdir()
        (skills_dir / "gh-skill3").mkdir()

        dest_dir = tmp_path / "organized"
        stats = organize_skills(skills_dir, dest_dir)

        assert len(stats["github"]) == 3
        assert set(stats["github"]) == {"gh-skill1", "gh-skill2", "gh-skill3"}

    def test_organize_all_categories(self, mock_skill_dirs: Path, tmp_path: Path) -> None:
        """Organize skills across all categories."""
        dest_dir = tmp_path / "organized"

        stats = organize_skills(mock_skill_dirs, dest_dir)

        # Verify each category has expected skills
        assert len(stats["github"]) == 2
        assert len(stats["mojo"]) == 2
        assert len(stats["workflow"]) == 1
        assert len(stats["quality"]) == 1
        assert len(stats["agent"]) == 1
        assert len(stats["documentation"]) == 1
        assert len(stats["cicd"]) == 1
        assert len(stats["worktree"]) == 1
        assert len(stats["other"]) == 2
