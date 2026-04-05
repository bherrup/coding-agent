# Architecture Decision Records

## 1. Built-in Health Check Server for Kubernetes
**Date:** 2026-04-05
**Status:** Accepted

### Decision
A built-in HTTP server listening on the defined `PORT` (default `8080`) has been added inside `app/main.py`. It returns `{"status": "healthy"}` for root path queries (`/`).

### Context
When running within Kubernetes (GKE Autopilot) or Cloud Run, the orchestrator depends heavily on liveness and readiness probes to maintain high availability. Previously, the Socket Mode Slack connection was the only indicator of "health," which made it difficult to natively load-balance or self-heal containers. The isolated HTTP thread directly satisfies container lifecycle bounds without interfering with Slack processing.

---

## 2. Strict Graceful Lifecycle Interruptions (SIGINT)
**Date:** 2026-04-05
**Status:** Accepted

### Decision
When the host signals `SIGTERM` or `SIGINT` to the agent, the backend intercepts this and issues a `SIGINT` cascade to active background threads (specifically `Gemini CLI`). 

### Context
During regular system restarts or K8s rolling updates, simply calling `.terminate()` was causing hard crashes in the agent's context engines. Emitting a robust `SIGINT` allows the CLI tooling to execute a graceful dump of state-files or history dumps. As part of this enhancement, `fleet/database.py` was extended to track `phase` and `approval` state. Slack notifications gracefully inform end-users that an interrupt has occurred, retaining full session IDs and context for continuation upon spin-up.

---

## 3. Ephemeral Storage Bounds (Purge Active Sessions)
**Date:** 2026-04-05
**Status:** Accepted

### Decision
Upon application initialization inside `app/main.py`, the system aggressively triggers a purge of `/active_sessions` directories. 

### Context
Kubernetes configurations rely on Persistent Volume Claims (ReadWriteOnce) to bridge long-running Gemini instances against abrupt pod termination. However, because each chat initializes robust `git worktrees` inside the `/mnt/persistence/active_sessions` paths, these rapidly expand and exhaust storage quotas (e.g. 50Gi capacity). By automatically triggering cleanup for stranded state trees upon daemon initialization `utils.purge_active_sessions()`, we effectively sidestep file leakage problems completely.
