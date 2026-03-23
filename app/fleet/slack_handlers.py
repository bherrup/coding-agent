import re
import shutil
import os
import signal
from . import config
from . import database
from . import utils

def handle_admin_commands(command, say, thread_ts, active_tasks=None):
    """Handles fleet management commands like status, cleanup, context, and cancel."""
    cmd_lower = command.lower()
    
    if cmd_lower.startswith("fleet cancel") or cmd_lower.startswith("fleet stop"):
        parts = command.split()
        session_id = None
        if len(parts) >= 3:
            session_id = parts[2]
        else:
            # Infer from thread_ts
            session_id = database.get_session_by_thread_ts(thread_ts)
            
        if not session_id:
            say("💡 Usage: `fleet cancel <session_id>` (or use from within a fleet thread)", thread_ts=thread_ts)
            return True
            
        if active_tasks is not None and session_id in active_tasks:
            task_info = active_tasks[session_id]
            process = task_info.get("process")
            if process:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    say(f"🛑 **Fleet Cancel:** Sent termination signal to session `{session_id}` and its sub-processes.", thread_ts=thread_ts)
                except Exception as e:
                    say(f"⚠️ **Fleet Cancel:** Error during termination: {e}. Attempting standard terminate.", thread_ts=thread_ts)
                    process.terminate()
                database.update_session_status(session_id, "cancelled")
            else:
                say(f"⚠️ **Fleet Cancel:** Session `{session_id}` is starting but hasn't launched a process yet. Please try again in a few seconds.", thread_ts=thread_ts)
        else:
            say(f"⚠️ **Fleet Cancel:** Session `{session_id}` does not appear to be currently running.", thread_ts=thread_ts)
            
        return True

    if cmd_lower == "fleet status" or cmd_lower == "fleet context status":
        rows = database.get_recent_sessions(limit=15)
        
        if not rows:
            say("📁 **Fleet Status:** No active sessions found in database.", thread_ts=thread_ts)
            return True
        
        report_lines = []
        for session_id, status, token_usage, updated_at in rows:
            session_dir = config.SESSIONS_ROOT / session_id
            size_str = utils.format_size(utils.get_dir_size(session_dir)) if session_dir.exists() else "0 B"
            usage_str = f" | 🧠 {token_usage:,} tokens" if token_usage else ""
            
            # Convert SQLite timestamp to simpler format
            try:
                from datetime import datetime
                dt = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S")
                mtime = dt.strftime('%m-%d %H:%M')
            except Exception:
                mtime = updated_at
                
            report_lines.append(f"• `{session_id}` [{status.upper()}]: {size_str}{usage_str} (Last Update: {mtime})")
            
        report = "\n".join(report_lines)
        say(f"📋 **Recent Fleet Sessions (Top 15):**\n{report}", thread_ts=thread_ts)
        return True
        
    if cmd_lower.startswith("fleet resume"):
        parts = command.split()
        if len(parts) < 3:
            say("💡 Usage: `fleet resume <session_id>`", thread_ts=thread_ts)
            return True
            
        session_id = parts[2]
        
        row = database.get_session_by_id(session_id)
        
        if row:
            orig_thread_ts, channel, prompt = row
            say(f"🚀 **Resuming session:** `{session_id}`. Output will be directed to its original thread.", thread_ts=thread_ts)
            # This requires circular import logic if we call handle_interaction directly, 
            # so we'll return a special tuple to tell the caller to handle it
            return ("RESUME", orig_thread_ts, channel)
        else:
            say(f"⚠️ **Error:** Session `{session_id}` not found in database.", thread_ts=thread_ts)
        return True

    if cmd_lower.startswith("fleet context"):
        parts = command.split()
        if len(parts) == 2 or (len(parts) == 3 and parts[2] == "status"):
            return handle_admin_commands("fleet status", say, thread_ts)
        
        if len(parts) == 4 and parts[2] == "limit":
            try:
                new_limit = int(parts[3])
                config.set_max_tokens(new_limit)
                say(f"⚙️ **Fleet Config:** `MAX_TOKENS` updated to `{config.MAX_TOKENS:,}`", thread_ts=thread_ts)
            except ValueError:
                say("⚠️ **Error:** Please provide a valid number for the limit.", thread_ts=thread_ts)
            return True
            
        say("💡 Usage:\n• `fleet context status`\n• `fleet context limit <number>`", thread_ts=thread_ts)
        return True

    if cmd_lower.startswith("fleet cleanup"):
        parts = command.split()
        if len(parts) < 3:
            say("💡 Usage: `fleet cleanup <session_id|all>`", thread_ts=thread_ts)
            return True
        
        target = parts[2]
        if target == "all":
            if config.SESSIONS_ROOT.exists():
                shutil.rmtree(config.SESSIONS_ROOT)
                config.SESSIONS_ROOT.mkdir(parents=True, exist_ok=True)
            database.delete_all_sessions()
            say("🧹 **Fleet Cleanup:** All sessions have been purged.", thread_ts=thread_ts)
            return True
        
        target_dir = config.SESSIONS_ROOT / target
        if target_dir.exists() and target_dir.is_dir():
            shutil.rmtree(target_dir)
            
        database.delete_session(target)
        say(f"🧹 **Fleet Cleanup:** Session `{target}` has been deleted.", thread_ts=thread_ts)
        return True

    return False

def build_interaction_handler(executor, active_tasks, process_task_fn):
    """Closure to provide access to global state without circular imports."""
    def handle_interaction(event, say):
        """Common logic for mentions and threaded messages."""
        thread_ts = event.get("thread_ts", event.get("ts"))
        channel = event.get("channel")
        raw_text = event.get("text", "")
        
        clean_text = re.sub(r"<@U[A-Z0-9]+>", "", raw_text).strip()
        
        if not clean_text:
            if event.get("type") == "app_mention":
                say("I'm listening! Please provide a prompt.", thread_ts=thread_ts)
            return

        admin_result = handle_admin_commands(clean_text, say, thread_ts, active_tasks)
        if admin_result:
            if isinstance(admin_result, tuple) and admin_result[0] == "RESUME":
                _, orig_thread_ts, orig_channel = admin_result
                simulated_event = {"thread_ts": orig_thread_ts, "ts": orig_thread_ts, "text": "Resume executing", "channel": orig_channel}
                handle_interaction(simulated_event, say)
            return

        session_dir = database.get_or_create_session(thread_ts, clean_text, channel)
        session_id = session_dir.name
        
        # Check if this specific session is already running
        if session_id in active_tasks:
            say("⏳ **Fleet is currently working on this thread.** Please wait for the current task to finish.", thread_ts=thread_ts)
            return
        
        # Check queue saturation
        if executor._work_queue.qsize() >= 3:
             say("⏳ **Fleet Queue Busy:** Your request is queued and will start shortly.", thread_ts=thread_ts)
             
        # Preemptively register the session to lock it
        active_tasks[session_id] = {
            "process": None,
            "channel": channel,
            "thread_ts": thread_ts,
            "session_id": session_id,
            "status": "starting"
        }
             
        # Submit task
        executor.submit(process_task_fn, session_id, thread_ts, channel, clean_text, say, active_tasks)

    return handle_interaction

def register_handlers(app, executor, active_tasks, process_task_fn):
    """Registers Bolt event handlers."""
    handle_interaction = build_interaction_handler(executor, active_tasks, process_task_fn)

    @app.event("app_mention")
    def handle_mention(event, say):
        handle_interaction(event, say)

    @app.event("message")
    def handle_message_events(event, say):
        if "thread_ts" not in event or event.get("bot_id"):
            return
        handle_interaction(event, say)