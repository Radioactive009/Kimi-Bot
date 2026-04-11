import os
import re
from unittest.mock import MagicMock, patch

# Mocking modules that might fail in this environment
import sys
sys.modules['pyttsx3'] = MagicMock()
sys.modules['speech_recognition'] = MagicMock()
sys.modules['bs4'] = MagicMock()
sys.modules['groq'] = MagicMock()
if 'pywhatkit' not in sys.modules:
    sys.modules['pywhatkit'] = MagicMock()

# Import the code to test
import kimi

def test_boss_honorific():
    print("Testing 'boss' honorific in AGENT_ACTION_ACKS...")
    for ack in kimi.AGENT_ACTION_ACKS:
        if "boss" not in ack.lower():
            print(f"FAILED: '{ack}' does not contain 'boss'")
            return False
    print("PASSED: All ACKs contain 'boss'")
    return True

def test_system_prompt():
    print("Testing system prompt...")
    # Mock build_memory_context and client
    with patch('kimi.build_memory_context', return_value="Memory context"):
        # We need to simulate the environment
        os.environ["GROQ_API_KEY"] = "test_key"
        # We don't want to actually call Groq, just check the string construction logic
        # Actually, get_ai_response is large, let's just inspect the file content again
        pass
    
    # Direct inspection of the file content for the system_message string
    with open('kimi.py', 'r', encoding='utf-8') as f:
        content = f.read()
        if "You MUST always address the user as 'boss'" in content:
            print("PASSED: System message contains 'boss' instruction")
        else:
            print("FAILED: System message missing 'boss' instruction")
            return False
    return True

if __name__ == "__main__":
    s1 = test_boss_honorific()
    s2 = test_system_prompt()
    if s1 and s2:
        print("\nVerification successful!")
    else:
        print("\nVerification FAILED!")
        exit(1)
