# Dockerfile for scylla-runner:latest
# Multi-stage build for reduced image size
#
# This image provides:
# - Python 3.10+ environment
# - Git and common build tools (runtime only)
# - Claude Code CLI for agent evaluation
# - Entry point for test execution

# ============================================================================
# Stage 1: Builder - Install Python packages with build dependencies
# ============================================================================
# Pinned to SHA256 digest for reproducibility - prevents drift from upstream updates
# Python 3.12 aligns with pyproject.toml classifiers (3.10-3.12); requires-python = ">=3.10"
FROM python:3.12-slim@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c AS builder

# Set build environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies (will NOT be in final image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Layer 1: Build backend (invalidated only when hatchling version changes)
# Pinned to match pyproject.toml [build-system].requires — see #1141
RUN pip install --no-cache-dir "hatchling==1.27.0"

# Layer 2: Dependencies (invalidated only when pyproject.toml changes or EXTRAS changes)
# Copy only pyproject.toml first so dependency installs are cached separately
# from source changes. Uses tomllib (stdlib since Python 3.11) to extract deps.
#
# Optional-dependency groups from [project.optional-dependencies] that are built
# into this layer when EXTRAS is set at build time:
#   analysis  — matplotlib, numpy, pandas, scipy, seaborn, altair, vl-convert-python, krippendorff
#   dev       — pytest, pytest-cov, pre-commit, ruff, defusedxml
#
# Usage:
#   docker build .                               # runtime deps only (default)
#   docker build --build-arg EXTRAS=analysis .   # + analysis group in cache layer
#   docker build --build-arg EXTRAS=analysis,dev .  # + both groups
ARG EXTRAS=""
COPY pyproject.toml /opt/scylla/
RUN pip install --user --no-cache-dir \
    $(python3 -c "
import tomllib, os
data = tomllib.load(open('/opt/scylla/pyproject.toml', 'rb'))
deps = list(data['project']['dependencies'])
opt = data['project'].get('optional-dependencies', {})
for group in [g.strip() for g in os.environ.get('EXTRAS', '').split(',') if g.strip()]:
    deps.extend(opt.get(group, []))
print(' '.join(deps))
" EXTRAS="$EXTRAS")

# Layer 3: Package install (invalidated when scylla/ source changes)
# Source-only changes hit cached layer 2 and only re-run this install step.
COPY README.md /opt/scylla/
COPY scylla/ /opt/scylla/scylla/
RUN pip install --user --no-cache-dir --no-deps /opt/scylla/

# ============================================================================
# Stage 2: Runtime - Minimal production image
# ============================================================================
# Pinned to SHA256 digest for reproducibility - prevents drift from upstream updates
# Python 3.12 aligns with pyproject.toml classifiers (3.10-3.12); requires-python = ">=3.10"
FROM python:3.12-slim@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c

# Set labels for image metadata
LABEL org.opencontainers.image.title="scylla-runner"
LABEL org.opencontainers.image.description="AI agent testing and evaluation runner"
LABEL org.opencontainers.image.vendor="ProjectScylla"
LABEL org.opencontainers.image.version="latest"

# Copy Python packages from builder stage to global location
COPY --from=builder /root/.local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /root/.local/bin /usr/local/bin

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/home/scylla \
    XDG_CONFIG_HOME=/home/scylla/.config \
    CLAUDE_CONFIG_DIR=/home/scylla/.claude

# Install ONLY runtime dependencies (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (required for Claude Code CLI)
# Using NodeSource repository for latest LTS version
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI (pinned to specific version for reproducibility)
# This is the primary tool for agent-based test execution
# Version 2.1.42 verified working in #601
# See: https://github.com/mvillmow/ProjectScylla/issues/650
RUN npm install -g @anthropic-ai/claude-code@2.1.42

# Create non-root user for security
RUN groupadd -r scylla && useradd -r -g scylla -m -s /bin/bash scylla

# Set up workspace directory (will be mounted at runtime with full project)
WORKDIR /workspace
RUN chown -R scylla:scylla /workspace

# Ensure clean Claude Code environment (no pre-existing config)
RUN rm -rf /home/scylla/.claude /home/scylla/.claude-plugin 2>/dev/null || true && \
    mkdir -p /home/scylla/.claude && \
    chown -R scylla:scylla /home/scylla/.claude

# Copy entry point script from docker/ subdirectory
COPY --chown=scylla:scylla docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Environment variables that containers receive at runtime
# These are documented but not set here - they're injected by the orchestrator
#
# TIER           - Test tier (T0, T1, T2, T3, T4, T5, T6)
# MODEL          - Model identifier (e.g., claude-sonnet-4-5-20250929)
# RUN_NUMBER     - Run number (1-9 for prompt sensitivity)
# ANTHROPIC_API_KEY - API key for Claude (passed from host)
# OPENAI_API_KEY    - API key for OpenAI models (if needed)
# TEST_ID        - Unique identifier for this test run
# TIMEOUT        - Maximum execution time in seconds

# Switch to non-root user
USER scylla

# Health check for container orchestration platforms
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c 'import scylla; print("OK")' || exit 1

# Default entry point
ENTRYPOINT ["/entrypoint.sh"]

# Default command (can be overridden)
CMD ["--help"]
