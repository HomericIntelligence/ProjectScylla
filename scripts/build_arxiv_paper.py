#!/usr/bin/env python3
"""Convert docs/paper.md to arXiv-ready LaTeX format.

This script reads the Markdown paper and generates a complete LaTeX document
without using pandoc, handling sections, citations, figures, tables, and
applying minor tone cleanup.
"""

import re
from pathlib import Path

# Citation mapping from inline [N] to BibTeX keys
CITATION_MAP = {
    "1": "liu2023agentbench",
    "2": "jimenez2024swebench",
    "3": "yao2024taubench",
    "4": "zhu2023promptbench2",
    "5": "polo2024efficient",
    "6": "projectodyssey",
    "7": "anthropic2024claude",
    "8": "gao2024lmevalharness",
    "9": "safetynet",
    "10": "ccmarketplace",
}

# Figures to include in main body (near their references)
MAIN_BODY_FIGURES = {"fig02", "fig06", "fig07", "fig09", "fig13", "fig14"}

# All figures that exist
ALL_FIGURES = {
    "fig01",
    "fig02",
    "fig03",
    "fig04",
    "fig05",
    "fig06",
    "fig07",
    "fig08",
    "fig09",
    "fig10",
    "fig11",
    "fig13",
    "fig14",
    "fig15",
    "fig16",
    "fig17",
    "fig18",
    "fig19",
    "fig20",
    "fig21",
    "fig22",
    "fig24",
    "fig25",
    "fig26",
}

# Appendix figure groupings
APPENDIX_FIGURES = {
    "Variance Analysis": ["fig01", "fig03", "fig04", "fig05"],
    "Cost Analysis": ["fig08", "fig10", "fig11"],
    "Judge Analysis": ["fig15", "fig16", "fig17"],
    "Diagnostic Metrics": ["fig18", "fig19", "fig20", "fig21", "fig22"],
    "Implementation Rate": ["fig24", "fig25", "fig26"],
}


def cleanup_tone(text: str) -> str:
    """Apply minor tone cleanup to remove informalities."""
    contractions = {
        r"\bdon't\b": "do not",
        r"\bdoesn't\b": "does not",
        r"\bdidn't\b": "did not",
        r"\bcan't\b": "cannot",
        r"\bcouldn't\b": "could not",
        r"\bwon't\b": "will not",
        r"\bwouldn't\b": "would not",
        r"\bisn't\b": "is not",
        r"\baren't\b": "are not",
        r"\bwasn't\b": "was not",
        r"\bweren't\b": "were not",
        r"\bhasn't\b": "has not",
        r"\bhaven't\b": "have not",
        r"\bhadn't\b": "had not",
        r"\bwe're\b": "we are",
        r"\bthey're\b": "they are",
        r"\bit's\b": "it is",
        r"\bthat's\b": "that is",
        r"\bthere's\b": "there is",
        r"\bI'm\b": "I am",
        r"\bhe's\b": "he is",
        r"\bshe's\b": "she is",
        r"\byou're\b": "you are",
    }

    for pattern, replacement in contractions.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text


def escape_latex(text: str) -> str:
    """Escape special LaTeX characters in text."""
    # Replace Unicode math symbols first (before escaping special chars)
    text = text.replace("≥", "__GEQMATH__")
    text = text.replace("≤", "__LEQMATH__")
    text = text.replace("≠", "__NEQMATH__")
    text = text.replace("×", "__TIMESMATH__")
    text = text.replace("±", "__PMMATH__")
    text = text.replace("→", "__ARROWMATH__")
    text = text.replace("—", "---")  # em-dash
    text = text.replace("–", "--")  # en-dash

    # Order matters - backslash first
    text = text.replace("\\", "\\textbackslash{}")
    text = text.replace("&", "\\&")
    text = text.replace("%", "\\%")
    text = text.replace("$", "\\$")
    text = text.replace("#", "\\#")
    text = text.replace("_", "\\_")
    text = text.replace("{", "\\{")
    text = text.replace("}", "\\}")
    text = text.replace("~", "\\textasciitilde{}")
    text = text.replace("^", "\\textasciicircum{}")

    # Now restore math symbols
    text = text.replace("__GEQMATH__", "$\\geq$")
    text = text.replace("__LEQMATH__", "$\\leq$")
    text = text.replace("__NEQMATH__", "$\\neq$")
    text = text.replace("__TIMESMATH__", "$\\times$")
    text = text.replace("__PMMATH__", "$\\pm$")
    text = text.replace("__ARROWMATH__", "$\\rightarrow$")

    return text


def convert_inline_formatting(line: str) -> str:
    """Convert inline Markdown formatting to LaTeX."""
    # First, handle Unicode symbols that need math mode
    line = line.replace("≥", "$\\geq$")
    line = line.replace("≤", "$\\leq$")
    line = line.replace("≠", "$\\neq$")
    line = line.replace("×", "$\\times$")
    line = line.replace("±", "$\\pm$")
    line = line.replace("→", "$\\rightarrow$")
    line = line.replace("—", "---")  # em-dash
    line = line.replace("–", "--")  # en-dash

    # Save code blocks temporarily
    code_blocks = []

    def save_code(match):
        code_blocks.append(match.group(1))
        return f"__CODE__{len(code_blocks) - 1}__"

    line = re.sub(r"`([^`]+)`", save_code, line)

    # Bold: **text** -> \textbf{text}
    line = re.sub(r"\*\*([^*]+)\*\*", r"\\textbf{\1}", line)

    # Italic: *text* -> \emph{text}
    line = re.sub(r"(?<![*\w])\*([^*]+)\*(?![*\w])", r"\\emph{\1}", line)

    # Restore code blocks as \texttt (escape underscores and other special chars)
    for i, code in enumerate(code_blocks):
        # Escape special characters in code
        escaped = code.replace("\\", "\\textbackslash{}")
        escaped = escaped.replace("_", "\\_")
        escaped = escaped.replace("{", "\\{")
        escaped = escaped.replace("}", "\\}")
        escaped = escaped.replace("^", "\\textasciicircum{}")
        escaped = escaped.replace("~", "\\textasciitilde{}")
        escaped = escaped.replace("%", "\\%")
        escaped = escaped.replace("&", "\\&")
        escaped = escaped.replace("#", "\\#")
        line = line.replace(f"__CODE__{i}__", f"\\texttt{{{escaped}}}")

    # Citations: [N] -> \cite{key}
    def replace_citation(match):
        num = match.group(1)
        if num in CITATION_MAP:
            return f"\\cite{{{CITATION_MAP[num]}}}"
        return match.group(0)

    line = re.sub(r"\[(\d+)\]", replace_citation, line)

    return line


def read_figure_metadata(figure_num: str) -> tuple[str, str]:
    """Read caption and label from _include.tex file."""
    include_path = Path(f"docs/paper-dryrun/figures/{figure_num}_include.tex")
    if not include_path.exists():
        # Try to find any matching file
        fig_dir = Path("docs/paper-dryrun/figures")
        matches = list(fig_dir.glob(f"{figure_num}_*_include.tex"))
        if matches:
            include_path = matches[0]
        else:
            return "", f"fig:{figure_num}"

    content = include_path.read_text()

    # Extract caption
    caption_match = re.search(r"\\caption\{([^}]+)\}", content)
    caption = caption_match.group(1) if caption_match else ""

    # Extract label
    label_match = re.search(r"\\label\{([^}]+)\}", content)
    label = label_match.group(1) if label_match else f"fig:{figure_num}"

    return caption, label


def generate_figure_latex(figure_num: str, width: str = "0.8\\textwidth") -> str:
    """Generate LaTeX figure environment for a given figure."""
    caption, label = read_figure_metadata(figure_num)

    # Escape special characters in caption
    caption = caption.replace("%", "\\%")
    caption = caption.replace("&", "\\&")
    caption = caption.replace("#", "\\#")
    caption = caption.replace("_", "\\_")

    # Determine actual filename from paper-dryrun/figures/
    fig_dir = Path("docs/paper-dryrun/figures")
    pdf_files = list(fig_dir.glob(f"{figure_num}_*.pdf"))

    if not pdf_files:
        return f"% Figure {figure_num} not found\n"

    filename = pdf_files[0].name

    latex = f"""\\begin{{figure}}[htbp]
\\centering
\\includegraphics[width={width}]{{figures/{filename}}}
\\caption{{{caption}}}
\\label{{{label}}}
\\end{{figure}}

"""
    return latex


def convert_markdown_table(lines: list[str]) -> str:
    """Convert Markdown table to LaTeX tabular environment."""
    if len(lines) < 2:
        return ""

    # Parse header
    header = lines[0]
    separator = lines[1] if len(lines) > 1 else ""
    data_rows = lines[2:] if len(lines) > 2 else []

    # Extract cells from header
    header_cells = [cell.strip() for cell in header.split("|")]
    # Remove empty cells from edges
    header_cells = [c for c in header_cells if c]

    num_cols = len(header_cells)

    # Determine alignment from separator
    alignments = []
    sep_cells = [cell.strip() for cell in separator.split("|") if cell.strip()]
    for cell in sep_cells:
        if cell.startswith(":") and cell.endswith(":"):
            alignments.append("c")
        elif cell.endswith(":"):
            alignments.append("r")
        else:
            alignments.append("l")

    if len(alignments) != num_cols:
        alignments = ["l"] * num_cols

    # Build LaTeX table
    col_spec = "|" + "|".join(alignments) + "|"

    latex = f"\\begin{{tabular}}{{{col_spec}}}\n\\hline\n"

    # Header row
    header_latex = " & ".join([convert_inline_formatting(c) for c in header_cells])
    latex += header_latex + " \\\\\n\\hline\n"

    # Data rows
    for row in data_rows:
        cells = [cell.strip() for cell in row.split("|")]
        cells = [c for c in cells if c]
        if cells and len(cells) == num_cols:
            row_latex = " & ".join([convert_inline_formatting(c) for c in cells])
            latex += row_latex + " \\\\\n\\hline\n"

    latex += "\\end{tabular}\n"

    return latex


def find_table_file(table_ref: str) -> str | None:
    """Find the matching table .tex file for a reference like 'Table 2.1'."""
    # Extract table number
    match = re.search(r"(\d+)\.(\d+)", table_ref)
    if not match:
        return None

    major = match.group(1).zfill(2)
    table_dir = Path("docs/paper-dryrun/tables")

    # Try to find matching file
    candidates = list(table_dir.glob(f"tab{major}_*.tex"))
    if candidates:
        return candidates[0].name

    return None


def convert_paper_to_latex(paper_path: Path, output_path: Path):
    """Convert paper from Markdown to LaTeX format."""
    content = paper_path.read_text()

    # Apply tone cleanup
    content = cleanup_tone(content)

    lines = content.split("\n")
    latex_lines = []

    # State tracking
    in_code_block = False
    in_list = False
    list_type = None
    in_table = False
    table_lines = []
    skip_mode = False

    # Track which figures have been inserted
    inserted_figures = set()

    # Document preamble
    latex_lines.extend(
        [
            r"\documentclass[11pt,letterpaper]{article}",
            r"\usepackage[utf8]{inputenc}",
            r"\usepackage[margin=1in]{geometry}",
            r"\usepackage{graphicx}",
            r"\usepackage{amsmath,amssymb}",
            r"\usepackage{hyperref}",
            r"\usepackage{booktabs}",
            r"\usepackage{array}",
            r"\usepackage{multirow}",
            r"\usepackage{longtable}",
            r"\usepackage{listings}",
            r"\usepackage{xcolor}",
            r"",
            r"% Listings configuration",
            r"\lstset{",
            r"  basicstyle=\ttfamily\small,",
            r"  breaklines=true,",
            r"  frame=single,",
            r"  backgroundcolor=\color{gray!10}",
            r"}",
            r"",
            r"\title{Measuring the Value of Enhanced Reasoning in Agentic AI Architectures:\\",
            r"An Economic Analysis of Testing Tiers}",
            r"\author{Anonymous}",
            r"\date{}",
            r"",
            r"\begin{document}",
            r"\maketitle",
            r"",
        ]
    )

    i = 0
    while i < len(lines):
        line = lines[i]

        # Skip title, subtitle, author lines
        if i < 10 and (
            line.startswith("# ")
            or line.startswith("## Understanding")
            or "Micah Villmow" in line
            or "Individual" in line
            or "@" in line
        ):
            i += 1
            continue

        # Handle code blocks
        if line.strip().startswith("```"):
            if not in_code_block:
                in_code_block = True
                latex_lines.append(r"\begin{lstlisting}")
            else:
                latex_lines.append(r"\end{lstlisting}")
                latex_lines.append("")
                in_code_block = False
            i += 1
            continue

        if in_code_block:
            latex_lines.append(line)
            i += 1
            continue

        # Handle horizontal rules (skip them)
        if line.strip() in ["---", "***", "___"]:
            i += 1
            continue

        # Handle tables
        if "|" in line and "---" not in line and not in_table:
            in_table = True
            table_lines = [line]
            i += 1
            continue

        if in_table:
            if "|" in line or "---" in line.strip():
                table_lines.append(line)
                i += 1
                continue
            else:
                # End of table
                if len(table_lines) >= 2:
                    latex_table = convert_markdown_table(table_lines)
                    latex_lines.append("")
                    latex_lines.append(latex_table)
                    latex_lines.append("")
                in_table = False
                table_lines = []
                # Process current line

        # Handle sections
        if line.startswith("## "):
            if in_list:
                latex_lines.append(f"\\end{{{list_type}}}")
                latex_lines.append("")
                in_list = False

            # Strip "## " and optional section numbers like "1. "
            title = line[2:].strip()  # Remove "##"
            title = re.sub(r"^\d+\.?\s+", "", title)  # Remove optional section numbers

            # Handle abstract specially
            if title.lower() == "abstract":
                latex_lines.append(r"\begin{abstract}")
                # Collect abstract text
                i += 1
                while i < len(lines) and not lines[i].startswith("##"):
                    if lines[i].strip() and lines[i].strip() not in ["---", "***", "___"]:
                        latex_lines.append(convert_inline_formatting(lines[i]))
                    i += 1
                latex_lines.append(r"\end{abstract}")
                latex_lines.append("")
                continue

            # Handle keywords section (keep as-is, don't make it a section)
            if title.lower() == "keywords":
                latex_lines.append(r"\begin{center}")
                latex_lines.append(r"\textbf{Keywords:}")
                # Collect keywords text
                i += 1
                keyword_lines = []
                while i < len(lines) and not lines[i].startswith("##"):
                    if lines[i].strip() and lines[i].strip() not in ["---", "***", "___"]:
                        keyword_lines.append(convert_inline_formatting(lines[i]))
                    i += 1
                latex_lines.extend(keyword_lines)
                latex_lines.append(r"\end{center}")
                latex_lines.append("")
                continue

            title = convert_inline_formatting(title)

            # Check for references section
            if "reference" in title.lower():
                skip_mode = True
                latex_lines.append("")
                latex_lines.append(r"\bibliographystyle{plain}")
                latex_lines.append(r"\bibliography{references}")
                i += 1
                continue

            # Check for appendix section (triggers \appendix command)
            if title.lower() == "appendices":
                latex_lines.append("")
                latex_lines.append(r"\appendix")
                # Don't create a section for "Appendices" itself, just emit \appendix
                i += 1
                continue

            latex_lines.append(f"\\section{{{title}}}")
            latex_lines.append("")
            i += 1
            continue

        if line.startswith("### "):
            if in_list:
                latex_lines.append(f"\\end{{{list_type}}}")
                latex_lines.append("")
                in_list = False

            # Strip "###" and optional subsection numbers like "4.1 "
            title = line[3:].strip()
            title = re.sub(r"^\d+\.\d+\.?\s+", "", title)

            # Check if this is an appendix subsection (e.g., "Appendix A:")
            # These should be \section after \appendix, not \subsection
            if title.lower().startswith("appendix "):
                # Remove "Appendix " prefix for cleaner section title
                appendix_title = title[9:].strip()  # Remove "Appendix "
                latex_lines.append(f"\\section{{{appendix_title}}}")
            else:
                title = convert_inline_formatting(title)
                latex_lines.append(f"\\subsection{{{title}}}")

            latex_lines.append("")
            i += 1
            continue

        if line.startswith("#### "):
            if in_list:
                latex_lines.append(f"\\end{{{list_type}}}")
                latex_lines.append("")
                in_list = False

            title = line[4:].strip()
            title = convert_inline_formatting(title)
            latex_lines.append(f"\\subsubsection{{{title}}}")
            latex_lines.append("")
            i += 1
            continue

        # Skip references section content
        if skip_mode:
            i += 1
            continue

        # Handle lists
        bullet_match = re.match(r"^(\s*)([-*])\s+(.+)$", line)
        if bullet_match:
            item_text = bullet_match.group(3)

            if not in_list:
                latex_lines.append(r"\begin{itemize}")
                in_list = True
                list_type = "itemize"

            item_text = convert_inline_formatting(item_text)
            latex_lines.append(f"\\item {item_text}")
            i += 1
            continue

        number_match = re.match(r"^(\s*)(\d+)\.\s+(.+)$", line)
        if number_match:
            item_text = number_match.group(3)

            if not in_list:
                latex_lines.append(r"\begin{enumerate}")
                in_list = True
                list_type = "enumerate"
            elif list_type == "itemize":
                latex_lines.append(r"\end{itemize}")
                latex_lines.append(r"\begin{enumerate}")
                list_type = "enumerate"

            item_text = convert_inline_formatting(item_text)
            latex_lines.append(f"\\item {item_text}")
            i += 1
            continue

        # Close list if we hit non-list content
        if in_list and line.strip() and not line.strip().startswith(("- ", "* ")):
            if not re.match(r"^\s*\d+\.\s+", line):
                latex_lines.append(f"\\end{{{list_type}}}")
                latex_lines.append("")
                in_list = False

        # Check for figure references and insert main body figures
        # Look for patterns like "Figure 7 (see `docs/paper-dryrun/figures/fig07_..."
        # Handle multi-line references and multiple figures on same line
        combined_text = line
        if i + 1 < len(lines):
            combined_text += " " + lines[i + 1]
        if i + 2 < len(lines):
            combined_text += " " + lines[i + 2]

        # Find all figure numbers mentioned (fig01, fig02, etc.)
        fig_nums_in_text = re.findall(r"(fig\d+)_", combined_text)

        if "Figure" in line and fig_nums_in_text:
            # Replace all "Figure N (see ...)" with "Figure~\ref{fig:figNN}"
            for fig_num in fig_nums_in_text:
                # Replace pattern like "Figure 7 (see `docs/.../fig07_...`)"
                line = re.sub(
                    rf"Figure\s+\d+\s*\(see\s+`?docs/paper-dryrun/figures/{fig_num}_[^`)]+`?\)",
                    f"Figure~\\ref{{fig:{fig_num}}}",
                    line,
                )

            line = convert_inline_formatting(line)
            latex_lines.append(line)

            # Insert all main body figures found on this line
            for fig_num in fig_nums_in_text:
                if fig_num in MAIN_BODY_FIGURES and fig_num not in inserted_figures:
                    latex_lines.append("")
                    latex_lines.append(generate_figure_latex(fig_num))
                    inserted_figures.add(fig_num)

            i += 1
            continue

        # Check for table references
        table_pattern = r"Table\s+(\d+\.\d+)"
        table_match = re.search(table_pattern, line)
        if table_match:
            table_file = find_table_file(table_match.group(1))
            if table_file:
                line = convert_inline_formatting(line)
                latex_lines.append(line)
                latex_lines.append("")
                latex_lines.append(f"\\input{{tables/{table_file}}}")
                latex_lines.append("")
                i += 1
                continue

        # Regular text
        if line.strip():
            line = convert_inline_formatting(line)
            latex_lines.append(line)
        else:
            if latex_lines and latex_lines[-1].strip():
                latex_lines.append("")

        i += 1

    # Close any open list
    if in_list:
        latex_lines.append(f"\\end{{{list_type}}}")
        latex_lines.append("")

    # End document
    latex_lines.append(r"\end{document}")

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(latex_lines))
    print(f"✓ Generated LaTeX paper: {output_path}")
    print(f"  - Inserted {len(inserted_figures)} figures")
    section_marker = "\\section"
    section_count = len([line for line in latex_lines if line.startswith(section_marker)])
    print(f"  - {section_count} sections")


if __name__ == "__main__":
    paper_path = Path("docs/paper.md")
    output_path = Path("docs/paper-dryrun-arxiv/main.tex")

    if not paper_path.exists():
        print(f"✗ Error: {paper_path} not found")
        exit(1)

    convert_paper_to_latex(paper_path, output_path)
    print("✓ Conversion complete")
