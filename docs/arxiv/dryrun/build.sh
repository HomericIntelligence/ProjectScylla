#!/usr/bin/env bash
# Build arXiv paper and submission package
# Run from this directory: cd docs/arxiv/dryrun && ./build.sh

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

echo "=========================================="
echo "Building arXiv Paper: Taming Scylla"
echo "=========================================="
echo ""

# Step 1: Clean auxiliary files
echo "[1/4] Cleaning auxiliary files..."
rm -f paper.aux paper.log paper.out paper.toc paper.lof paper.lot paper.blg
echo "✓ Cleaned"
echo ""

# Step 2: Full LaTeX compilation cycle
echo "[2/4] Compiling LaTeX (4-step cycle)..."
echo "  Pass 1/4: pdflatex (generating aux)..."
pdflatex -interaction=nonstopmode -halt-on-error paper.tex > /dev/null 2>&1 || {
    echo "✗ Error during first pdflatex pass"
    echo "Check paper.log for details"
    exit 1
}

echo "  Pass 2/4: bibtex (resolving citations)..."
bibtex paper > /dev/null 2>&1 || {
    echo "✗ Error during bibtex pass"
    echo "Check paper.blg for details"
    exit 1
}

echo "  Pass 3/4: pdflatex (inserting citations)..."
pdflatex -interaction=nonstopmode -halt-on-error paper.tex > /dev/null 2>&1 || {
    echo "✗ Error during second pdflatex pass"
    exit 1
}

echo "  Pass 4/4: pdflatex (finalizing references)..."
pdflatex -interaction=nonstopmode -halt-on-error paper.tex > /dev/null 2>&1 || {
    echo "✗ Error during third pdflatex pass"
    exit 1
}

echo "✓ Compilation successful"
echo ""

# Step 3: Validate output
echo "[3/4] Validating output..."

# Check PDF exists
if [ ! -f "paper.pdf" ]; then
    echo "✗ Error: paper.pdf not generated"
    exit 1
fi

# Check file size
PDF_SIZE=$(stat -f%z "paper.pdf" 2>/dev/null || stat -c%s "paper.pdf" 2>/dev/null)
if [ "${PDF_SIZE}" -lt 10000 ]; then
    echo "✗ Warning: PDF file seems too small (${PDF_SIZE} bytes)"
    exit 1
fi

# Check for LaTeX errors
ERROR_COUNT=$(grep "^!" paper.log 2>/dev/null | wc -l | tr -d ' ')
ERROR_COUNT=${ERROR_COUNT:-0}
if [ "${ERROR_COUNT}" -gt 0 ]; then
    echo "✗ Warning: ${ERROR_COUNT} LaTeX errors found in log"
fi

# Check for unresolved references
UNRESOLVED=$(grep "??" paper.log 2>/dev/null | grep -v pdfTeX | wc -l | tr -d ' ')
UNRESOLVED=${UNRESOLVED:-0}
if [ "${UNRESOLVED}" -gt 0 ]; then
    echo "✗ Warning: ${UNRESOLVED} unresolved references"
fi

# Get page count if pdfinfo available
if command -v pdfinfo &> /dev/null; then
    PAGE_COUNT=$(pdfinfo paper.pdf 2>/dev/null | grep "Pages:" | awk '{print $2}')
    echo "  PDF: ${PDF_SIZE} bytes, ${PAGE_COUNT} pages"
else
    echo "  PDF: ${PDF_SIZE} bytes"
fi

echo "✓ Validation passed"
echo ""

# Step 4: Create submission tarball
echo "[4/4] Creating submission tarball..."

# Files to include (exclude paper.bbl and 00README.json per arXiv requirements)
tar -czf arxiv-submission.tar.gz \
    paper.tex \
    references.bib \
    figures/*.pdf \
    tables/tab04_criteria_performance.tex 2>/dev/null || {
    echo "✗ Error creating tarball"
    exit 1
}

TARBALL_SIZE=$(stat -f%z "arxiv-submission.tar.gz" 2>/dev/null || stat -c%s "arxiv-submission.tar.gz" 2>/dev/null)
FILE_COUNT=$(tar -tzf arxiv-submission.tar.gz | wc -l | tr -d ' ')

echo "✓ Tarball created: ${TARBALL_SIZE} bytes, ${FILE_COUNT} files"
echo ""

# Clean auxiliary files (arXiv generates .bbl from .bib)
echo "Cleaning auxiliary files..."
rm -f paper.aux paper.log paper.out paper.toc paper.lof paper.lot paper.blg paper.bbl
echo "✓ Cleaned"
echo ""

# Summary
echo "=========================================="
echo "Build Complete!"
echo "=========================================="
echo ""
echo "Output files:"
echo "  - paper.pdf (compiled paper)"
echo "  - arxiv-submission.tar.gz (upload to arXiv)"
echo ""
echo "Next steps:"
echo "  1. Review paper.pdf for correctness"
echo "  2. Upload arxiv-submission.tar.gz to arxiv.org"
echo "  3. See SUBMISSION-CHECKLIST.md for details"
echo ""
