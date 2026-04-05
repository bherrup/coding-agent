#!/bin/bash
# 🚀 Fleet Worktree: Isolated Workspace Initialization
set -e

REPO_NAME=$1
REQUESTED_BRANCH=$2

if [ -z "$REPO_NAME" ]; then
    echo "Usage: init-worktree <repo-name> [branch-name]"
    exit 1
fi

# 1. Path Resolution
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# Bare repositories should be persistent to avoid re-cloning
BARE_REPOS_ROOT="${WORKSPACE_ROOT:-$PROJECT_ROOT}/local-workspace/repos"
mkdir -p "$BARE_REPOS_ROOT"

# Worktrees should be local to the current session directory for speed and cleanup
# Resolve to ABSOLUTE path to prevent ambiguity with git -C
SESSION_DIR="$(pwd)"
WORKTREE_PATH="${SESSION_DIR}/local-workspace/worktrees/$REPO_NAME"
mkdir -p "${SESSION_DIR}/local-workspace/worktrees"

CONFIG_FILE=${FLEET_CONFIG_PATH:-"${RESOURCES_ROOT:-$PROJECT_ROOT}/fleet_config.json"}
if [ ! -f "$CONFIG_FILE" ]; then
    CONFIG_FILE="${RESOURCES_ROOT:-$PROJECT_ROOT}/fleet_config.example.json"
fi

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Error: $CONFIG_FILE not found."
    exit 1
fi

# 2. Extract repo metadata
REPO_URL=$(python3 -c "import json; print(next((r['url'] for r in json.load(open('$CONFIG_FILE'))['repositories'] if r['name'] == '$REPO_NAME'), ''))")
PLATFORM=$(python3 -c "import json; print(next((r.get('platform', 'gitlab') for r in json.load(open('$CONFIG_FILE'))['repositories'] if r['name'] == '$REPO_NAME'), 'gitlab'))")
PRIMARY_BRANCH=$(python3 -c "import json; print(next((r.get('primary_branch', 'main') for r in json.load(open('$CONFIG_FILE'))['repositories'] if r['name'] == '$REPO_NAME'), 'main'))")

if [ -z "$REPO_URL" ]; then
    echo "❌ Error: Repository '$REPO_NAME' not found in $CONFIG_FILE."
    exit 1
fi

# Use the requested branch or fallback to primary branch
BRANCH_NAME=${REQUESTED_BRANCH:-$PRIMARY_BRANCH}

# 3. Authentication Setup (HTTPS/PAT)
# Prefer GITLAB_PAT or GITLAB_TOKEN
GITLAB_TOKEN=${GITLAB_TOKEN:-$GITLAB_PAT}
export GITLAB_TOKEN

BARE_REPO="$BARE_REPOS_ROOT/$REPO_NAME.git"

# 4. Clone/Update bare repository
if [ ! -d "$BARE_REPO" ]; then
    echo "🌐 Cloning bare repository: $REPO_URL -> $BARE_REPO"
    
    # Use glab for GitLab repos if possible
    if [ "$PLATFORM" == "gitlab" ] && command -v glab &> /dev/null && [ -n "$GITLAB_TOKEN" ]; then
        glab repo clone "$REPO_URL" "$BARE_REPO" -- --bare
    else
        # Fallback to standard git with token injection for HTTPS
        AUTH_URL=$REPO_URL
        if [[ "$REPO_URL" == https://* ]] && [ -n "$GITLAB_TOKEN" ]; then
            # Inject token: https://oauth2:TOKEN@gitlab.com/...
            AUTH_URL=$(echo "$REPO_URL" | sed "s|https://|https://oauth2:${GITLAB_TOKEN}@|")
        fi
        git clone --bare "$AUTH_URL" "$BARE_REPO"
    fi
else
    echo "🔄 Updating bare repository: $BARE_REPO"
    
    # Update remote URL if token changed or for consistency
    if [[ "$REPO_URL" == https://* ]] && [ -n "$GITLAB_TOKEN" ]; then
        AUTH_URL=$(echo "$REPO_URL" | sed "s|https://|https://oauth2:${GITLAB_TOKEN}@|")
        git -C "$BARE_REPO" remote set-url origin "$AUTH_URL"
    fi
    
    git -C "$BARE_REPO" fetch origin
fi

# 5. Add worktree
echo "🌿 Initializing worktree: $BRANCH_NAME -> $WORKTREE_PATH (Status: ${FLEET_SESSION_STATUS:-new})"

# RESUMPTION CHECK: If this is a resumed session, check if the worktree already exists and is valid.
if [ "$FLEET_SESSION_STATUS" == "resuming" ]; then
    if [ -d "$WORKTREE_PATH/.git" ]; then
        # Verify it belongs to our bare repo
        ACTUAL_BARE=$(git -C "$WORKTREE_PATH" rev-parse --git-common-dir 2>/dev/null || true)
        # BARE_REPO is absolute, ACTUAL_BARE might be relative or absolute depending on git version
        # We do a loose check to see if they refer to the same place
        if [ -n "$ACTUAL_BARE" ]; then
            echo "✅ Valid existing worktree found for resumed session. Preserving state."
            exit 0
        fi
    fi
    echo "⚠️ Resumed session but no valid worktree found. Initializing fresh..."
fi

# Remove existing worktree directory if it exists (for fresh starts or corrupted resumes)
if [ -d "$WORKTREE_PATH" ]; then
    rm -rf "$WORKTREE_PATH"
fi

# CRITICAL: Prune stale worktree metadata from bare repo
git -C "$BARE_REPO" worktree prune

# Use detached HEAD (--detach) to allow concurrent sessions on the same branch.
if git -C "$BARE_REPO" rev-parse --verify "$BRANCH_NAME" >/dev/null 2>&1; then
    git -C "$BARE_REPO" worktree add --detach "$WORKTREE_PATH" "$BRANCH_NAME"
else
    echo "🌿 Branch '$BRANCH_NAME' does not exist. Creating worktree from '$PRIMARY_BRANCH'."
    git -C "$BARE_REPO" worktree add --detach "$WORKTREE_PATH" "$PRIMARY_BRANCH"
fi

echo "✅ Worktree initialized at: $WORKTREE_PATH"
