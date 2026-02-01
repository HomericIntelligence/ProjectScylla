# ProjectScylla

ProjectScylla is a testing and optimization framework for agentic workflows, inspired by the mythic trials of Odysseus. In Homer’s Odyssey, Scylla represents one of the greatest challenges faced on the journey home — a monster that forced sailors to navigate perilous straits where every choice carried risk. In the same spirit, ProjectScylla provides a proving ground for AI agents, evaluating their ability to perform under constraints, balance trade-offs, and optimize outcomes when no path is perfect.

## Purpose

The goal of ProjectScylla is to measure, refine, and improve agentic systems. While ProjectOdyssey focuses on training and capability development, and ProjectKeystone establishes the communication layer for distributed agents, ProjectScylla ensures that agents are not only functional but resilient. It is the crucible where performance is tested, weaknesses are revealed, and strengths are sharpened.

## Core Concepts

- ⚖️ Trade-Off Evaluation: Agents are placed in scenarios where every decision has a cost, mirroring the dilemma of navigating between Scylla and Charybdis.
- 📊 Metrics & Benchmarks: Structured measurement of agent performance across adaptability, efficiency, and reliability.
- 🔄 Iterative Optimization: Continuous refinement through repeated trials, enabling agents to improve over time.
- 🧭 Resilience Testing: Assessing how agents respond to uncertainty, constraints, and unavoidable risks.

## Why Scylla?

Scylla embodies the essence of constrained optimization: unavoidable danger, sacrifice, and the need for wise navigation. By framing evaluation in this mythic context, ProjectScylla highlights the importance of judgment, foresight, and adaptability in agentic systems. Just as Odysseus had to choose the lesser evil to save his crew, agents must learn to optimize outcomes in environments where perfection is impossible.

## Ecosystem

- ProjectOdyssey → Training and capability development.
- ProjectKeystone → Communication and distributed agent coordination.
- ProjectScylla → Testing, measurement, and optimization under trial.

Together, these projects form a cohesive ecosystem for building, connecting, and refining agentic workflows.

---

## Quick Start

### Prerequisites

- **Pixi**: Package manager for reproducible environments ([install](https://pixi.sh))
- **Python 3.14+**: Required for analysis pipeline
- **Git**: For version control

### Installation

```bash
# Clone the repository
git clone https://github.com/HomericIntelligence/ProjectScylla.git
cd ProjectScylla

# Pixi will automatically set up the environment on first command
pixi run -e analysis python --version
```

### Running the Analysis Pipeline

The analysis pipeline processes experiment results and generates publication-ready figures, tables, and statistical reports.

#### Full Analysis (Recommended)

Generate all outputs (data exports, figures, and tables) from your experiment results:

```bash
pixi run -e analysis python scripts/generate_all_results.py \
  --data-dir ~/fullruns \
  --output-dir results/analysis
```

**Options:**
- `--data-dir`: Directory containing experiment results (default: `~/fullruns`)
- `--output-dir`: Base directory for outputs (default: `docs/`)
- `--no-render`: Skip PNG/PDF rendering (faster, Vega-Lite specs only)
- `--skip-data`: Skip data export (if CSVs already exist)
- `--skip-figures`: Skip figure generation
- `--skip-tables`: Skip table generation
- `--exclude`: Exclude specific experiments (e.g., `--exclude test001-dryrun`)

**Example with options:**

```bash
# Fast analysis without rendering (development mode)
pixi run -e analysis python scripts/generate_all_results.py \
  --no-render \
  --exclude test001-dryrun test001-debug

# Generate only tables (assumes data/figures already exist)
pixi run -e analysis python scripts/generate_all_results.py \
  --skip-data --skip-figures
```

#### Individual Pipeline Steps

Run specific parts of the analysis pipeline:

**1. Export Data Only**

```bash
pixi run -e analysis python scripts/export_data.py \
  --data-dir ~/fullruns \
  --output-dir results/analysis/data
```

Outputs:
- `results/analysis/data/runs.csv` - Per-run metrics
- `results/analysis/data/judges.csv` - Judge evaluations
- `results/analysis/data/criteria.csv` - Criterion-level scores
- `results/analysis/data/subtests.csv` - Subtest metadata
- `results/analysis/data/summary.json` - Experiment summary
- `results/analysis/data/statistical_results.json` - Statistical analysis

**2. Generate Figures Only**

```bash
pixi run -e analysis python scripts/generate_figures.py \
  --data-dir ~/fullruns \
  --output-dir results/analysis/figures
```

Outputs (27 figures × 5 formats each):
- `*.vl.json` - Vega-Lite specifications (version control friendly)
- `*.csv` - Figure data
- `*.png` - Raster images (300 DPI, publication quality)
- `*.pdf` - Vector graphics
- `*_include.tex` - LaTeX snippets for inclusion

**3. Generate Tables Only**

```bash
pixi run -e analysis python scripts/generate_tables.py \
  --data-dir ~/fullruns \
  --output-dir results/analysis/tables
```

Outputs (11 tables × 2 formats each):
- `*.md` - Markdown tables (human-readable)
- `*.tex` - LaTeX tables (publication-ready, booktabs formatted)

### Output Structure

After running the analysis, your output directory will contain:

```
results/analysis/
├── data/
│   ├── runs.csv                      # Per-run metrics
│   ├── judges.csv                    # Judge evaluations
│   ├── criteria.csv                  # Criterion-level scores
│   ├── subtests.csv                  # Subtest metadata
│   ├── summary.json                  # Experiment summary
│   └── statistical_results.json      # Statistical analysis results
├── figures/
│   ├── fig01_score_variance.*        # 5 formats per figure
│   ├── fig02_grade_distribution.*
│   ├── ...
│   └── fig27_effect_sizes.*
└── tables/
    ├── table01_tier_summary.md       # Markdown + LaTeX per table
    ├── table01_tier_summary.tex
    ├── ...
    └── table11_diagnostics.tex
```

### Using the Outputs

**In LaTeX Documents:**

```latex
% Include a figure
\begin{figure}
  \centering
  \input{results/analysis/figures/fig04_pass_rate_by_tier_include.tex}
  \caption{Pass rate by tier with 95\% bootstrap confidence intervals.}
  \label{fig:pass-rate}
\end{figure}

% Include a table
\input{results/analysis/tables/table02_tier_comparison.tex}
```

**In Python/Jupyter:**

```python
import pandas as pd

# Load the data
runs_df = pd.read_csv('results/analysis/data/runs.csv')
judges_df = pd.read_csv('results/analysis/data/judges.csv')

# Load statistical results
import json
with open('results/analysis/data/statistical_results.json') as f:
    stats = json.load(f)
```

**View Figures:**

```bash
# Open all PNG figures
open results/analysis/figures/*.png

# Or use your favorite viewer
eog results/analysis/figures/fig04_pass_rate_by_tier.png
```

---

## Analysis Pipeline Architecture

### Statistical Methodology

The analysis pipeline implements rigorous non-parametric statistical methods suitable for bounded, ordinal, and potentially non-normal data:

- **Bootstrap Confidence Intervals**: BCa (bias-corrected and accelerated) with 10,000 resamples
- **Omnibus Testing**: Kruskal-Wallis H test before pairwise comparisons (controls FWER)
- **Pairwise Comparisons**: Mann-Whitney U with Holm-Bonferroni correction
- **Effect Sizes**: Cliff's delta with bootstrapped confidence intervals (Romano et al., 2006 thresholds)
- **Inter-Rater Reliability**: Krippendorff's alpha for judge agreement

All statistical parameters are centralized in `src/scylla/analysis/config.yaml` for reproducibility.

### Metrics Computed

**Quality Metrics:**
- **Pass-Rate**: Functional test coverage (automated test success)
- **Implementation Rate (Impl-Rate)**: Semantic requirement satisfaction (LLM-as-Judge)
- **Score**: Weighted rubric-based evaluation
- **Consistency**: Output stability (1 - Coefficient of Variation)

**Economic Metrics:**
- **Cost-of-Pass (CoP)**: Expected cost per successful solution
- **Frontier CoP**: Minimum CoP across all configurations
- **Token Distribution**: Cost breakdown by component (input/output/total)

**Process Metrics:**
- **Latency**: Time from query to resolution
- **Judge Agreement**: Krippendorff's alpha across judges

### Data Requirements

The pipeline expects experiment results in the following structure:

```
fullruns/
└── {experiment_name}/
    └── {timestamp}/
        ├── config/
        │   └── experiment.json       # Experiment metadata
        └── T0-T6/                     # Tiers
            └── {subtest_id}/          # Subtests
                └── run_{01-10}/       # Runs (typically 10 per subtest)
                    ├── run_result.json  # Run outcomes
                    └── judge/
                        └── judge_{01-03}/
                            └── judgment.json  # Judge evaluations
```

**Required Fields in `run_result.json`:**
- `run_number`: Run identifier (integer)
- `exit_code`: Success/failure indicator (0 = success)
- `judges`: List of judge evaluations with grades and criteria scores

See `src/scylla/analysis/schemas/run_result_schema.json` for the complete JSON Schema.

### Configuration

All analysis parameters are externalized in `src/scylla/analysis/config.yaml`:

- Statistical parameters (alpha, bootstrap resamples, seed)
- Minimum sample sizes for each test
- Figure dimensions and DPI
- Color palettes and grade ordering
- Precision for numeric output
- LaTeX formatting options

Modify this file to customize the analysis without changing code.

---

## Development

### Running Tests

```bash
# Run all analysis tests
pixi run -e analysis pytest tests/unit/analysis/ -v

# Run specific test file
pixi run -e analysis pytest tests/unit/analysis/test_stats.py -v

# Run with coverage
pixi run -e analysis pytest tests/unit/analysis/ --cov=src/scylla/analysis --cov-report=html
```

### Adding New Figures

1. Create a new module in `src/scylla/analysis/figures/`
2. Implement your figure function following the existing pattern
3. Register the figure in `scripts/generate_figures.py`
4. Add tests in `tests/unit/analysis/test_figures.py`

### Adding New Tables

1. Add table function to appropriate module in `src/scylla/analysis/tables/`
2. Register in `scripts/generate_tables.py`
3. Add tests in `tests/unit/analysis/test_tables.py`

### Code Quality

```bash
# Run linting
pixi run -e analysis ruff check src/scylla/analysis/

# Auto-fix issues
pixi run -e analysis ruff check --fix src/scylla/analysis/

# Format code
pixi run -e analysis ruff format src/scylla/analysis/
```

---

## Troubleshooting

### Common Issues

**1. Data validation errors**

```
Schema validation failed: 'N/A' does not match '^[SABCDF]$'
```

**Solution**: Some judges returned "N/A" instead of valid grades. The pipeline warns but continues. To fix:
- Review the problematic runs
- Ensure all grades are one of: S, A, B, C, D, F
- Or update the schema to allow N/A

**2. Missing files**

```
Failed to load: [Errno 2] No such file or directory: '.../run_result.json'
```

**Solution**: Some runs are incomplete. The pipeline skips these with a warning. To investigate:
```bash
find ~/fullruns -name "run_*" -type d -exec sh -c 'test -f "$1/run_result.json" || echo "Missing: $1"' _ {} \;
```

**3. Type errors in criterion scores**

```
TypeError: unsupported operand type(s) for +: 'float' and 'str'
```

**Solution**: Some `criterion.achieved` values are strings instead of numbers. Fix in your data generation pipeline or add type coercion.

**4. Empty DataFrames**

The pipeline handles empty data gracefully but won't generate meaningful outputs. Ensure:
- At least 2 experiments exist in `--data-dir`
- Each experiment has at least 1 completed run
- Runs have valid `run_result.json` files

### Getting Help

- **Documentation**: See `docs/research.md` for detailed methodology
- **Examples**: Check `tests/unit/analysis/` for usage examples
- **Issues**: Report bugs at [GitHub Issues](https://github.com/HomericIntelligence/ProjectScylla/issues)
- **CLAUDE.md**: See `.claude/shared/` for development guidelines

---

## LaTeX Dependencies

To compile documents with generated tables/figures, you'll need:

**Required Packages:**
- `booktabs` - Professional table formatting
- `longtable` - Multi-page tables
- `threeparttable` - Table notes/footnotes
- `graphicx` - Figure inclusion

**Example Preamble:**

```latex
\documentclass{article}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{threeparttable}
\usepackage{graphicx}
\usepackage{amsmath}  % For statistical symbols

\begin{document}
% Your content here
\end{document}
```

---

## Publication Readiness

The analysis pipeline is **publication-ready** with:

✅ Rigorous non-parametric statistics (Kruskal-Wallis, Mann-Whitney U, Cliff's delta)
✅ Multiple comparison correction (Holm-Bonferroni throughout)
✅ Bootstrap confidence intervals (BCa, 10K resamples, seed=42)
✅ Effect sizes with confidence intervals
✅ 300 DPI publication-quality figures
✅ LaTeX-ready tables with proper formatting
✅ Reproducible configuration (all parameters in config.yaml)
✅ Comprehensive test suite (240+ tests, all passing)
✅ Statistical methodology documented and cited

See `docs/research.md` for the complete research methodology and metric definitions.

---

## License

[Add license information]

## Citation

If you use ProjectScylla in your research, please cite:

```bibtex
@software{projectscylla2026,
  title = {ProjectScylla: A Testing and Optimization Framework for Agentic Workflows},
  author = {[Authors]},
  year = {2026},
  url = {https://github.com/HomericIntelligence/ProjectScylla}
}
```
