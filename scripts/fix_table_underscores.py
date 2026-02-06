#!/usr/bin/env python3
"""Fix unescaped underscores in table .tex files.

Only escapes underscores in table data rows, not in LaTeX commands.
"""

import re
import sys


def fix_table_underscores(content: str) -> str:
    """Fix unescaped underscores in table content."""
    lines = content.split("\n")
    fixed_lines = []

    for line in lines:
        # Skip lines with LaTeX commands that should not be modified
        if any(
            cmd in line
            for cmd in [
                "\\label",
                "\\caption",
                "\\begin",
                "\\end",
                "\\toprule",
                "\\midrule",
                "\\bottomrule",
                "\\multicolumn",
            ]
        ):
            fixed_lines.append(line)
            continue

        # For data rows, escape underscores that are not already escaped
        # Match underscores not preceded by backslash
        fixed_line = re.sub(r"(?<!\\)_", r"\\_", line)
        fixed_lines.append(fixed_line)

    return "\n".join(fixed_lines)


if __name__ == "__main__":
    input_file = sys.argv[1]
    output_file = sys.argv[2]

    with open(input_file) as f:
        content = f.read()

    fixed_content = fix_table_underscores(content)

    with open(output_file, "w") as f:
        f.write(fixed_content)
