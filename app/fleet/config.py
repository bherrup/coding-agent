import os
from pathlib import Path

# Limits and Timers
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", 2000000))
CONTEXT_THRESHOLD = 0.90
TIMEOUT_SECONDS = int(os.environ.get("AGENT_TIMEOUT", 1800))

# Paths
# Paths
WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", "/workspace"))
RESOURCES_ROOT = Path(os.environ.get("RESOURCES_ROOT", "/workspace"))
# Fallback for local development if /workspace doesn't exist
if not RESOURCES_ROOT.exists():
    RESOURCES_ROOT = Path(__file__).parent.parent.parent.resolve()

FLEET_CONFIG_PATH = Path(os.environ.get("FLEET_CONFIG_PATH", RESOURCES_ROOT / "fleet_config.json"))
if not FLEET_CONFIG_PATH.exists():
    # Graceful fallback to the example template for fresh deployments
    FLEET_CONFIG_PATH = RESOURCES_ROOT / "fleet_config.example.json"

SESSIONS_ROOT = Path(os.environ.get("SESSIONS_ROOT", WORKSPACE_ROOT / "sessions"))
ACTIVE_SESSIONS_ROOT = Path(os.environ.get("ACTIVE_SESSIONS_ROOT", "/tmp/fleet/sessions"))
DB_PATH = Path(os.environ.get("DB_PATH", WORKSPACE_ROOT / "fleet.db"))

def set_max_tokens(new_limit: int):
    global MAX_TOKENS
    MAX_TOKENS = new_limit
