"""Tests for scripts/fix_table_underscores.py."""

from __future__ import annotations

import pytest

from fix_table_underscores import fix_table_underscores


# ---------------------------------------------------------------------------
# fix_table_underscores
# ---------------------------------------------------------------------------


class TestFixTableUnderscores:
    """Tests for fix_table_underscores()."""

    def test_escapes_bare_underscore_in_data_row(self) -> None:
        """Underscores in data rows are escaped with backslash."""
        content = "column_name & value\n"
        result = fix_table_underscores(content)
        assert r"column\_name" in result

    def test_does_not_double_escape(self) -> None:
        """Already-escaped underscores are not double-escaped."""
        content = r"already\_escaped" + "\n"
        result = fix_table_underscores(content)
        assert r"\\_" not in result
        assert r"\_" in result

    def test_skips_label_line(self) -> None:
        """Lines with \\label command are not modified."""
        content = r"\label{tab:my_table}" + "\n"
        result = fix_table_underscores(content)
        assert "my_table" in result  # underscore not escaped

    def test_skips_caption_line(self) -> None:
        """Lines with \\caption command are not modified."""
        content = r"\caption{Some_Caption}" + "\n"
        result = fix_table_underscores(content)
        assert "Some_Caption" in result

    def test_skips_begin_line(self) -> None:
        """Lines with \\begin command are not modified."""
        content = r"\begin{tabular}" + "\n"
        result = fix_table_underscores(content)
        assert "tabular" in result

    def test_skips_end_line(self) -> None:
        """Lines with \\end command are not modified."""
        content = r"\end{tabular}" + "\n"
        result = fix_table_underscores(content)
        assert "tabular" in result

    def test_skips_toprule_line(self) -> None:
        """Lines with \\toprule are not modified."""
        content = r"\toprule" + "\n"
        result = fix_table_underscores(content)
        assert result == content

    def test_skips_midrule_line(self) -> None:
        """Lines with \\midrule are not modified."""
        content = r"\midrule" + "\n"
        result = fix_table_underscores(content)
        assert result == content

    def test_skips_bottomrule_line(self) -> None:
        """Lines with \\bottomrule are not modified."""
        content = r"\bottomrule" + "\n"
        result = fix_table_underscores(content)
        assert result == content

    def test_skips_multicolumn_line(self) -> None:
        """Lines with \\multicolumn are not modified."""
        content = r"\multicolumn{3}{c}{col_header}" + "\n"
        result = fix_table_underscores(content)
        assert "col_header" in result  # underscore not escaped

    def test_preserves_newline_structure(self) -> None:
        """Multi-line content preserves line count."""
        content = "line_one\nline_two\n"
        result = fix_table_underscores(content)
        assert result.count("\n") == content.count("\n")

    def test_empty_content(self) -> None:
        """Empty string returns empty string."""
        assert fix_table_underscores("") == ""

    def test_multiple_underscores_in_row(self) -> None:
        """All underscores in a data row are escaped."""
        content = "col_a & col_b & col_c\n"
        result = fix_table_underscores(content)
        # All three underscores should be escaped
        assert result.count(r"\_") == 3

    @pytest.mark.parametrize(
        "latex_cmd",
        [r"\label", r"\caption", r"\begin", r"\end", r"\toprule", r"\midrule", r"\bottomrule"],
    )
    def test_all_latex_commands_skip_modification(self, latex_cmd: str) -> None:
        """All LaTeX commands cause the line to be skipped."""
        content = f"{latex_cmd}{{some_underscore}}\n"
        result = fix_table_underscores(content)
        assert result == content
