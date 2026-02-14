# ProjectScylla

[![Python](https://img.shields.io/badge/python-3.14+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-BSD--3--Clause-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-2026%2B-brightgreen.svg)](#)
[![Status](https://img.shields.io/badge/status-stable-brightgreen.svg)](#)

## 📑 Table of Contents

- [🎯 What is ProjectScylla?](#-what-is-projectscylla)
- [Core Concepts](#core-concepts)
- [🚀 Quick Start](#-quick-start)
- [📊 System Requirements](#-system-requirements)
- [Analysis Pipeline Architecture](#analysis-pipeline-architecture)
- [Development](#development)
- [🔧 Troubleshooting](#-troubleshooting)
- [Publication Readiness](#publication-readiness)
- [🤝 Contributing](#-contributing)

## 🎯 What is ProjectScylla?

ProjectScylla is a comprehensive testing framework for AI agent workflows that:

- **🔬 Measures** agent performance under constrained conditions
- **📈 Analyzes** results with rigorous statistical methods
- **⚖️ Optimizes** agent decisions through trade-off evaluation
- **📋 Generates** publication-ready reports, figures, and tables

**Key Output**: Publication-quality statistical reports with **27 figures** and **11 tables** from a single command.

> "In Homer's Odyssey, Scylla represents one of the greatest challenges on the journey home — a monster that forced sailors to navigate perilous straits where every choice carried risk. ProjectScylla provides the same proving ground for AI agents."

## Quick Start Guide

### 🚀 5-Minute Setup

```bash
# 1. Install prerequisites
curl -fsSL https://pixi.sh/install.sh | bash

# 2. Clone and setup
git clone https://github.com/HomericIntelligence/ProjectScylla.git
cd ProjectScylla

# 3. Run your first analysis
pixi run python --version  # Verify installation
pixi run python scripts/generate_all_results.py --data-dir ~/fullruns

# 4. View results (27 figures + 11 tables generated)
open results/analysis/figures/*.png  # macOS
xdg-open results/analysis/figures/*.png  # Linux
```

**That's it!** All outputs appear in `results/analysis/` directory.

### 💡 Usage Examples

**Compare Two Agent Configurations:**

```bash
pixi run python scripts/generate_all_results.py \
  --data-dir ~/experiments/ \
  --output-dir comparison_results/ \
  --exclude test001-dryrun
```

**Fast Development Mode (No Rendering):**

```bash
# Quick iteration - generates Vega-Lite specs only
pixi run python scripts/generate_all_results.py \
  --data-dir ~/quick_test \
  --no-render \
  --skip-data  # Skip if CSVs already exist
```

## 📊 System Requirements

**Minimum Requirements:**

- Python 3.14+
- 8GB RAM for full dataset analysis
- 2GB disk space for results

**Typical Performance:**

- Full analysis: 10-15 minutes (10,000 bootstrap samples)
- Figures only: 2-3 minutes
- Tables only: 1-2 minutes

**Scale:** Handles experiments with 1000+ runs efficiently

---

## Core Concepts

- ⚖️ **Trade-Off Evaluation**: Agents face scenarios where every decision has cost, mirroring Scylla and Charybdis dilemma
- 📊 **Metrics & Benchmarks**: Structured measurement across adaptability, efficiency, and reliability
- 🔄 **Iterative Optimization**: Continuous refinement through repeated trials
- 🧭 **Resilience Testing**: Assessment under uncertainty, constraints, and risks

## Ecosystem

- **ProjectOdyssey** → Training and capability development
- **ProjectKeystone** → Communication and distributed agent coordination
- **ProjectScylla** → Testing, measurement, and optimization under trial

Together: cohesive ecosystem for building, connecting, and refining agent workflows.

---

## Running the Analysis Pipeline

### Full Analysis (Recommended)

Generate all outputs (data exports, figures, tables):

```bash
pixi run python scripts/generate_all_results.py \
  --data-dir ~/fullruns \
  --output-dir results/analysis
```

**Key Options:**

- `--data-dir` → Directory with experiment results (default: `~/fullruns`)
- `--output-dir` → Base output directory (default: `docs/`)
- `--no-render` → Skip PNG/PDF (faster, Vega-Lite specs only)
- `--skip-data/skip-figures/skip-tables` → Generate specific components only
- `--exclude` → Filter experiments (e.g., `--exclude test001-dryrun`)

```bash
# Development mode - no rendering
pixi run python scripts/generate_all_results.py \
  --no-render \
  --exclude test001-dryrun test001-debug

# Regenerate tables only (assumes data/figures exist)
pixi run python scripts/generate_all_results.py \
  --skip-data --skip-figures
```

### Individual Pipeline Steps

**1. Export Data Only**

```bash
pixi run python scripts/export_data.py \
  --data-dir ~/fullruns \
  --output-dir results/analysis/data
```

**Outputs:** `runs.csv`, `judges.csv`, `criteria.csv`, `subtests.csv`, `summary.json`, `statistical_results.json`

**2. Generate Figures Only (27 figures × 5 formats)**

```bash
pixi run python scripts/generate_figures.py \
  --data-dir ~/fullruns \
  --output-dir results/analysis/figures
```

**Outputs:** `*.vl.json`, `*.csv`, `*.png` (300 DPI), `*.pdf`, `*_include.tex`

**3. Generate Tables Only (11 tables × 2 formats)**

```bash
pixi run python scripts/generate_tables.py \
  --data-dir ~/fullruns \
  --output-dir results/analysis/tables
```

**Outputs:** `*.md` (human-readable), `*.tex` (LaTeX, booktabs formatted)

### Output Structure

```
results/analysis/
├── data/
│   ├── runs.csv                      # Per-run metrics
│   ├── judges.csv                    # Judge evaluations
│   ├── criteria.csv                  # Criterion-level scores
│   ├── subtests.csv                  # Subtest metadata
│   ├── summary.json                  # Experiment summary
│   └── statistical_results.json      # Statistical analysis
├── figures/                          # 27 figures × 5 formats
│   ├── fig01_score_variance.*
│   ├── fig02_grade_distribution.*
│   └── ... (27 total)
└── tables/                           # 11 tables × 2 formats
    ├── table01_tier_summary.md
    ├── table01_tier_summary.tex
    └── ... (11 total)
```

### Using the Outputs

**LaTeX Integration:**

```latex
\begin{figure}
  \centering
  \input{results/analysis/figures/fig04_pass_rate_by_tier_include.tex}
  \caption{Pass rate by tier with 95\% bootstrap confidence intervals.}
  \label{fig:pass-rate}
\end{figure}

\input{results/analysis/tables/table02_tier_comparison.tex}
```

**Python/Jupyter:**

```python
import pandas as pd
import json

# Load data
runs_df = pd.read_csv('results/analysis/data/runs.csv')
judges_df = pd.read_csv('results/analysis/data/judges.csv')

# Load statistical results
with open('results/analysis/data/statistical_results.json') as f:
    stats = json.load(f)
```

---

## Experiment Management Scripts

ProjectScylla provides comprehensive scripts for running, managing, and analyzing experiments.

### 🧪 Running Experiments

**Primary Experiment Runner:**

```bash
# Run full experiment
pixi run python scripts/run_e2e_experiment.py --config config/test.yaml

# Run specific tiers
pixi run python scripts/run_e2e_experiment.py \
  --tiers-dir tests/fixtures/tests/test-001 \
  --tiers T0 T1 --runs 10 -v
```

**Container-Based Execution:**

```bash
./scripts/setup_api_key.sh
./scripts/run_experiment_in_container.sh \
  --tiers-dir tests/fixtures/tests/test-001 \
  --tiers T0 --runs 5 --verbose
```

### 🔄 Recovery & Re-running

```bash
# Re-run failed agents
pixi run python scripts/rerun_agents.py \
  --data-dir ~/fullruns/test_experiment --tiers T0 T1

# Re-run failed judges
pixi run python scripts/rerun_judges.py \
  --data-dir ~/fullruns/test_experiment
```

### 📊 Results Management

```bash
# Regenerate all results
pixi run python scripts/regenerate_results.py \
  --data-dir ~/fullruns/test_experiment \
  --output-dir results/analysis

# Regenerate agent-specific results
pixi run python scripts/regenerate_agent_results.py \
  --data-dir ~/fullruns/test_experiment
```

---

## Analysis Pipeline Architecture

### Statistical Methodology

Rigorous non-parametric methods for bounded, ordinal, non-normal data:

- **Bootstrap Confidence Intervals**: BCa with 10,000 resamples
- **Omnibus Testing**: Kruskal-Wallis H test (controls FWER)
- **Pairwise Comparisons**: Mann-Whitney U + Holm-Bonferroni correction
- **Effect Sizes**: Cliff's delta with bootstrapped CIs
- **Inter-Rater Reliability**: Krippendorff's alpha for judge agreement

Configuration: `scylla/analysis/config.yaml` (all parameters externalized)

### Metrics

**Quality:**

- Pass-Rate (functional test coverage)
- Implementation Rate (semantic satisfaction)
- Score (weighted rubric evaluation)
- Consistency (1 - Coefficient of Variation)

**Economic:**

- Cost-of-Pass (expected cost per success)
- Frontier CoP (minimum CoP across configs)
- Token Distribution (cost breakdown)

**Process:**

- Latency (query to resolution time)
- Judge Agreement (Krippendorff's alpha)

### Data Requirements

Expected structure:

```
fullruns/{experiment_name}/{timestamp}/
├── config/experiment.json            # Metadata
└── T0-T6/{subtest_id}/run_{01-10}/
    ├── run_result.json              # Outcomes
    └── judge/judge_{01-03}/judgment.json  # Evaluations
```

**Required in run.json:**

- `run_number` (integer)
- `exit_code` (0 = success)
- `judges` (list with grades & criteria)

Schema: `scylla/analysis/schemas/run_result_schema.json`

---

## Development

### 🧪 Testing

ProjectScylla has a comprehensive test suite with **85+ test files** covering all functionality.

#### Test Categories

- **Unit Tests** (67+ files): Analysis, adapters, config, executors, judges, metrics, reporting
- **Integration Tests** (2 files): End-to-end workflow testing
- **E2E Tests** (1 file): Full pipeline validation
- **Test Fixtures** (47+ scenarios): Complete test cases with expected outputs

#### Running Tests

```bash
# All tests (comprehensive)
pixi run pytest tests/ --verbose

# Unit tests only (fastest)
pixi run pytest tests/unit/ -v

# Specific modules
pixi run pytest tests/unit/analysis/ -v
pixi run pytest tests/unit/adapters/ -v
pixi run pytest tests/unit/config/ -v

# Integration tests
pixi run pytest tests/integration/ -v

# Coverage analysis
pixi run pytest tests/ --cov=scylla/scylla --cov-report=html

# Specific test file
pixi run pytest tests/unit/analysis/test_stats.py -v
```

#### Test Quality Assurance

```bash
# Code quality (linting + formatting)
pixi run ruff check scylla/
pixi run ruff format scylla/ --check
```

### Adding Components

**New Figures:**

1. Create module in `scylla/analysis/figures/`
2. Implement function following existing pattern
3. Register in `scripts/generate_figures.py`
4. Add tests in `tests/unit/analysis/test_figures.py`

**New Tables:**

1. Add function to module in `scylla/analysis/tables/`
2. Register in `scripts/generate_tables.py`
3. Add tests in `tests/unit/analysis/test_tables.py`

### Code Quality

```bash
# Linting
pixi run ruff check scylla/analysis/

# Auto-fix and format
pixi run ruff check --fix scylla/analysis/
pixi run ruff format scylla/analysis/
```

---

## 🔧 Troubleshooting

### Quick Reference

| Symptom | Solution |
|---------|----------|
| `Schema validation failed: 'N/A' does not match` | Ensure grades are S, A, B, C, D, or F only |
| `[Errno 2] No such file or directory` | Run: `find ~/fullruns -name "run_result.json"` |
| `TypeError: unsupported operand` | Fix type coercion in criterion.achieved values |
| Empty outputs | Check: ≥2 experiments, ≥1 completed run each |
| Slow performance | Use `--no-render` flag for faster iteration |

### Common Issues

**1. Data Validation Errors**

```
Schema validation failed: 'N/A' does not match '^[SABCDF]$'
```

**Fix:** Review problematic runs, ensure valid grades S/A/B/C/D/F or update schema.

**2. Missing Files**

```
Failed to load: [Errno 2] No such file or directory
```

**Fix:** Incomplete runs skipped with warnings. Investigate:

```bash
find ~/fullruns -name "run_*" -type d -exec sh -c 'test -f "$1/run_result.json" || echo "Missing: $1"' _ {} \;
```

**3. Type Errors**

```
TypeError: unsupported operand type(s) for +: 'float' and 'str'
```

**Fix:** Some `criterion.achieved` are strings. Fix in data generation or add coercion.

### Getting Help

- **Documentation**: `docs/research.md` for methodology
- **Examples**: `tests/unit/analysis/` for usage patterns
- **Issues**: [GitHub Issues](https://github.com/HomericIntelligence/ProjectScylla/issues)
- **Support**: Create an issue with error message and steps to reproduce

---

## Publication Readiness

✅ **Rigorous non-parametric statistics** (Kruskal-Wallis, Mann-Whitney U, Cliff's delta)

✅ **Multiple comparison correction** (Holm-Bonferroni throughout)

✅ **Bootstrap confidence intervals** (BCa, 10K resamples, seed=42)

✅ **Effect sizes with confidence intervals**

✅ **300 DPI publication-quality figures**

✅ **LaTeX-ready tables** with booktabs formatting

✅ **Reproducible configuration** (all parameters in config.yaml)

✅ **Comprehensive test suite** (2026+ tests, all passing)

✅ **Documented methodology** with citations

See `docs/research.md` for complete research methodology and metric definitions.

### LaTeX Dependencies

Required packages for document compilation:

```latex
\documentclass{article}
 \usepackage{booktabs}   % Professional tables
 \usepackage{longtable}  % Multi-page tables
 \usepackage{threeparttable} % Table notes
 \usepackage{graphicx}   % Figure inclusion
 \usepackage{amsmath}    % Statistical symbols

\begin{document}
% Your content here
\end{document}
```

---

## 🤝 Contributing

We welcome contributions! Please see **[CONTRIBUTING.md](CONTRIBUTING.md)** for detailed guidelines on:

- Development setup and environment configuration
- Git workflow and branch management
- Code quality standards and testing requirements
- Pull request and code review process
- Issue reporting guidelines

**Quick Start for Contributors:**

1. Fork the repository and clone locally
2. Copy `.env.example` to `.env` and configure API keys
3. Install dependencies: `curl -fsSL https://pixi.sh/install.sh | bash`
4. Run tests: `pixi run pytest tests/ -v`
5. Check [CONTRIBUTING.md](CONTRIBUTING.md) for detailed workflow

**Areas for contribution:**

- Additional statistical methods and metrics
- New visualization types and formats
- Performance optimizations
- Documentation improvements
- Bug fixes and feature requests

Visit our [GitHub Repository](https://github.com/HomericIntelligence/ProjectScylla) to get started.

---

## License

[![License](https://img.shields.io/badge/license-BSD--3--Clause-blue.svg)](LICENSE)

## Citation

```bibtex
@software{projectscylla2026,
  title = {ProjectScylla: A Testing and Optimization Framework for Agentic Workflows},
  author = {Micah Villmow},
  year = {2026},
  url = {https://github.com/HomericIntelligence/ProjectScylla}
}
```
