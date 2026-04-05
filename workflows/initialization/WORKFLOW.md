# Initialization Workflow

Rigorous protocol for deliberate repository identification and workspace setup.

## Instructions
You MUST follow this workflow when you decide to research or modify code within a specific repository.

### 1. Semantic Repo Identification
- Read `fleet_config.json`.
- Match the user's request or the current task to the `description` of one of the available repositories.
- **Decision Point:** If no repository is a clear match, stop and ask the user for clarification.

### 2. State Identification
- Explicitly state which repository you have identified: "Target Repository: `<name>`".
- Briefly explain *why* this repo matches the task context.

### 3. Workspace Initialization
- Execute the initialization command: `bash scripts/init-worktree.sh <repo-name> [branch-name]`.
- Confirm the worktree was successfully created at `./local-workspace/worktrees/<repo-name>`.

### 4. Context Switch
- Change your working directory to the new worktree: `cd ./local-workspace/worktrees/<repo-name>`.
- Begin your research phase (e.g., `ls`, `grep`, `read_file`).
