import os
import json
import logging
import subprocess
import time
import shutil
from pathlib import Path
from . import config
from . import database
from . import utils
from .events import EventHandler

logger = logging.getLogger(__name__)

def generate_gemini_settings():
    """Dynamically generates the settings.json for Gemini CLI."""
    subagents = []
    config_path = config.FLEET_CONFIG_PATH
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config_data = json.load(f)
                subagents = config_data.get("subagents", [])
                
                for agent in subagents:
                    if "system_prompt_file" in agent:
                        prompt_path = config.RESOURCES_ROOT / agent.pop("system_prompt_file")
                        if prompt_path.exists():
                            with open(prompt_path, "r") as pf:
                                agent["system_prompt"] = pf.read()
                        else:
                            logger.warning(f"Prompt file not found: {prompt_path}")
                            agent["system_prompt"] = f"Warning: Prompt file {prompt_path.name} not found."
                            
                logger.info(f"Loaded {len(subagents)} subagents from {config_path}")
        except Exception as e:
            logger.error(f"Failed to load fleet_config.json: {e}")

    settings = {
        "mcpServers": {
            "gitlab": {
                "command": "bash",
                "args": [
                    "-c",
                    'mcp-gitlab | grep --line-buffered "^{"',
                ],
                "env": {
                    "GITLAB_TOKEN": os.environ.get("GITLAB_PAT", ""),
                    "GITLAB_PERSONAL_ACCESS_TOKEN": os.environ.get("GITLAB_PAT", ""),
                    "GITLAB_ACCESS_TOKEN": os.environ.get("GITLAB_PAT", ""),
                    "GITLAB_URL": os.environ.get("GITLAB_URL", "https://gitlab.com"),
                    "GITLAB_API_URL": os.environ.get("GITLAB_URL", "https://gitlab.com"),
                    "LOG_LEVEL": "error",
                    "NODE_ENV": "production",
                    "NODE_OPTIONS": "--no-warnings",
                    "DEBUG": "",
                },
                "trust": True,
            },
            "sentry": {
                "command": "bash",
                "args": [
                    "-c",
                    'sentry-mcp | grep --line-buffered "^{"',
                ],
                "env": {
                    "SENTRY_AUTH_TOKEN": os.environ.get("SENTRY_TOKEN", ""),
                    "SENTRY_ACCESS_TOKEN": os.environ.get("SENTRY_TOKEN", ""),
                    "LOG_LEVEL": "error",
                    "NODE_ENV": "production",
                    "NODE_OPTIONS": "--no-warnings",
                    "DEBUG": "",
                },
                "trust": True,
            },
            "asana": {
                "command": "bash",
                "args": [
                    "-c",
                    'mcp-server-asana | grep --line-buffered "^{"',
                ],
                "env": {
                    "ASANA_ACCESS_TOKEN": os.environ.get("ASANA_PAT", ""),
                    "ASANA_PERSONAL_ACCESS_TOKEN": os.environ.get("ASANA_PAT", ""),
                    "LOG_LEVEL": "error",
                    "NODE_ENV": "production",
                    "NODE_OPTIONS": "--no-warnings",
                    "DEBUG": "",
                },
                "trust": True,
            },
        },
        "extensions": {
            "maestro": {
                "subagents": subagents,
                "env": {
                    "GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN", ""),
                    "GH_TOKEN": os.environ.get("GH_TOKEN", ""),
                }
            }
        }
    }
    
    settings_dir = Path.home() / ".gemini"
    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_path = settings_dir / "settings.json"
    
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=4)
    
    # Attempt to chown if running as root (e.g. in container startup)
    if os.getuid() == 0:
        try:
            shutil.chown(str(settings_dir), user="agent", group="agent")
            shutil.chown(str(settings_path), user="agent", group="agent")
        except Exception as e:
            logger.warning(f"Failed to chown settings: {e}")
    
    logger.info(f"Gemini settings generated at {settings_path}")


def process_task(session_id, thread_ts, channel, clean_text, say, active_tasks):
    """Worker function executed inside the ThreadPoolExecutor."""
    # HISTORICAL PATH (Persistence)
    persistent_session_dir = config.SESSIONS_ROOT / session_id
    persistent_session_dir.mkdir(parents=True, exist_ok=True)
    
    # ACTIVE PATH (Execution - can be /tmp or Filestore)
    active_session_dir = config.ACTIVE_SESSIONS_ROOT / session_id
    active_session_dir.mkdir(parents=True, exist_ok=True)
    
    # Critical: Ensure agent has access if running as root
    try:
        if os.getuid() == 0:
            shutil.chown(str(config.ACTIVE_SESSIONS_ROOT), user="agent", group="agent")
    except Exception:
        pass

    # If resuming, ensure the active directory is populated from the persistent history
    # This is only needed if working on separate filesystems. If both are on Filestore, 
    # we could optimize further, but this remains robust.
    is_resuming = (persistent_session_dir / ".gemini").exists()
    if is_resuming and not (active_session_dir / ".gemini").exists():
        logger.info(f"🔄 Resuming session {session_id}: syncing history -> active")
        for item in persistent_session_dir.iterdir():
            try:
                target = active_session_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, target)
            except Exception as e:
                logger.error(f"Failed to sync {item.name} from history: {e}")
    else:
        logger.info(f"🆕 Initializing session {session_id}")

    # Copy shared resources (Strategy Context)
    shared_resources = ["fleet_config.json", "scripts", "prompts", ".gemini", "workflows"]
    for resource in shared_resources:
        source = config.RESOURCES_ROOT / resource
        target = active_session_dir / resource
        if source.exists() and not target.exists():
            try:
                if source.is_dir():
                    shutil.copytree(source, target)
                else:
                    shutil.copy2(source, target)
            except Exception as e:
                logger.error(f"Failed to copy {resource}: {e}")

    # Special handling for Tech Lead System Prompt (GEMINI.md)
    system_prompt_source = config.RESOURCES_ROOT / "GEMINI.md"
    if not system_prompt_source.exists():
        system_prompt_source = config.RESOURCES_ROOT / "FLEET_AGENT.md"

    if system_prompt_source.exists():
        try:
            shutil.copy2(system_prompt_source, active_session_dir / "GEMINI.md")
        except Exception as e:
            logger.error(f"Failed to copy system prompt: {e}")

    say(f"🚀 Fleet Agent processing in session: `{session_id}`...", thread_ts=thread_ts)
    database.update_session_status(session_id, "running")
    start_time = time.time()
    
    # Check for API Key early
    if not os.environ.get("GEMINI_API_KEY"):
        say("❌ **ERROR:** `GEMINI_API_KEY` is not set. Please check your Secret Manager configuration.", thread_ts=thread_ts)
        database.update_session_status(session_id, "error")
        return

    try:
        gemini_bin = shutil.which("gemini") or "/usr/local/bin/gemini"
        
        # 6. Apply Phase Injection (Fleet Protocol Enforcement)
        approval_type, explanation = utils.check_approval(clean_text)
        
        # Persist approval if granted
        if approval_type == 'unconditional':
            database.update_session_state(session_id, approval_status='APPROVED')
        
        # Fetch current state for resumption context
        current_phase, approval_status = database.get_session_state(session_id)
        
        context_prefix = ""
        if not is_resuming:
            context_prefix = (
                "[PHASE_INJECTION: INITIALIZATION] This is a new session. Follow the Fleet Protocol "
                "in GEMINI.md. Perform research, consult specialists, and provide a structured "
                "implementation plan. CRITICAL: You MUST stop and wait for explicit approval "
                "after proposing the plan. DO NOT EXECUTE yet.\n\n"
            )
        elif approval_status == 'APPROVED':
            context_prefix = (
                f"[PHASE_INJECTION: RESUMPTION] You were in the {current_phase} phase with "
                "UNCONDITIONAL APPROVAL from the user. Continue your implementation immediately. "
                "Audit the current workspace to resume from your last known state.\n\n"
            )
        elif approval_type == 'unconditional':
            context_prefix = (
                "[PHASE_INJECTION: UNCONDITIONAL_APPROVAL] The user has approved your plan. "
                "Transition to the EXECUTION Phase immediately and begin implementation.\n\n"
            )
        elif approval_type == 'conditional':
            context_prefix = (
                f"[PHASE_INJECTION: CONDITIONAL_APPROVAL] {explanation} "
                "Acknowledge the feedback, refine your plan, and then proceed directly to the EXECUTION Phase.\n\n"
            )
        elif is_resuming:
            context_prefix = (
                f"[PHASE_INJECTION: RESUMPTION] You were in the {current_phase} phase. "
                "Review the conversation history and your progress. Ensure you have explicit approval "
                "before starting any execution tasks.\n\n"
            )
        else:
            context_prefix = (
                "[PHASE_INJECTION: CONTINUITY] The user is providing additional feedback or clarification. "
                "Continue the current phase (Research or Planning). Ensure you have explicit approval "
                "before starting any execution tasks.\n\n"
            )
        
        final_prompt = f"{context_prefix}{clean_text}"
        
        # EXECUTE in the active session directory
        cmd = [
            gemini_bin, 
            "--yolo", 
            "--include-directories", ".", 
            "--output-format", "stream-json"
        ]
        
        if is_resuming:
            cmd += ["--resume", "latest"]
            
        # 7. Execute Gemini Command
        cmd += ["-p", final_prompt]
        
        logger.info(f"Executing Gemini command (Resuming: {is_resuming}): {' '.join(cmd)}")

        # Ensure environment is passed correctly
        env = os.environ.copy()
        env["GEMINI_FORCE_FILE_STORAGE"] = "true"
        env["FLEET_SESSION_STATUS"] = "resuming" if is_resuming else "new"
        # Promote system prompt to primary System Prompt using absolute path
        env["GEMINI_SYSTEM_MD"] = str(active_session_dir / "GEMINI.md")


        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(active_session_dir),
            env=env,
            start_new_session=True
        )
        
        active_tasks[session_id] = {
            "process": process,
            "channel": channel,
            "thread_ts": thread_ts,
            "session_id": session_id
        }
        
        handler = EventHandler(say, thread_ts, session_id)
        error_detected = None
        
        # ACTIVE OUTPUT DRAINING
        while True:
            if process.stdout:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                
                line_strip = line.strip()
                if not line_strip:
                    continue
                
                if not line_strip.startswith("{"):
                    logger.info(f"CLI Raw: {line_strip}")
                    if any(kw in line_strip for kw in ["Executing ", "Delegating to "]):
                        if "MCP context refresh" not in line_strip:
                            if not any(prefix in line_strip for prefix in ["🛠️", "🤖", "🐚", "📂", "📁", "🦊"]):
                                say(f"💭 **Status:** `{line_strip}`", thread_ts=thread_ts)
                        
                    detected = utils.check_for_errors(line_strip)
                    if detected:
                        error_detected = detected
                    continue

                try:
                    event_data = json.loads(line_strip)
                    if handler.handle_event(event_data):
                        process.terminate()
                        break
                except json.JSONDecodeError:
                    continue

            if time.time() - start_time > config.TIMEOUT_SECONDS:
                say(f"🛑 **TIMEOUT: Subagent exceeded {config.TIMEOUT_SECONDS}s.** Terminating.", thread_ts=thread_ts)
                process.terminate()
                break
                
        process.wait()
        
        # SYNC RESULTS to History (Persistence)
        # Only sync if they are on different filesystems or we want to maintain a clean history
        if str(active_session_dir) != str(persistent_session_dir):
            logger.info(f"Syncing results to history: {active_session_dir} -> {persistent_session_dir}")
            for item in active_session_dir.iterdir():
                if item.is_symlink() and item.name in shared_resources:
                    continue
                try:
                    if item.is_dir():
                        shutil.copytree(item, persistent_session_dir / item.name, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, persistent_session_dir / item.name)
                except Exception as e:
                    logger.error(f"Failed to sync {item.name} to history: {e}")

        # CLEANUP active session dir
        try:
            logger.info(f"🧹 Cleaning up active session dir: {active_session_dir}")
            shutil.rmtree(active_session_dir)
        except Exception as e:
            logger.error(f"Failed to cleanup {active_session_dir}: {e}")

        if session_id in active_tasks:
            del active_tasks[session_id]
            
        final_usage_msg = ""
        if handler.last_usage:
            final_usage_msg = f"\n\n📊 **Context Usage:** {handler.last_usage:,} / {config.MAX_TOKENS:,} tokens"
        
        # Any remaining thought after the final tool call is the actual final response
        handler.flush_final_response()
            
        if error_detected:
            database.update_session_status(session_id, "error")
            say(error_detected, thread_ts=thread_ts)
        else:
            database.update_session_status(session_id, "completed")
            say(f"✅ Execution Finished.{final_usage_msg}", thread_ts=thread_ts)
            
    except Exception as e:
        logger.error(f"Error executing gemini in {session_id}: {e}")
        say(f"❌ Error: {e}", thread_ts=thread_ts)
        database.update_session_status(session_id, "error")
        if session_id in active_tasks:
            del active_tasks[session_id]
