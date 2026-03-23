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
if [ -n "$GITHUB_TOKEN" ] || [ -n "$GH_TOKEN" ]; then
    echo "🐙 Configuring GitHub CLI..."
    # Ensure GH_TOKEN is set for the current process if only GITHUB_TOKEN is provided
    export GH_TOKEN=${GH_TOKEN:-$GITHUB_TOKEN}

    # Only run login if the token in the env doesn't already make us authenticated
    if ! gh auth status &>/dev/null; then
        echo "$GH_TOKEN" | gh auth login --with-token
    fi

    gh auth setup-git
    echo "✅ GitHub CLI configured."

    # If no SSH key is provided, rewrite GitHub SSH URLs to HTTPS to use the token
    if [ -z "$SSH_PRIVATE_KEY" ]; then
        echo "🔗 Configuring GitHub URL rewrite (SSH -> HTTPS)..."
        git config --global url."https://github.com/".insteadOf git@github.com:
    fi
fi

# Authenticate with GitLab CLI
if [ -n "$GITLAB_PAT" ]; then
    echo "🦊 Authenticating with GitLab CLI..."
    glab auth login --token "$GITLAB_PAT" --hostname ${GITLAB_URL:-gitlab.com}
    # glab doesn't have 'setup-git', we manually set the credential helper
    git config --global credential."https://${GITLAB_URL:-gitlab.com}".helper "!glab auth git-credential"
    echo "✅ GitLab CLI authenticated."

    # If no SSH key is provided, rewrite GitLab SSH URLs to HTTPS to use the PAT
    if [ -z "$SSH_PRIVATE_KEY" ]; then
        echo "🔗 Configuring GitLab URL rewrite (SSH -> HTTPS)..."
        git config --global url."https://${GITLAB_URL:-gitlab.com}/".insteadOf git@${GITLAB_URL:-gitlab.com}:
    fi
fi

# Install Stitch Extension if not already installed
if ! gemini extensions list | grep -q "Stitch"; then
    echo "🧵 Installing Stitch extension..."
    gemini extensions install https://github.com/gemini-cli-extensions/stitch --auto-update --consent
    
    # Configure API key if provided
    if [ -n "$STITCH_API_KEY" ]; then
        echo "🔑 Configuring Stitch API key..."
        sed "s/YOUR_API_KEY/$STITCH_API_KEY/g" ~/.gemini/extensions/Stitch/gemini-extension-apikey.json > ~/.gemini/extensions/Stitch/gemini-extension.json
    fi
fi

# Execute the application via uv
echo "🚀 Starting Fleet Agent..."
exec uv run python /home/agent/app/main.py
