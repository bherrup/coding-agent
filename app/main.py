import os
import signal
import sys
import logging
import concurrent.futures
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
            logger.info(f"Terminating process for session {session_id}")
            process.terminate()
            
            database.update_session_status(session_id, "interrupted")

            try:
                app.client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text=f"🚨 **Fleet Agent is shutting down/restarting.** Work paused in session `{session_id}`. Use `@agent fleet resume {session_id}` when the system is back online."
                )
            except Exception as e:
                logger.error(f"Failed to send shutdown message to Slack: {e}")
    sys.exit(0)

# Register signals
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

if __name__ == "__main__":
    logger.info("Initializing Fleet Agent...")
    
    # Initialize DB and check for crashes
    database.init_db()
    database.check_orphaned_sessions()
    
    # Generate Settings
    gemini_runner.generate_gemini_settings()
    
    # Register Slack routing
    slack_handlers.register_handlers(app, executor, active_tasks, gemini_runner.process_task)
    
    # Start app
    logger.info("Starting SocketModeHandler...")
    handler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
    handler.start()
