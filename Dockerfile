# Stage 1: Runtime Setup
FROM python:3.12-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    docker.io \
    procps \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install uv (modern package management)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install Gemini CLI and Maestro globally
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g @google/gemini-cli@latest

# Install gitlab-ci-local
RUN npm install -g gitlab-ci-local

# Install MCP Servers
RUN npm install -g @zereight/mcp-gitlab \
    @sentry/mcp-server \
    @roychri/mcp-server-asana

# Install GitHub CLI (gh)
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg && \
    chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null && \
    apt-get update && apt-get install -y gh

# Install GitLab CLI (glab)
RUN curl -fsSL https://packages.gitlab.com/install/repositories/gitlab/gitlab-explorer/script.deb.sh | bash && \
    apt-get update && apt-get install -y glab

# Create a non-root user
RUN groupadd -g 1001 agent && \
    useradd -u 1001 -g agent -m -s /bin/bash agent && \
    usermod -aG docker agent

# Workspace directory
WORKDIR /workspace
RUN chown -R agent:agent /workspace

# Setup agent environment
USER agent
ENV PATH="/home/agent/.local/bin:$PATH"

# Copy application and config files
COPY --chown=agent:agent app/ /home/agent/app/
COPY --chown=agent:agent fleet_config.json /workspace/fleet_config.json
COPY --chown=agent:agent prompts/ /workspace/prompts/
COPY --chown=agent:agent GEMINI.md /workspace/GEMINI.md
COPY --chown=agent:agent scripts/ /workspace/scripts/

# Setup repository cache directory
RUN mkdir -p /workspace/repos && chown -R agent:agent /workspace/repos

# Initialize Python environment via uv
WORKDIR /home/agent/app
RUN uv sync

# Set entrypoint
ENTRYPOINT ["/bin/bash", "/workspace/scripts/entrypoint.sh"]
