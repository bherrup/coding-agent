import os
import re
import logging

logger = logging.getLogger(__name__)

def get_dir_size(path):
    """Calculates the total size of a directory in bytes."""
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += get_dir_size(entry.path)
    except Exception as e:
        logger.error(f"Error calculating size for {path}: {e}")
    return total

def format_size(size_bytes):
    """Formats bytes into a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"

def check_for_errors(line):
    """Parses raw CLI output lines for known fatal errors."""
    if "TerminalQuotaError" in line or "Quota exceeded" in line:
        retry_match = re.search(r"Please retry in ([\d\.]+)s", line)
        wait_time = f" (Retry in {retry_match.group(1)}s)" if retry_match else ""
        return f"🛑 **QUOTA EXCEEDED:** You have exhausted your Gemini API quota.{wait_time}"
    if "Invalid configuration" in line:
        return "❌ **CONFIG ERROR:** The Gemini CLI settings.json is invalid."
    if "unexpected critical error" in line.lower():
        return "💥 **CRITICAL ERROR:** An unexpected error occurred in the Gemini CLI."
    return None