#!/usr/bin/env bash
# Build arXiv submission package from paper.tex

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ARXIV_DIR="${PROJECT_ROOT}/docs/paper-dryrun-arxiv"

echo "=========================================="
echo "Building arXiv Submission Package"
echo "=========================================="
echo ""

# Step 1: Create directory structure
echo "[1/11] Creating directory structure..."
mkdir -p "${ARXIV_DIR}/figures"
mkdir -p "${ARXIV_DIR}/tables"
echo "✓ Directories created"
echo ""

# Step 1.5: Verify paper alignment
echo "[1.5/11] Verifying paper.md <-> paper.tex alignment..."
cd "${PROJECT_ROOT}"
pixi run python scripts/verify_paper_alignment.py || echo "⚠ Warning: alignment issues found (continuing anyway)"
echo ""

# Step 2: Generate main.tex from paper.tex (always regenerate)
echo "[2/11] Generating main.tex from paper.tex..."
cd "${PROJECT_ROOT}"
pixi run python scripts/build_arxiv_paper.py
if [ ! -f "${ARXIV_DIR}/main.tex" ]; then
    echo "✗ Error: main.tex not generated"
    exit 1
fi
echo "✓ main.tex generated from paper.tex"
echo ""

# Step 3: Copy figures
echo "[3/11] Copying figures..."
FIGURE_COUNT=0
for pdf in docs/paper-dryrun/figures/*.pdf; do
    if [ -f "$pdf" ]; then
        cp "$pdf" "${ARXIV_DIR}/figures/"
        FIGURE_COUNT=$((FIGURE_COUNT + 1))
    fi
done
echo "✓ Copied ${FIGURE_COUNT} figure PDFs"
echo ""

# Step 4: Copy tables and fix underscores
echo "[4/11] Copying tables..."
TABLE_COUNT=0
for tex in docs/paper-dryrun/tables/*.tex; do
    if [ -f "$tex" ]; then
        filename=$(basename "$tex")
        pixi run python scripts/fix_table_underscores.py "$tex" "${ARXIV_DIR}/tables/$filename"
        TABLE_COUNT=$((TABLE_COUNT + 1))
    fi
done
echo "✓ Copied ${TABLE_COUNT} table .tex files"
echo ""

# Step 5: Copy bibliography
echo "[5/11] Copying bibliography..."
cp docs/references.bib "${ARXIV_DIR}/references.bib"
echo "✓ Bibliography copied"
echo ""

# Step 6: Create 00README.json
echo "[6/11] Creating 00README.json..."
cat > "${ARXIV_DIR}/00README.json" << 'EOF'
{
  "spec_version": 1,
  "process": {
    "compiler": "pdflatex",
    "texlive_version": "2023"
  },
  "sources": [
    { "filename": "main.tex", "usage": "toplevel" }
  ]
}
EOF
echo "✓ 00README.json created"
echo ""

# Step 7: Compile LaTeX
echo "[7/11] Compiling LaTeX (pdflatex → bibtex → pdflatex × 2)..."
cd "${ARXIV_DIR}"

# Clean any stale auxiliary files
rm -f *.aux *.log *.out *.toc *.lof *.lot *.bbl *.blg

# First pass
echo "  Pass 1/4: pdflatex (generating aux)..."
pdflatex -interaction=nonstopmode -halt-on-error main.tex > /dev/null 2>&1 || {
    echo "✗ Error during first pdflatex pass"
    echo "Check ${ARXIV_DIR}/main.log for details"
    exit 1
}

# BibTeX
echo "  Pass 2/4: bibtex (resolving citations)..."
bibtex main > /dev/null 2>&1 || {
    echo "✗ Error during bibtex pass"
    echo "Check ${ARXIV_DIR}/main.blg for details"
    exit 1
}

# Second pass
echo "  Pass 3/4: pdflatex (inserting citations)..."
pdflatex -interaction=nonstopmode -halt-on-error main.tex > /dev/null 2>&1 || {
    echo "✗ Error during second pdflatex pass"
    exit 1
}

# Third pass
echo "  Pass 4/4: pdflatex (finalizing references)..."
pdflatex -interaction=nonstopmode -halt-on-error main.tex > /dev/null 2>&1 || {
    echo "✗ Error during third pdflatex pass"
    exit 1
}

echo "✓ Compilation successful"
echo ""

# Step 8: Validate output
echo "[8/11] Validating PDF output..."
if [ ! -f "main.pdf" ]; then
    echo "✗ Error: main.pdf not generated"
    exit 1
fi

# Check file size
PDF_SIZE=$(stat -f%z "main.pdf" 2>/dev/null || stat -c%s "main.pdf" 2>/dev/null)
if [ "${PDF_SIZE}" -lt 10000 ]; then
    echo "✗ Warning: PDF file seems too small (${PDF_SIZE} bytes)"
fi

# Check page count (requires pdfinfo)
if command -v pdfinfo &> /dev/null; then
    PAGE_COUNT=$(pdfinfo main.pdf 2>/dev/null | grep "Pages:" | awk '{print $2}')
    echo "  Pages: ${PAGE_COUNT}"
    if [ "${PAGE_COUNT}" -lt 10 ]; then
        echo "✗ Warning: Page count seems low"
    fi
fi

echo "✓ PDF validated (size: ${PDF_SIZE} bytes)"
echo ""

# Step 9: Create submission tarball
echo "[9/11] Creating submission tarball..."

# Files to include
tar -czf submission.tar.gz \
    main.tex \
    main.bbl \
    references.bib \
    00README.json \
    figures/*.pdf \
    tables/*.tex

TARBALL_SIZE=$(stat -f%z "submission.tar.gz" 2>/dev/null || stat -c%s "submission.tar.gz" 2>/dev/null)
echo "✓ Tarball created (size: ${TARBALL_SIZE} bytes)"
echo ""

# Step 10: Clean auxiliary files
echo "[10/11] Cleaning auxiliary files..."
rm -f main.aux main.log main.out main.toc main.lof main.lot main.blg
echo "✓ Auxiliary files cleaned"
echo ""

# Summary
echo "=========================================="
echo "Build Complete!"
echo "=========================================="
echo ""
echo "Output directory: ${ARXIV_DIR}"
echo ""
echo "Files ready for submission:"
echo "  - main.pdf (compiled paper)"
echo "  - submission.tar.gz (upload this to arXiv)"
echo ""
echo "Next steps:"
echo "  1. Review main.pdf for correctness"
echo "  2. Upload submission.tar.gz to arxiv.org"
echo "  3. See docs/arxiv-submission.md for detailed instructions"
echo ""
