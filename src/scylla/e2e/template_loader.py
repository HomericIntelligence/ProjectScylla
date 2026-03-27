"""Template loader for bash script generation.

Provides utilities for loading and rendering bash script templates
with parameter substitution.
"""

from __future__ import annotations

from pathlib import Path
from string import Template

# Template directory
TEMPLATE_DIR = Path(__file__).parent / "templates"


def load_template(template_name: str) -> Template:
    """Load a bash script template.

    Args:
        template_name: Name of the template file (e.g., "python_check.sh.template")

    Returns:
        string.Template object ready for substitution.

    Raises:
        FileNotFoundError: If template file doesn't exist

    """
    template_path = TEMPLATE_DIR / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    template_content = template_path.read_text()
    return Template(template_content)


def render_template(template_name: str, **kwargs: str) -> str:
    """Load and render a template with parameter substitution.

    Args:
        template_name: Name of the template file
        **kwargs: Variables to substitute in the template

    Returns:
        Rendered script content as string.

    Example:
        >>> script = render_template("python_check.sh.template", workspace="/path/to/workspace")

    """
    template = load_template(template_name)
    return template.substitute(**kwargs)


def write_script(
    output_path: Path,
    template_name: str,
    executable: bool = True,
    **kwargs: str,
) -> Path:
    """Render template and write to file.

    Args:
        output_path: Path where the script will be written
        template_name: Name of the template file
        executable: Whether to make the script executable (default: True)
        **kwargs: Variables to substitute in the template

    Returns:
        Path to the written script file.

    Example:
        >>> write_script(
        ...     Path("/results/run_01/commands/python_check.sh"),
        ...     "python_check.sh.template",
        ...     workspace="/workspace"
        ... )

    """
    script_content = render_template(template_name, **kwargs)
    output_path.write_text(script_content)

    if executable:
        output_path.chmod(0o755)

    return output_path
