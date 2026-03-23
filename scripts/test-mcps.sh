#!/bin/bash
# DO NOT set -e here, we want to see all failures
set -x 

# Reset gemini config to a clean state
rm -rf ~/.gemini
mkdir -p ~/.gemini

echo "🔍 Generating current Gemini settings..."
# Run generator from app dir with a timeout
cd /home/agent/app
timeout 10s uv run python -c "from fleet import gemini_runner; gemini_runner.generate_gemini_settings()" || echo "❌ Settings generation timed out!"

echo -e "\n📄 Contents of ~/.gemini/settings.json (Tokens omitted):"
cat ~/.gemini/settings.json | sed -E 's/"(.*TOKEN.*)": ".*"/"\1": "[REDACTED]"/g; s/"(.*PAT.*)": ".*"/"\1": "[REDACTED]"/g; s/"(.*KEY.*)": ".*"/"\1": "[REDACTED]"/g'

echo -e "\n🔍 Testing Binaries Individually (Checking for immediate crashes)..."

echo "Testing GitLab..."
export GITLAB_TOKEN=$GITLAB_PAT
export GITLAB_PERSONAL_ACCESS_TOKEN=$GITLAB_PAT
export GITLAB_API_URL=$GITLAB_URL
timeout 5s mcp-gitlab --help || echo "GitLab exit code: $?"

echo "Testing Sentry..."
export SENTRY_ACCESS_TOKEN=$SENTRY_TOKEN
timeout 5s sentry-mcp --help || echo "Sentry exit code: $?"

echo "Testing Asana..."
export ASANA_ACCESS_TOKEN=$ASANA_PAT
timeout 5s mcp-server-asana --help || echo "Asana exit code: $?"

echo "Testing Stitch..."
export STITCH_API_KEY=$STITCH_API_KEY
export STITCH_PROJECT_ID=$STITCH_PROJECT_ID
timeout 5s stitch-mcp --help || echo "Stitch exit code: $?"

# Create a clean test directory
mkdir -p /workspace/mcp-test
cd /workspace/mcp-test

echo -e "\n📡 Checking Gemini MCP List..."
timeout 10s gemini mcp list || echo "⚠️ Gemini mcp list timed out."

echo -e "\n🛠️ Testing Discovery..."
timeout 15s gemini -p "list tools" --output-format text --raw-output 2>&1 | grep -iE "mcp|error|syntax|connected|disconnected" || echo "⚠️ Tool discovery timed out."

echo -e "\n✅ Diagnostic complete."