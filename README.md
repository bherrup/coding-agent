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
    - `events.py`: Refactored event handling and Slack formatting.
    - `gemini_runner.py`: Gemini CLI execution and phase injection.
    - `slack_handlers.py`: Slack interaction and routing.
    - `utils.py`: Helper functions and error checking.
  - `pyproject.toml`: Modern Python project configuration (uv, ruff, pytest).
- `cdk/`: AWS CDK infrastructure for deploying the Fleet to AWS ECS.
- `scripts/`: Helper scripts for environment setup, Git worktree management, and container entrypoints.
- `fleet_config.json`: Configuration for supported Git repositories and specialized subagents.
- `prompts/`: External Markdown files containing system prompts for specialized subagents.
- `FLEET_AGENT.md`: Core directives and instructions for the Fleet's autonomous agents (renamed from `GEMINI.md`).

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

## Deployment (Google Cloud Platform)
The Fleet is deployed to Google Cloud Run via automated Cloud Build pipelines, utilizing Secret Manager for all sensitive credentials.

### GCP Setup Prerequisites
1. **Enable APIs:**
   ```bash
   gcloud services enable \
       run.googleapis.com \
       secretmanager.googleapis.com \
       cloudbuild.googleapis.com \
       artifactregistry.googleapis.com \
       file.googleapis.com \
       compute.googleapis.com
   ```
2. **Create Artifact Registry:**
   ```bash
   gcloud artifacts repositories create your-artifact-registry-repo --repository-format=docker --location=us-central1
   ```
3. **Create Filestore Instance (NFS):**
   ```bash
   gcloud filestore instances create fleet-filestore \
       --zone=us-central1-a \
       --tier=BASIC_HDD \
       --file-share=name="fleet_share",capacity=1TB \
       --network=name="default"
   
   # Retrieve and save the IP address of the new instance
   export FILESTORE_IP=$(gcloud filestore instances describe fleet-filestore --zone=us-central1-a --format="value(networks[0].ipAddresses[0])")
   ```
4. **Grant Permissions:**
   Grant the Cloud Build service account access to the artifact registry and logging:
   ```bash
   # Identify your project number
   export PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')

   # Grant Artifact Registry Writer (to allow Cloud Build to push the image)
   gcloud projects add-iam-policy-binding ${PROJECT_ID} \
       --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
       --role="roles/artifactregistry.writer"

   # Grant Logging Writer (to allow Cloud Build to write logs)
   gcloud projects add-iam-policy-binding ${PROJECT_ID} \
       --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
       --role="roles/logging.logWriter"

   # Grant Cloud Run Admin (to allow Cloud Build to deploy the service)
   gcloud projects add-iam-policy-binding ${PROJECT_ID} \
       --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
       --role="roles/run.admin"

   # Grant Service Account User (required for Cloud Build to act as the service account)
   gcloud projects add-iam-policy-binding ${PROJECT_ID} \
       --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
       --role="roles/iam.serviceAccountUser"

   # Grant Secret Manager Secret Accessor (so the service can read secrets at runtime)
   gcloud projects add-iam-policy-binding ${PROJECT_ID} \
       --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
       --role="roles/secretmanager.secretAccessor"
   ```
5. **Create Secrets:**
   Create the required secrets in Secret Manager. You can use the `google_secret_update` function we added to your shell:
   ```bash
   # Initialize the secret first (once per secret)
   gcloud secrets create SLACK_BOT_TOKEN
   
   # Use the helper to add the value
   google_secret_update SLACK_BOT_TOKEN "your-token-here"
   ```
6. **Deploy:**
   Trigger the build and deployment pipeline using Cloud Build, passing in the Filestore IP:
   ```bash
   gcloud builds submit --config cloudbuild.yaml --substitutions=_FILESTORE_IP=$FILESTORE_IP .
   ```

## Key Features
- **Maestro Subagents**: Dynamically configured specialized agents (e.g., Frontend, Backend, Infrastructure).
- **Fleet Protocol Enforcement**: Uses **Phase Injection** to ensure the Lead agent follows mandatory workflows, including the "STOP for approval" protocol after the planning phase.
- **Polished Tool Feedback**: A context-rich Slack notification system that summarizes tool actions (files, GitLab MRs, shell commands) with visual category indicators.
- **Quality Manifesto**: A standardized protocol where repositories define their own quality checks via `.fleet/quality.json` or `Makefile`, ensuring the Fleet follows repo-specific standards.
- **Isolated Worktrees**: Every session operates in a fresh Git worktree to prevent cross-session pollution.
- **Flexible Git Authentication**: Supports both SSH keys and Personal Access Tokens (HTTPS). Automatically translates SSH URLs to HTTPS if keys are missing but tokens are available.
- **Git CLI Integration**: Pre-authenticated `gh` and `glab` CLI tools for seamless repository operations.
- **Modern Python Stack**: Uses `uv` for package management, `ruff` for formatting, and `ty` for ultra-fast type checking.
