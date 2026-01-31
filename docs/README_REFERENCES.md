# References Guide

## BibTeX File Structure

The `references.bib` file contains all bibliographic references for ProjectScylla research documents.

### Organization

References are organized into two sections:

1. **Paper.md References (citations [1]-[8])**: Common benchmarks and evaluation frameworks
   - Agent-Bench, SWE-Bench, TAU-Bench
   - PromptBench, PromptEval
   - Claude Code, lm-evaluation-harness

2. **Research.md References (numbered 1-36)**: Comprehensive research citations
   - Hierarchical agentic architectures
   - Multi-agent systems
   - Cost-of-Pass framework
   - Token efficiency and optimization
   - Evaluation methodologies

### Usage

#### LaTeX Documents

```latex
\documentclass{article}
\usepackage{cite}

\begin{document}

% Cite using BibTeX keys
As shown in SWE-Bench~\cite{jimenez2024swebench}...

Agent-Bench~\cite{liu2023agentbench} demonstrates...

% Bibliography
\bibliographystyle{plain}
\bibliography{references}

\end{document}
```

#### Markdown Documents

For now, citations in `research.md` and `paper.md` use numbered references ([1], [2], etc.).
These correspond to specific entries in `references.bib`.

**Mapping:**
- `paper.md [1]` → `liu2023agentbench` (Agent-Bench)
- `paper.md [2]` → `jimenez2024swebench` (SWE-Bench)
- `paper.md [3]` → `yao2024taubench` (TAU-Bench)
- `paper.md [4]` → `zhu2024promptbench` (PromptBench)
- `paper.md [5]` → `deng2024prompteval` (PromptEval)
- `paper.md [7]` → `anthropic2024claudecode` (Claude Code)
- `paper.md [8]` → `gao2024lmevalharness` (lm-evaluation-harness)

### Adding New References

1. Add entry to `references.bib` following the existing format:

```bibtex
@article{authorYYYYkeyword,
  title={Full Title Here},
  author={Author, Name and Others},
  journal={Venue},
  year={2025},
  url={https://...},
  note={Additional context}
}
```

2. Use consistent key format: `firstauthorYYYYkeyword`
3. Add URL when available
4. Include `note` field for access dates or additional context

### Citation Keys

**Format**: `firstauthorYYYYkeyword`

Examples:
- `liu2023agentbench` - Liu et al., 2023, Agent-Bench paper
- `jimenez2024swebench` - Jimenez et al., 2024, SWE-Bench paper
- `anthropic2024claudecode` - Anthropic, 2024, Claude Code documentation

### Tools

**Compile LaTeX with BibTeX:**
```bash
pdflatex research_paper.tex
bibtex research_paper
pdflatex research_paper.tex
pdflatex research_paper.tex
```

**Validate BibTeX file:**
```bash
# Check syntax
bibtex -terse references

# Generate bibliography preview
bibtool -s references.bib
```

### Status

- ✅ 43 total references (8 from paper.md, 35 from research.md)
- ✅ All major benchmarks covered (Agent-Bench, SWE-Bench, TAU-Bench)
- ✅ Cost-of-Pass framework references included
- ⚠️ Some research.md references need author names (listed as "others")
- ⚠️ Some URLs may need verification

### Future Work

1. Add complete author lists for multi-author papers
2. Verify all URLs are current
3. Add DOIs where available
4. Convert numbered citations in markdown to BibTeX keys
5. Create unified citation style guide
