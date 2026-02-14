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
FROM python:3.14.2-slim AS builder

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

# Install Python build dependencies
RUN pip install --no-cache-dir hatchling

# Copy project files for building scylla package
COPY pyproject.toml /opt/scylla/
COPY README.md /opt/scylla/
COPY scylla/ /opt/scylla/scylla/

# Install scylla package to user directory (will be copied to runtime stage)
RUN pip install --user --no-cache-dir /opt/scylla/

# ============================================================================
# Stage 2: Runtime - Minimal production image
# ============================================================================
FROM python:3.14.2-slim

# Set labels for image metadata
LABEL org.opencontainers.image.title="scylla-runner"
LABEL org.opencontainers.image.description="AI agent testing and evaluation runner"
LABEL org.opencontainers.image.vendor="ProjectScylla"
LABEL org.opencontainers.image.version="latest"

# Copy Python packages from builder stage to global location
COPY --from=builder /root/.local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
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

# Install Claude Code CLI
# This is the primary tool for agent-based test execution
RUN npm install -g @anthropic-ai/claude-code

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

# Default entry point
ENTRYPOINT ["/entrypoint.sh"]

# Default command (can be overridden)
CMD ["--help"]
