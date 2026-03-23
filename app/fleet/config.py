import os
from pathlib import Path

# Limits and Timers
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", 2000000))
CONTEXT_THRESHOLD = 0.90
TIMEOUT_SECONDS = int(os.environ.get("AGENT_TIMEOUT", 1800))

# Paths
WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", "/workspace"))
SESSIONS_ROOT = WORKSPACE_ROOT / "sessions"
DB_PATH = WORKSPACE_ROOT / "fleet.db"

def set_max_tokens(new_limit: int):
    global MAX_TOKENS
    MAX_TOKENS = new_limit
