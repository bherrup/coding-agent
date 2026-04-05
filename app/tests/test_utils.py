import os
import sys

# Add app folder to path for testing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fleet.utils import check_approval

def test_check_approval_unconditional():
    """Test various unconditional approval phrases."""
    approvals = [
        "go", "approved", "approve", "proceed", "yes", "do it", 
        "make it so", "looks good", "ship it", "unconditional approval",
        "approved as is", "Go ahead", "Yes, go!", "Ship it!", "Approved."
    ]
    for phrase in approvals:
        status, _ = check_approval(phrase)
        assert status == 'unconditional', f"Failed to detect approval for: {phrase}"

def test_check_approval_conditional():
    """Test various conditional approval phrases."""
    conditionals = [
        "Approved, but do X", "Go, and also do Y", "Yes but wait", 
        "Proceed however make sure Z", "Ship it, also add test",
        "approved with modifications"
    ]
    for phrase in conditionals:
        status, _ = check_approval(phrase)
        assert status == 'conditional', f"Failed to detect conditional for: {phrase}"

def test_check_approval_none():
    """Test phrases that should not be detected as approval."""
    not_approvals = [
        "What is the status?", "I don't know", "Wait a minute", 
        "Why did you do that?", "No, stop", "not approved", "refuse"
    ]
    for phrase in not_approvals:
        status, _ = check_approval(phrase)
        assert status == 'none', f"False positive for: {phrase}"
