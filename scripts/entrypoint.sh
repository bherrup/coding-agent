#!/bin/bash
set -e

# --- 1. INITIALIZATION ---
echo "🚀 Initializing Fleet Agent as '$(whoami)'..."

# Use /mnt/persistence if it exists and is writable, otherwise fall back to /workspace
BASE_DIR="/workspace"
if [ -d "/mnt/persistence" ] && [ -w "/mnt/persistence" ]; then
    BASE_DIR="/mnt/persistence"
fi

echo "📂 Using persistence directory: $BASE_DIR"
mkdir -p "$BASE_DIR/sessions" "$BASE_DIR/repos" "$BASE_DIR/data"

# --- 2. EXTENSION SETUP (Original Logic) ---
# Install Stitch Extension if not already installed (Keep existing functionality)
if ! gemini extensions list 2>&1 | grep -iq 'stitch'; then
    echo "🧵 Installing Stitch extension..."
    gemini extensions install https://github.com/gemini-cli-extensions/stitch --auto-update --consent
fi

if [ -n "$STITCH_API_KEY" ]; then
    echo "🔑 Configuring Stitch API key..."
    mkdir -p ~/.gemini/extensions/Stitch
    echo "{\"name\": \"Stitch\", \"api_key\": \"$STITCH_API_KEY\", \"version\": \"1.0.0\"}" > ~/.gemini/extensions/Stitch/gemini-extension.json
fi

# --- 3. GIT AUTHENTICATION ---
# Configure GitHub Token if provided
if [ -n "$GITHUB_TOKEN" ]; then
    echo "🐙 Configuring GitHub CLI..."
    gh auth setup-git
    git config --global url."https://github.com/".insteadOf git@github.com:
fi

# Configure GitLab Token if provided
GITLAB_TOKEN=${GITLAB_TOKEN:-$GITLAB_PAT}
if [ -n "$GITLAB_TOKEN" ]; then
    echo "🦊 Configuring GitLab CLI..."
    GITLAB_HOSTNAME="${GITLAB_URL:-gitlab.com}"
    GITLAB_HOSTNAME="${GITLAB_HOSTNAME#*://}"
    glab auth login --token "$GITLAB_TOKEN" --hostname "$GITLAB_HOSTNAME"
    git config --global credential."https://$GITLAB_HOSTNAME".helper "!glab auth git-credential"
    git config --global url."https://$GITLAB_HOSTNAME/".insteadOf git@$GITLAB_HOSTNAME:
fi

# --- 4. START APP ---
echo "🚀 Starting Fleet Agent app..."
cd /home/agent/app

# Run the app directly using the venv's python which is already in the PATH
exec python main.py
