#!/bin/bash
set -e

# Setup SSH Key for Git operations
if [ -n "$SSH_PRIVATE_KEY" ]; then
    echo "🔑 Configuring SSH access..."
    mkdir -p ~/.ssh
    echo "$SSH_PRIVATE_KEY" > ~/.ssh/id_rsa
    chmod 600 ~/.ssh/id_rsa
    ssh-keyscan github.com gitlab.com >> ~/.ssh/known_hosts 2>/dev/null
    echo "✅ SSH configured."
fi

# Authenticate with GitHub CLI
if [ -n "$GITHUB_TOKEN" ]; then
    echo "🐙 Authenticating with GitHub CLI..."
    echo "$GITHUB_TOKEN" | gh auth login --with-token
    gh auth setup-git
    echo "✅ GitHub CLI authenticated."
fi

# Authenticate with GitLab CLI
if [ -n "$GITLAB_PAT" ]; then
    echo "🦊 Authenticating with GitLab CLI..."
    glab auth login --token "$GITLAB_PAT" --hostname ${GITLAB_URL:-gitlab.com}
    glab auth setup-git
    echo "✅ GitLab CLI authenticated."
fi

# Execute the application via uv
echo "🚀 Starting Fleet Agent..."
exec uv run python /home/agent/app/main.py
