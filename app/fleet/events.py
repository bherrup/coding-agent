import logging
from . import config
from . import database

logger = logging.getLogger(__name__)

class EventHandler:
    """Handles and formats Gemini CLI JSON events for Slack."""

    def __init__(self, say, thread_ts, session_id):
        self.say = say
        self.thread_ts = thread_ts
        self.session_id = session_id
        self.current_thought = ""
        self.last_usage = None
        self.should_stop = False
        self.current_phase = "RESEARCH"
        self.approval_status = "PENDING"
        
        # Load initial state from DB
        try:
            initial_phase, initial_approval = database.get_session_state(session_id)
            self.current_phase = initial_phase
            self.approval_status = initial_approval
        except Exception as e:
            logger.error(f"Failed to load session state for {session_id}: {e}")

    def handle_event(self, event_data):
        """Processes a single JSON event from the Gemini CLI."""
        event_type = event_data.get("type")
        
        if event_type == "message":
            self._handle_message(event_data)
        elif event_type == "tool_use":
            self._handle_tool_use(event_data)
        elif event_type == "result":
            self._handle_result(event_data)
        
        return self.should_stop

    def _update_db_state(self):
        """Syncs local phase/approval state to the database."""
        try:
            database.update_session_state(
                self.session_id, 
                phase=self.current_phase, 
                approval_status=self.approval_status
            )
        except Exception as e:
            logger.error(f"Failed to update session state for {self.session_id}: {e}")

    def _handle_message(self, event_data):
        """Accumulates assistant thoughts and detects phase transitions."""
        if event_data.get("role") == "assistant":
            chunk = event_data.get("content", "")
            self.current_thought += chunk
            
            # Detect PLANNING phase
            if self.current_phase == "RESEARCH":
                lower_chunk = chunk.lower()
                if any(kw in lower_chunk for kw in ["plan", "architecture", "proposed scope"]):
                    self.current_phase = "PLANNING"
                    self._update_db_state()

    def _handle_tool_use(self, event_data):
        """Formats and posts tool execution messages to Slack and detects EXECUTION phase."""
        tool_name = event_data.get("tool_name")
        agent_name = event_data.get("agent_name", "Lead")
        params = event_data.get("parameters", {})
        
        # Detect EXECUTING phase
        modifying_tools = ["write_file", "replace", "run_shell_command"]
        if tool_name in modifying_tools and self.current_phase != "EXECUTION":
            # run_shell_command should only count if it's not a read operation
            is_write = True
            if tool_name == "run_shell_command":
                cmd = params.get("command", "").lower()
                if any(kw in cmd for kw in ["ls ", "cat ", "grep ", "git log", "git show", "git status"]):
                    is_write = False
            
            if is_write:
                self.current_phase = "EXECUTION"
                self._update_db_state()

        # Extract a brief "summary" of what the tool is doing from its parameters
        context = ""
        emoji = "🤖" # Default
        
        if tool_name == "activate_skill":
            emoji = "🛠️"
            context = f" (`{params.get('name', 'unknown')}`)"
        elif tool_name == "read_file":
            emoji = "📂"
            lines = ""
            if "start_line" in params and "end_line" in params:
                lines = f" (lines {params['start_line']}-{params['end_line']})"
            context = f" on `{params.get('file_path', 'unknown')}`{lines}"
        elif tool_name == "write_file":
            emoji = "📂"
            context = f" to `{params.get('file_path', 'unknown')}`"
        elif tool_name == "replace":
            emoji = "📂"
            instr = params.get('instruction', 'modifying file')
            if len(instr) > 50:
                instr = instr[:47] + "..."
            context = f" in `{params.get('file_path', 'unknown')}`: \"{instr}\""
        elif tool_name == "list_directory":
            emoji = "📁"
            context = f" in `{params.get('dir_path', '.')}`"
        elif tool_name == "run_shell_command":
            emoji = "🐚"
            # Prioritize description for shell commands
            desc = params.get('description')
            if desc:
                if len(desc) > 60:
                    desc = desc[:57] + "..."
                context = f": \"{desc}\""
            else:
                cmd = params.get('command', '').split('\n')[0]
                if len(cmd) > 50:
                    cmd = cmd[:47] + "..."
                context = f": `{cmd}`"
        elif tool_name.startswith("mcp_gitlab_"):
            emoji = "🦊"
            project = params.get('project_id', 'unknown')
            if "merge_request_iid" in params:
                context = f" (MR `#{params['merge_request_iid']}` in `{project}`)"
            elif "issue_iid" in params:
                context = f" (Issue `#{params['issue_iid']}` in `{project}`)"
            elif "pipeline_id" in params:
                context = f" (Pipeline `{params['pipeline_id']}` in `{project}`)"
            elif "job_id" in params:
                context = f" (Job `{params['job_id']}` in `{project}`)"
            else:
                context = f" (Project: `{project}`)"
        
        # Fallback for unknown tools: use the first parameter
        if not context and params:
            first_key = next(iter(params))
            val = str(params[first_key]).split('\n')[0]
            if len(val) > 40:
                val = val[:37] + "..."
            context = f" ({first_key}: `{val}`)"
        
        # Post the thought and the tool call as a linked action
        if self.current_thought.strip():
            thought = self.current_thought.strip()
            self.say(f"💭 **[{agent_name}]** {thought}\n↳ {emoji} Executing `{tool_name}`{context}...", thread_ts=self.thread_ts)
            self.current_thought = ""
        else:
            self.say(f"{emoji} **[{agent_name}]** Executing `{tool_name}`{context}...", thread_ts=self.thread_ts)

    def _handle_result(self, event_data):
        """Handles tool execution results and usage tracking."""
        agent_name = event_data.get("agent_name", "Lead")
        tool_name = event_data.get("tool_name", "tool")
        is_error = "error" in event_data or event_data.get("is_error", False)
        
        if is_error:
            error_msg = event_data.get("error", "Unknown error")
            if len(error_msg) > 100:
                error_msg = error_msg[:97] + "..."
            self.say(f"❌ **[{agent_name}]** `{tool_name}` failed: `{error_msg}`", thread_ts=self.thread_ts)
        
        stats = event_data.get("stats", {})
        usage = stats.get("total_tokens")
        if usage:
            self.last_usage = usage
            database.update_session_status(self.session_id, "running", usage)
            if usage / config.MAX_TOKENS > config.CONTEXT_THRESHOLD:
                self.say("⚠️ **CRITICAL: Context limit reached!** Terminating.", thread_ts=self.thread_ts)
                self.should_stop = True

    def flush_final_response(self):
        """Sends any remaining assistant thoughts as the final message."""
        final_response = self.current_thought.strip()
        if final_response:
            for i in range(0, len(final_response), 3000):
                self.say(final_response[i:i+3000], thread_ts=self.thread_ts)
            self.current_thought = ""
