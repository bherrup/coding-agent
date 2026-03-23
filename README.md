# Harmonized Engineering Fleet

Autonomous Engineering Fleet powered by Gemini CLI.

## Overview
The Harmonized Engineering Fleet is an autonomous agent system designed to handle software engineering tasks via Slack. It leverages the Gemini CLI and Maestro extension to orchestrate specialized subagents, manage Git repositories using isolated worktrees, and maintain high code quality standards.

## Project Structure
- `app/`: Python backend application (Slack Bolt).
  - `main.py`: Application entrypoint and orchestration.
  - `fleet/`: Core application package.
    - `config.py`: Centralized configuration and paths.
    - `database.py`: SQLite state management.
    - `gemini_runner.py`: Gemini CLI execution and event parsing.
    - `slack_handlers.py`: Slack interaction and routing.
    - `utils.py`: Helper functions and error checking.
  - `pyproject.toml`: Modern Python project configuration (uv, ruff, pytest).
- `cdk/`: AWS CDK infrastructure for deploying the Fleet to AWS ECS.
- `scripts/`: Helper scripts for environment setup, Git worktree management, and container entrypoints.
- `fleet_config.json`: Configuration for supported Git repositories and specialized subagents.
- `prompts/`: External Markdown files containing system prompts for specialized subagents.
- `GEMINI.md`: Core directives and instructions for the Fleet's autonomous agents.

## Development

### Prerequisites
- [uv](https://astral.sh/uv/)
- Docker
- Node.js (for Gemini CLI)

### Local Setup
1. Install dependencies:
   ```bash
   cd app && uv sync
   ```
2. Run tests:
   ```bash
   cd app && uv run pytest
   ```
3. Run linting and type checking:
   ```bash
   cd app && uv run ruff check . && uv run ty check
   ```

### Running Locally
1. Copy `.env.example` to `.env` and fill in the required tokens.
2. Start the Fleet via Docker Compose:
   ```bash
   docker-compose up --build
   ```

## Deployment
The Fleet is deployed using AWS CDK.

1. Install CDK dependencies:
   ```bash
   cd cdk && npm install
   ```
2. Deploy the infrastructure:
   ```bash
   cd cdk && npx cdk deploy --all
   ```

## Key Features
- **Maestro Subagents**: Dynamically configured specialized agents (e.g., Frontend, Backend, Infrastructure).
- **Isolated Worktrees**: Every session operates in a fresh Git worktree to prevent cross-session pollution.
- **Flexible Git Authentication**: Supports both SSH keys and Personal Access Tokens (HTTPS). Automatically translates SSH URLs to HTTPS if keys are missing but tokens are available.
- **Git CLI Integration**: Pre-authenticated `gh` and `glab` CLI tools for seamless repository operations.
- **Modern Python Stack**: Uses `uv` for package management, `ruff` for formatting, and `ty` for ultra-fast type checking.
