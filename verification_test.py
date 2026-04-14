from unittest.mock import MagicMock

import sys

# Mock modules that may fail in restricted environments.
sys.modules["pyttsx3"] = MagicMock()
sys.modules["speech_recognition"] = MagicMock()
sys.modules["bs4"] = MagicMock()
if "pywhatkit" not in sys.modules:
    sys.modules["pywhatkit"] = MagicMock()

import kimi


def test_boss_honorific():
    print("Testing 'boss' honorific in AGENT_ACTION_ACKS...")
    for ack in kimi.AGENT_ACTION_ACKS:
        if "boss" not in ack.lower():
            print(f"FAILED: '{ack}' does not contain 'boss'")
            return False
    print("PASSED: All ACKs contain 'boss'")
    return True


def test_system_prompt_template():
    print("Testing Gemini system prompt template...")
    with open("kimi.py", "r", encoding="utf-8") as f:
        content = f.read()

    required_fragments = [
        "You are Kimi, a sophisticated AI assistant.",
        "Reply in Hindi (Hinglish).",
        "Reply in English.",
        "build_memory_context()",
    ]
    for fragment in required_fragments:
        if fragment not in content:
            print(f"FAILED: Missing expected fragment -> {fragment}")
            return False

    print("PASSED: System prompt contains expected Gemini-era fragments")
    return True


if __name__ == "__main__":
    s1 = test_boss_honorific()
    s2 = test_system_prompt_template()
    if s1 and s2:
        print("\nVerification successful!")
    else:
        print("\nVerification FAILED!")
        raise SystemExit(1)
