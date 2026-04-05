#!/bin/bash
# 🚀 Fleet Shell: Interactive Gemini "Tech Lead" Session (Slack-Free)
set -e

# 1. Path Resolution
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Try to find the app directory
if [ -d "${PROJECT_ROOT}/app" ]; then
    APP_DIR="${PROJECT_ROOT}/app"
elif [ -d "/home/agent/app" ]; then
    APP_DIR="/home/agent/app"
else
    echo "❌ Error: Could not find 'app' directory."
    exit 1
fi

# 2. ENV Setup: Use current dir as the workspace root for local runs
export WORKSPACE_ROOT="${PROJECT_ROOT}"
export SESSIONS_ROOT="${WORKSPACE_ROOT}/local-workspace/sessions"
export SESSION_ID="local-$(date +%s)"
export LOCAL_SESSION_DIR="${SESSIONS_ROOT}/${SESSION_ID}"

# 3. Workspace Initialization
mkdir -p "${LOCAL_SESSION_DIR}"
echo "📁 Initializing session: ${LOCAL_SESSION_DIR}"

# 4. Copy Fleet Resources (Copying instead of symlinking for sandbox compatibility)
echo "📂 Copying Fleet context and skills..."
resources=("GEMINI.md" "FLEET_AGENT.md" "fleet_config.json" "prompts" "scripts" ".gemini")
for res in "${resources[@]}"; do
    if [ -e "${PROJECT_ROOT}/${res}" ]; then
        # Use -r for directories and -L to follow symlinks if they exist in the root
        cp -rL "${PROJECT_ROOT}/${res}" "${LOCAL_SESSION_DIR}/${res}"
    fi
done

# Ensure GEMINI.md exists in the session (copied from FLEET_AGENT.md if missing)
if [ ! -f "${LOCAL_SESSION_DIR}/GEMINI.md" ] && [ -f "${PROJECT_ROOT}/FLEET_AGENT.md" ]; then
    cp "${PROJECT_ROOT}/FLEET_AGENT.md" "${LOCAL_SESSION_DIR}/GEMINI.md"
fi

# 5. Generate Gemini Settings
echo "🔍 Generating Fleet settings.json..."
cd "${APP_DIR}"
# Temporarily set up the paths for the python script
export WORKSPACE_ROOT="${PROJECT_ROOT}"
uv run python -c "from fleet import gemini_runner; gemini_runner.generate_gemini_settings()"

# 6. Launch Gemini Tech Lead Session
echo "--------------------------------------------------------"
echo "🤖 Entering Fleet Tech Lead Mode (Session ID: ${SESSION_ID})"
echo "Type '/mcp list' to verify servers or '/help' for commands."
echo "--------------------------------------------------------"

cd "${LOCAL_SESSION_DIR}"

# Point to GEMINI.md as the system prompt for higher priority
export GEMINI_SYSTEM_MD="GEMINI.md"

# Launch gemini in interactive mode
# We include the PROJECT_ROOT just in case, but real work happens in '.'
exec gemini --yolo --include-directories .
