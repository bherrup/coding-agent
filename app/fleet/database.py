import sqlite3
import re
import logging
import os
from datetime import datetime
from . import config

logger = logging.getLogger(__name__)

def get_connection():
    """Returns a SQLite connection, ensuring the parent directory exists."""
    # Ensure the parent directory exists (critical for Filestore/NFS mounts)
    try:
        if not config.DB_PATH.parent.exists():
            logger.info(f"Creating database directory: {config.DB_PATH.parent}")
            config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"CRITICAL: Failed to create database directory {config.DB_PATH.parent}: {e}")
        # Log current UID and directory info for debugging
        logger.error(f"Current UID: {os.getuid()}, Directory exists: {config.DB_PATH.parent.exists()}")
        
    try:
        # We use a 5s timeout to handle potential NFS latency
        return sqlite3.connect(config.DB_PATH, timeout=5.0)
    except sqlite3.OperationalError as e:
        logger.error(f"SQLITE ERROR: {e} (Path: {config.DB_PATH})")
        # Check if we can write to the directory
        if os.access(config.DB_PATH.parent, os.W_OK):
            logger.error("Directory is WRITABLE, but file open failed.")
        else:
            logger.error("Directory is NOT WRITABLE by current user.")
        raise

def init_db():
    """Initializes the SQLite database for session tracking."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            slack_thread_ts TEXT,
            slack_channel TEXT,
            prompt TEXT,
            status TEXT,
            phase TEXT DEFAULT 'INITIALIZATION',
            approval_status TEXT DEFAULT 'PENDING',
            token_usage INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # SAFE MIGRATION: Add columns if they don't exist
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN phase TEXT DEFAULT 'INITIALIZATION'")
    except sqlite3.OperationalError:
        pass # Column already exists
        
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN approval_status TEXT DEFAULT 'PENDING'")
    except sqlite3.OperationalError:
        pass # Column already exists

    conn.commit()
    conn.close()

def update_session_state(session_id, phase=None, approval_status=None):
    """Updates the phase and/or approval status of a session."""
    conn = get_connection()
    cursor = conn.cursor()
    if phase and approval_status:
        cursor.execute('''
            UPDATE sessions SET phase = ?, approval_status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE session_id = ?
        ''', (phase, approval_status, session_id))
    elif phase:
        cursor.execute('''
            UPDATE sessions SET phase = ?, updated_at = CURRENT_TIMESTAMP
            WHERE session_id = ?
        ''', (phase, session_id))
    elif approval_status:
        cursor.execute('''
            UPDATE sessions SET approval_status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE session_id = ?
        ''', (approval_status, session_id))
    conn.commit()
    conn.close()

def get_session_state(session_id):
    """Returns the (phase, approval_status) for a session."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT phase, approval_status FROM sessions WHERE session_id = ?', (session_id,))
    row = cursor.fetchone()
    conn.close()
    return row if row else ('INITIALIZATION', 'PENDING')

def update_session_status(session_id, status, token_usage=None):
    """Updates the status and optionally token usage of a session."""
    conn = get_connection()
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
    conn = get_connection()
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
    conn = get_connection()
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
    # Ensure session directory on NFS also exists
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir

def get_recent_sessions(limit=15):
    """Returns the most recent sessions from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT session_id, status, token_usage, updated_at FROM sessions ORDER BY updated_at DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_session_by_id(session_id):
    """Returns the thread_ts, channel, and prompt for a given session."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT slack_thread_ts, slack_channel, prompt FROM sessions WHERE session_id = ?', (session_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def get_session_by_thread_ts(thread_ts):
    """Returns the session_id for a given thread_ts."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT session_id FROM sessions WHERE slack_thread_ts = ?', (thread_ts,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def delete_all_sessions():
    """Deletes all session records from the database."""
    conn = get_connection()
    conn.execute('DELETE FROM sessions')
    conn.commit()
    conn.close()

def delete_session(session_id):
    """Deletes a specific session record from the database."""
    conn = get_connection()
    conn.execute('DELETE FROM sessions WHERE session_id = ?', (session_id,))
    conn.commit()
    conn.close()
