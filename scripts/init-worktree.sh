#!/bin/bash
set -e

REPO_NAME=$1
BRANCH_NAME=${2:-main}

if [ -z "$REPO_NAME" ]; then
    echo "Usage: init-worktree <repo-name> [branch-name]"
    exit 1
fi

CONFIG_FILE="fleet_config.json"
REPOS_DIR="/workspace/repos"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: $CONFIG_FILE not found in current directory. Please run this script from a session directory where it is symlinked."
    exit 1
fi

# Extract repo URL and primary branch from fleet_config.json using python (to avoid jq dependency)
REPO_URL=$(python3 -c "import json; print(next((r['url'] for r in json.load(open('$CONFIG_FILE'))['repositories'] if r['name'] == '$REPO_NAME'), ''))")
PRIMARY_BRANCH=$(python3 -c "import json; print(next((r.get('primary_branch', 'main') for r in json.load(open('$CONFIG_FILE'))['repositories'] if r['name'] == '$REPO_NAME'), 'main'))")

if [ -z "$REPO_URL" ]; then
    echo "Error: Repository '$REPO_NAME' not found in $CONFIG_FILE."
    echo "Available repositories are:"
    python3 -c "import json; [print(f\" - {r['name']}\") for r in json.load(open('$CONFIG_FILE'))['repositories']]"
    echo "Action required: Please check fleet_config.json and try again with a valid repository name."
    exit 1
fi

# If no branch is provided, default to the primary branch
if [ -z "$2" ]; then
    BRANCH_NAME=$PRIMARY_BRANCH
fi

BARE_REPO="$REPOS_DIR/$REPO_NAME.git"
WORKTREE_PATH="$PWD/$REPO_NAME"

# Ensure repos directory exists
mkdir -p "$REPOS_DIR"

# Clone bare repository if missing
if [ ! -d "$BARE_REPO" ]; then
    echo "Cloning bare repository: $REPO_URL -> $BARE_REPO"
    git clone --bare "$REPO_URL" "$BARE_REPO"
else
    echo "Updating bare repository: $BARE_REPO"
    git -C "$BARE_REPO" fetch origin
fi

# Add worktree to current session directory
echo "Adding worktree: $BRANCH_NAME -> $WORKTREE_PATH"

# Check if branch exists, if not create it
if git -C "$BARE_REPO" rev-parse --verify "$BRANCH_NAME" >/dev/null 2>&1; then
    git -C "$BARE_REPO" worktree add "$WORKTREE_PATH" "$BRANCH_NAME"
else
    echo "Branch '$BRANCH_NAME' does not exist. Creating it from the primary branch '$PRIMARY_BRANCH'."
    git -C "$BARE_REPO" worktree add -b "$BRANCH_NAME" "$WORKTREE_PATH" "$PRIMARY_BRANCH"
fi

echo "Worktree initialized at $WORKTREE_PATH"
