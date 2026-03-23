import os
import json
import logging
import subprocess
import time
from pathlib import Path
from . import config
from . import database
from . import utils

logger = logging.getLogger(__name__)

def generate_gemini_settings():
    """Dynamically generates the settings.json for Gemini CLI."""
    subagents = []
    config_path = config.WORKSPACE_ROOT / "fleet_config.json"
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config_data = json.load(f)
                subagents = config_data.get("subagents", [])
                
                for agent in subagents:
                    if "system_prompt_file" in agent:
                        prompt_path = config.WORKSPACE_ROOT / agent.pop("system_prompt_file")
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
                "type": "http",
                "url": f"{os.environ.get('GITLAB_URL', 'https://gitlab.com').rstrip('/')}/api/v4/mcp"
            },
            "sentry": {
                "command": "bash",
                "args": [
                    "-c",
                    f'sentry-mcp --access-token={os.environ.get("SENTRY_TOKEN", "")} --organization-slug={os.environ.get("SENTRY_ORG", "")} --project-slug={os.environ.get("SENTRY_PROJECTS", "")} | grep --line-buffered "^\\{{"',
                ],
                "env": {
                    "SENTRY_AUTH_TOKEN": os.environ.get("SENTRY_TOKEN", ""),
                    "SENTRY_ACCESS_TOKEN": os.environ.get("SENTRY_TOKEN", ""),
                    "SENTRY_ORG": os.environ.get("SENTRY_ORG", ""),
                    "SENTRY_PROJECT": os.environ.get("SENTRY_PROJECTS", ""),
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
    
    logger.info(f"Gemini settings generated at {settings_path}")

def process_task(session_id, thread_ts, channel, clean_text, say, active_tasks):
    """Worker function executed inside the ThreadPoolExecutor."""
    session_dir = config.SESSIONS_ROOT / session_id
    
    # Symlink shared resources
    shared_resources = ["GEMINI.md", "fleet_config.json", "prompts", "scripts"]
    for resource in shared_resources:
        source = config.WORKSPACE_ROOT / resource
        target = session_dir / resource
        if source.exists() and not target.exists():
            try:
                target.symlink_to(source)
            except Exception as e:
                logger.error(f"Failed to symlink {resource}: {e}")
                
    say(f"🚀 Fleet Agent processing in session: `{session_id}`...", thread_ts=thread_ts)
    database.update_session_status(session_id, "running")
    start_time = time.time()
    
    try:
        cmd = ["gemini", "--yolo", "--include-directories", str(config.WORKSPACE_ROOT), "--output-format", "stream-json"]
        
        is_resuming = (session_dir / ".gemini").exists()
        if is_resuming:
            cmd += ["--resume", "latest"]
        
        # Enhance continuation prompts to maintain Tech Lead context
        final_prompt = clean_text
        if is_resuming and clean_text.lower() in ["go", "approved", "approve", "proceed"]:
            final_prompt = (
                f"User: {clean_text}. \n\n"
                "System: The user has approved your plan. You are now in the EXECUTION PHASE. "
                "Do NOT restart research. Follow the Execution Phase protocol strictly:\n"
                "1. Verify or create an Asana task in the configured 'asana_project' for this repository. When identifying the ticket number, first check for a custom field with a type of 'id'. If it exists, use that; otherwise, use the internal Asana Task GID.\n"
                "2. Create a branch formatted as '<type>/<ticket_number>-<slug>' off the configured primary branch.\n"
                "3. Delegate implementation to specialists and commit early and often.\n"
                "4. When done, use the git-specialist to create the Merge Request."
            )
            
        cmd.append(final_prompt)
        logger.info(f"Executing Gemini command: {' '.join(cmd)} in CWD: {session_dir}")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(session_dir),
            start_new_session=True
        )
        
        active_tasks[session_id] = {
            "process": process,
            "channel": channel,
            "thread_ts": thread_ts,
            "session_id": session_id
        }
        
        full_response = ""
        last_usage = None
        error_detected = None
        
        if process.stdout:
            for line in process.stdout:
                line_strip = line.strip()
                if not line_strip:
                    continue
                
                # Check for CLI errors and progress in non-JSON output
                if not line_strip.startswith("{"):
                    logger.info(f"CLI Raw: {line_strip}")
                    if any(kw in line_strip for kw in ["Executing ", "Delegating to "]):
                        if not any(prefix in line_strip for prefix in ["🛠️", "🤖"]):
                            say(f"💭 **Status:** `{line_strip}`", thread_ts=thread_ts)
                        
                    detected = utils.check_for_errors(line_strip)
                    if detected:
                        error_detected = detected
                    continue

                try:
                    event_data = json.loads(line_strip)
                    event_type = event_data.get("type")
                    
                    if event_type == "message":
                        if event_data.get("role") == "assistant":
                            chunk = event_data.get("content", "")
                            full_response += chunk
                    
                    elif event_type == "tool_use":
                        tool_name = event_data.get("tool_name")
                        tool_input = event_data.get("parameters", event_data.get("input", {}))
                        agent_name = event_data.get("agent_name", "Lead")
                        
                        if tool_name == "maestro":
                            subagent_name = tool_input.get("subagent", "unknown")
                            task = tool_input.get("task", "")
                            task_preview = f" for: `{task[:50]}...`" if task else ""
                            say(f"🤖 **Delegating to Specialist:** `{subagent_name}`{task_preview}...", thread_ts=thread_ts)
                        elif tool_name == "generalist":
                            request = tool_input.get("request", "")
                            req_preview = f" for: `{request[:50]}...`" if request else ""
                            say(f"🤖 **Delegating to Generalist subagent**{req_preview}...", thread_ts=thread_ts)
                        else:
                            prefix = f"🤖 **[{agent_name}]** " if agent_name != "Lead" else "🛠️ **Acting:** "
                            context = ""
                            if tool_name in ["read_file", "write_file", "replace"]:
                                path = tool_input.get("file_path", "")
                                if path:
                                    context = f": `{os.path.basename(path)}`"
                            elif tool_name == "run_shell_command":
                                cmd_input = tool_input.get("command", "")
                                if cmd_input:
                                    short_cmd = cmd_input[:60] + "..." if len(cmd_input) > 60 else cmd_input
                                    context = f": `{short_cmd}`"
                            elif tool_name in ["glob", "grep_search"]:
                                pattern = tool_input.get("pattern", "")
                                if pattern:
                                    context = f" for `{pattern}`"
                            elif tool_name == "google_web_search":
                                query = tool_input.get("query", "")
                                if query:
                                    context = f": `{query}`"
                            elif tool_name == "list_directory":
                                dir_path = tool_input.get("dir_path", "")
                                if dir_path:
                                    context = f" on `{os.path.basename(dir_path)}`"
                            else:
                                for key in ["url", "title", "issue_id", "name"]:
                                    if key in tool_input:
                                        val = str(tool_input[key])
                                        short_val = val[:40] + "..." if len(val) > 40 else val
                                        context = f" ({key}: {short_val})"
                                        break

                            say(f"{prefix}Executing `{tool_name}`{context}...", thread_ts=thread_ts)
                        
                    elif event_type == "result":
                        stats = event_data.get("stats", {})
                        last_usage = stats.get("total_tokens")
                        if last_usage:
                            database.update_session_status(session_id, "running", last_usage)
                            if last_usage / config.MAX_TOKENS > config.CONTEXT_THRESHOLD:
                                say(f"⚠️ **CRITICAL: Context limit reached ({last_usage:,}/{config.MAX_TOKENS:,})!** Terminating.", thread_ts=thread_ts)
                                process.terminate()
                                break

                except json.JSONDecodeError:
                    continue

                if time.time() - start_time > config.TIMEOUT_SECONDS:
                    say(f"🛑 **TIMEOUT: Subagent exceeded {config.TIMEOUT_SECONDS}s.** Terminating.", thread_ts=thread_ts)
                    process.terminate()
                    break
                
        process.wait()
        
        if session_id in active_tasks:
            del active_tasks[session_id]
            
        final_usage_msg = ""
        if last_usage:
            final_usage_msg = f"\n\n📊 **Context Usage:** {last_usage:,} / {config.MAX_TOKENS:,} tokens"
        
        if full_response:
            for i in range(0, len(full_response), 3000):
                say(f"```\n{full_response[i:i+3000]}\n```", thread_ts=thread_ts)
            
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
