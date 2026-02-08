# arXiv Paper: "Taming Scylla"

**Paper**: Taming Scylla: Measuring Cost-of-Pass in Agentic CLI Tools
**Format**: arXiv-ready LaTeX
**Status**: Publication-ready (all fixes applied)

---

## Quick Start

### Build Paper

```bash
cd docs/arxiv/dryrun
./build.sh
```

**Output**:
- `paper.pdf` - Compiled paper (494KB, 32 pages)
- `arxiv-submission.tar.gz` - Upload this to arXiv (398KB, 29 files)

### Files

| File | Purpose |
|------|---------|
| `paper.tex` | Main source (edit this) |
| `paper.bbl` | Pre-compiled bibliography (required for arXiv) |
| `references.bib` | Bibliography source (10 cited entries) |
| `00README.json` | arXiv configuration (pdflatex, TeX Live 2023) |
| `figures/*.pdf` | 24 figure PDFs |
| `tables/*.tex` | Table files (only tab04 is `\input`'ed) |
| `build.sh` | Build script (4-step LaTeX cycle + tarball) |
| `SUBMISSION-CHECKLIST.md` | arXiv upload instructions |

---

## Manual Compilation

If you need to compile manually without `build.sh`:

```bash
# Full 4-step cycle (required after bibliography changes)
pdflatex -interaction=nonstopmode paper.tex
bibtex paper
pdflatex -interaction=nonstopmode paper.tex
pdflatex -interaction=nonstopmode paper.tex

# Create submission tarball
tar -czf arxiv-submission.tar.gz \
    paper.tex \
    paper.bbl \
    references.bib \
    00README.json \
    figures/*.pdf \
    tables/tab04_criteria_performance.tex
```

---

## Paper Status

| Metric | Value |
|--------|-------|
| **Compilation** | ✅ 0 errors, 0 unresolved references |
| **Bibliography** | ✅ 10 cited entries (cleaned from 36) |
| **Figures** | ✅ 24 PDFs included |
| **Tables** | ✅ 1 table file |
| **PDF** | ✅ 494KB, 32 pages |
| **Submission** | ✅ Ready for arXiv upload |

---

## Recent Changes

**2026-02-07**: Publication polish applied
- ✅ CoP values updated to 3 decimal places
- ✅ Terminology standardized (git worktrees, not containers)
- ✅ Bibliography cleaned to 10 cited entries
- ✅ Glob paths corrected (tests/fixtures/tests/*)
- ✅ Grammar and style formalized

---

## arXiv Submission

See `SUBMISSION-CHECKLIST.md` for detailed instructions.

**Quick steps**:
1. Review `paper.pdf` one final time
2. Upload `arxiv-submission.tar.gz` to https://arxiv.org/submit
3. Select category: **cs.SE** (Software Engineering)
4. Monitor processing (24-48 hours)

---

## Troubleshooting

### "Undefined references" warning

Run the full 4-step cycle (or use `./build.sh`). Single pdflatex pass won't resolve citations.

### "Bibliography not found" error

The `paper.bbl` file must exist (pre-compiled by bibtex). If missing, run `bibtex paper`.

### Figures not rendering

Verify all PDFs exist in `figures/` directory. The paper references 24 figures (fig01-fig26, missing fig12/fig23).

### arXiv compilation fails

Check arXiv logs for specific errors. Common issues:
- Missing LaTeX packages (add to preamble)
- Figure paths incorrect (use relative paths)
- Bibliography issues (ensure paper.bbl is valid)

---

## Related Documentation

- `SUBMISSION-CHECKLIST.md` - arXiv upload guide
- `../../arxiv-submission.md` - General arXiv submission documentation
- `.claude-plugin/skills/arxiv-paper-polish/` - Skill for publication polish workflow
