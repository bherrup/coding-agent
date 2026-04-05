import os
import sys

# Add app folder to path for testing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fleet.utils import check_for_errors

def test_check_for_errors() -> None:
    """Test basic error checking logic."""
    assert "QUOTA EXCEEDED" in (check_for_errors("TerminalQuotaError") or "")
    assert "CONFIG ERROR" in (check_for_errors("Invalid configuration in /home/agent/.gemini/extensions/Stitch/gemini-extension.json: missing \"name\"") or "")
    assert "CRITICAL ERROR" in (check_for_errors("unexpected critical error") or "")
    assert check_for_errors("normal output") is None
