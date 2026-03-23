import sqlite3
import re
import logging
from datetime import datetime
from . import config

logger = logging.getLogger(__name__)

def init_db():
    """Initializes the SQLite database for session tracking."""
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            slack_thread_ts TEXT,
            slack_channel TEXT,
            prompt TEXT,
            status TEXT,
            token_usage INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def update_session_status(session_id, status, token_usage=None):
    """Updates the status and optionally token usage of a session."""
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    if token_usage is not None:
        cursor.execute('''
            UPDATE sessions 
            SET status = ?, token_usage = ?, updated_at = CURRENT_TIMESTAMP
            WHERE session_id = ?
        ''', (status, token_usage, session_id))
    else:
        cursor.execute('''
            UPDATE sessions 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE session_id = ?
        ''', (status, session_id))
    conn.commit()
    conn.close()

def check_orphaned_sessions():
    """Scan SQLite for sessions that were interrupted by a container restart."""
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT session_id, slack_channel, slack_thread_ts FROM sessions 
        WHERE status IN ('running', 'queued')
    ''')
    orphans = cursor.fetchall()
    
    if orphans:
        cursor.execute('''
            UPDATE sessions SET status = 'orphaned', updated_at = CURRENT_TIMESTAMP 
            WHERE status IN ('running', 'queued')
        ''')
        conn.commit()
        orphan_ids = [o[0] for o in orphans]
        logger.warning(f"Found orphaned sessions from previous run: {', '.join(orphan_ids)}")

    conn.close()

def get_or_create_session(thread_ts, prompt, channel):
    """Finds an existing session in SQLite, or creates a new one."""
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT session_id FROM sessions WHERE slack_thread_ts = ?', (thread_ts,))
    row = cursor.fetchone()
    
    if row:
        session_id = row[0]
        conn.close()
        return config.SESSIONS_ROOT / session_id

    # Create new session
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', prompt.lower())[:30].strip('-')
    if not slug:
        slug = "task"
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_id = f"{timestamp}_{slug}"
    
    cursor.execute('''
        INSERT INTO sessions (session_id, slack_thread_ts, slack_channel, prompt, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (session_id, thread_ts, channel, prompt, 'queued'))
    conn.commit()
    conn.close()
    
    session_dir = config.SESSIONS_ROOT / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir

def get_recent_sessions(limit=15):
    """Returns the most recent sessions from the database."""
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT session_id, status, token_usage, updated_at FROM sessions ORDER BY updated_at DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_session_by_id(session_id):
    """Returns the thread_ts, channel, and prompt for a given session."""
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT slack_thread_ts, slack_channel, prompt FROM sessions WHERE session_id = ?', (session_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def get_session_by_thread_ts(thread_ts):
    """Returns the session_id for a given thread_ts."""
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT session_id FROM sessions WHERE slack_thread_ts = ?', (thread_ts,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def delete_all_sessions():
    """Deletes all session records from the database."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute('DELETE FROM sessions')
    conn.commit()
    conn.close()

def delete_session(session_id):
    """Deletes a specific session record from the database."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute('DELETE FROM sessions WHERE session_id = ?', (session_id,))
    conn.commit()
    conn.close()