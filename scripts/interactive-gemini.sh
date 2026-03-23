#!/bin/bash
set -e

# Ensure gemini config directory exists
mkdir -p ~/.gemini

echo "🔍 Generating current Gemini settings..."
# We run this from the app directory so the python package is found
cd /home/agent/app
uv run python -c "from fleet import gemini_runner; gemini_runner.generate_gemini_settings()"

echo "🚀 Starting Gemini CLI in interactive mode..."
echo "Type '/mcp list' to verify servers or '/help' for commands."
echo "--------------------------------------------------------"

# Change to workspace root for the session
cd /workspace

# Start gemini. We use 'exec' so the script replaces itself with the gemini process.
exec gemini --yolo --include-directories /workspace
