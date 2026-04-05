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

def check_approval(text):
    """
    Analyzes the user's response to determine the protocol state.
    Returns: (type, explanation)
    type: 'unconditional', 'conditional', or 'none'
    """
    text_lower = text.lower().strip()
    
    # Approval base keywords and phrases
    approval_keywords = [
        "go", "approved", "approve", "proceed", "yes", "do it", 
        "make it so", "looks good", "ship it", "unconditional approval",
        "approved as is"
    ]
    
    # Check for conditional approval: "Approved, but..."
    # Match starting with keyword followed by "but/however/etc"
    keywords_pattern = "|".join([re.escape(k) for k in approval_keywords])
    conditional_match = re.match(rf"^({keywords_pattern})[,\s!.]+(but|however|only|also|and)\b", text_lower)
    if conditional_match or "approved with modifications" in text_lower:
        return 'conditional', "The user has provided CONDITIONAL approval. Acknowledge and follow the new scope modifications."
    
    # Check for unconditional approval
    if any(text_lower == kw or text_lower.startswith(f"{kw} ") or text_lower.startswith(f"{kw},") or text_lower.startswith(f"{kw}!") or text_lower.startswith(f"{kw}.") for kw in approval_keywords):
        return 'unconditional', "The user has granted UNCONDITIONAL approval of the entire plan."
        
    return 'none', None

def check_for_errors(line):
    """Parses raw CLI output lines for known fatal errors."""
    if "TerminalQuotaError" in line or "Quota exceeded" in line:
        retry_match = re.search(r"Please retry in ([\d\.]+)s", line)
        wait_time = f" (Retry in {retry_match.group(1)}s)" if retry_match else ""
        return f"🛑 **QUOTA EXCEEDED:** You have exhausted your Gemini API quota.{wait_time}"
    if "Invalid configuration" in line:
        return f"❌ **CONFIG ERROR:** The Gemini CLI settings.json is invalid. Details: `{line}`"
    if "unexpected critical error" in line.lower():
        return "💥 **CRITICAL ERROR:** An unexpected error occurred in the Gemini CLI."
    return None

def purge_active_sessions(path):
    """Purges the active session root to prevent storage leakage."""
    import shutil
    from pathlib import Path
    path = Path(path)
    if path.exists() and path.is_dir():
        logger.info(f"🧹 Purging active session root: {path}")
        try:
            for item in path.iterdir():
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                except Exception as e:
                    logger.error(f"Failed to delete {item}: {e}")
        except Exception as e:
            logger.error(f"Failed to cleanup {path}: {e}")
