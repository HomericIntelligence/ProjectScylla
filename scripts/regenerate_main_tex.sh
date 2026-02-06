#!/usr/bin/env bash
# Regenerate main.tex from paper.md (will overwrite existing main.tex!)
# Use this only when you want to discard manual edits and regenerate from scratch

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ARXIV_DIR="${PROJECT_ROOT}/docs/paper-dryrun-arxiv"

echo "=========================================="
echo "REGENERATE main.tex from paper.md"
echo "=========================================="
echo ""
echo "⚠️  WARNING: This will OVERWRITE any manual edits in main.tex!"
echo ""
read -p "Are you sure you want to continue? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "Regenerating main.tex..."
cd "${PROJECT_ROOT}"
pixi run python scripts/build_arxiv_paper.py

if [ -f "${ARXIV_DIR}/main.tex" ]; then
    echo "✓ main.tex regenerated from paper.md"
    echo ""
    echo "NOTE: You will need to manually fix LaTeX issues documented in"
    echo "docs/arxiv-submission.md before the PDF will compile successfully."
else
    echo "✗ Error: main.tex not generated"
    exit 1
fi
