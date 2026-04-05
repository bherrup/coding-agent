import os
import signal
import sys
import logging
import threading
import time
import concurrent.futures
from http.server import BaseHTTPRequestHandler, HTTPServer
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from fleet import database
from fleet import gemini_runner
from fleet import slack_handlers

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Bolt app
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# Simple Health Check Handler
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "healthy"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress standard HTTP access logs to keep console clean
        pass

def start_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    logger.info(f"Starting built-in health check server on port {port}")
    server.serve_forever()

# Thread pool for handling multiple concurrent requests
executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)

# Global registry for active tasks to handle graceful shutdown
active_tasks = {}

def handle_shutdown(signum, frame):
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    executor.shutdown(wait=False, cancel_futures=True)
    
    for session_id, task_info in active_tasks.items():
        process = task_info.get("process")
        channel = task_info.get("channel")
        thread_ts = task_info.get("thread_ts")
        
        if process and process.poll() is None:
            logger.info(f"Signaling process for session {session_id} (SIGINT)")
            # Send SIGINT to allow Gemini CLI to flush history/state
            process.send_signal(signal.SIGINT)
            
            database.update_session_status(session_id, "interrupted")
            
            # Fetch state for better messaging
            phase, approval = database.get_session_state(session_id)
            status_text = f"Phase: `{phase}`, Approval: `{approval}`"

            try:
                app.client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text=(
                        f"🚨 **Fleet Agent is cycling/restarting.**\n"
                        f"Work paused in session `{session_id}`.\n"
                        f"Last known state: {status_text}.\n"
                        f"Use `@agent fleet resume {session_id}` to continue from where we left off."
                    )
                )
            except Exception as e:
                logger.error(f"Failed to send shutdown message to Slack: {e}")
                
    sys.exit(0)

# Register signals
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

if __name__ == "__main__":
    # 1. Start built-in health check server immediately
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    
    # Give the server a moment to bind to the port
    time.sleep(2)
    
    logger.info("Initializing Fleet Agent components...")
    
    # 2. Initialize DB and check for crashes
    try:
        database.init_db()
        database.check_orphaned_sessions()
        
        # Purge any abandoned session data from /tmp or NFS active root
        from fleet import utils
        utils.purge_active_sessions(gemini_runner.config.ACTIVE_SESSIONS_ROOT)
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
    
    # 3. Generate Settings
    gemini_runner.generate_gemini_settings()
    
    # 4. Register Slack routing
    slack_handlers.register_handlers(app, executor, active_tasks, gemini_runner.process_task)
    
    # 5. Start app
    logger.info("Starting SocketModeHandler...")
    handler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
    handler.start()
