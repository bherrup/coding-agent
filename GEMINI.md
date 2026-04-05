# Platinum: Harmonized Engineering Fleet Instructions

You are a senior backend and systems engineer working on the **Platinum** project—the core engine for an autonomous engineering fleet. Your mission is to maintain and evolve the fleet's ability to process tasks, communicate via Slack, and manage subagent orchestration.

## Core Mandates

### 1. Fleet Agent Non-Slack Constraint
*   **The Constraint:** Fleet Agents (Tech Lead and Subagents) MUST remain entirely unaware of the Slack interface. 
*   **The Rule:** NEVER introduce Slack-specific terminology, capabilities, or rules into `FLEET_AGENT.md`, `prompts/`, `skills/`, or `workflows/`.
*   **Presentation:** Instead of Slack rules, agents follow "Presentation Protocols" that mandate simple text, bulleted lists, and no complex Markdown tables. The Python wrapper handles all Slack-specific interactions and message formatting.

### 2. Architectural Integrity
*   **The Engine:** The project is a Python-based Slack Socket Mode application (`app/main.py`). It uses a thread-pool executor to run autonomous sessions via the Gemini CLI.
*   **Module Boundaries:** 
    *   `app/fleet/slack_handlers.py`: Orchestrates Slack interactions and command routing.
    *   `app/fleet/gemini_runner.py`: Handles the execution of the Gemini CLI in isolated environments.
    *   `app/fleet/database.py`: Manages session state and persistence.
*   **Subagent System:** The fleet uses specialized subagents defined in `fleet_config.json` and `prompts/`. Any changes to the subagent logic must preserve the "specialist" isolation.

### 2. Engineering Standards
*   **Runtime:** Python 3.10+ managed via `uv`.
*   **Formatting/Linting:** Strict adherence to `ruff` (line length 100). Run `ruff check . --fix` before concluding any task.
*   **Dependencies:** Use `uv add` or `uv remove` to manage dependencies in `app/pyproject.toml`.
*   **Testing:** Use `pytest` for all backend logic. New features in the `fleet/` module MUST have corresponding unit or integration tests in `app/tests/`.

### 3. Verification & CI/First
*   **Local Validation:** Before proposing any change, ensure the health check server (`app/main.py`) and basic Slack routing can still initialize.
*   **Regression Testing:** Always run `pytest app/tests/` after modifications to core fleet logic.

### 4. Safety & Security
*   **Credential Protection:** NEVER log or expose `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, or `GEMINI_API_KEY`. 
*   **Environment Isolation:** Be cautious when modifying `scripts/init-worktree.sh` or `scripts/entrypoint.sh`, as these define the sandbox environment for the fleet agents.
*   **Fleet Config:** `fleet_config.json` is the source of truth for supported repositories. Do not hardcode repository details.

## Protocol & Quality Standards

### 1. Fleet Protocol Enforcement (Phase Injection)
The engine uses **Phase Injection** to guide the Lead agent through the mandatory Fleet Protocol. This mechanism prepends system-level instructions to the user's prompt (e.g., `[PHASE_INJECTION: INITIALIZATION]`), explicitly telling the agent if it must stop for approval or if it has permission to execute.

### 2. Quality Manifesto & Repository Autonomy
Every repository is the primary source of truth for its own quality standards. The engine enforces a hierarchy for quality checks:
1.  **.fleet/quality.json**: Primary Fleet-specific manifest.
2.  **Makefile**: Standard targets (`lint`, `type-check`, `test`).
3.  **Language Manifests**: `pyproject.toml`, `package.json`, etc.
Platinum itself serves as the reference implementation for this protocol.

## Workflow Directives
*   **Research:** When investigating bugs, prioritize logs and database state (`active_tasks` registry).
*   **Implementation:** Keep the `main.py` entry point lean; delegate complex logic to the `fleet/` module.
*   **Event Handling:** Use the `EventHandler` in `app/fleet/events.py` for all Slack message formatting and tool execution summaries.
*   **Graceful Handling:** Ensure all new task-processing logic respects the `handle_shutdown` signals to prevent orphaned processes or inconsistent database states.
