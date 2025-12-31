# Dockerfile for scylla-runner:latest
# Base image for isolated AI agent test execution
#
# This image provides:
# - Python 3.10+ environment
# - Git and common build tools
# - Claude Code CLI for agent evaluation
# - Entry point for test execution

FROM python:3.10-slim

# Set labels for image metadata
LABEL org.opencontainers.image.title="scylla-runner"
LABEL org.opencontainers.image.description="AI agent testing and evaluation runner"
LABEL org.opencontainers.image.vendor="ProjectScylla"
LABEL org.opencontainers.image.version="latest"

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
# Note: nodejs is required for Claude Code CLI (npm package)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    make \
    curl \
    gcc \
    g++ \
    build-essential \
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

# Set up workspace directory
WORKDIR /workspace
RUN chown -R scylla:scylla /workspace

# Copy entry point script
COPY --chown=scylla:scylla entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Environment variables that containers receive at runtime
# These are documented but not set here - they're injected by the orchestrator
#
# TIER           - Test tier (T0, T1, T2, T3, T4, T5, T6)
# MODEL          - Model identifier (e.g., claude-sonnet-4-20250514)
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
