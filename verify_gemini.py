import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


def _get_client():
    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        print("ERROR: GEMINI_API_KEY (or GOOGLE_API_KEY) not found in .env")
        return None
    return genai.Client(api_key=api_key, http_options={"api_version": "v1"})


def test_gemini_connection():
    client = _get_client()
    if not client:
        return False

    print("Testing Gemini connection...")
    try:
        response = client.models.generate_content(
            model="models/gemini-1.5-flash",
            contents="Say 'Gemini is ready!'",
        )
        print(f"SUCCESS: {response.text}")
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False


def test_gemini_tool_schema():
    client = _get_client()
    if not client:
        return False

    print("\nTesting tool schema compatibility...")
    try:
        tool = types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="get_current_time",
                    description="Returns current time for a given timezone.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "timezone": {"type": "string"},
                        },
                    },
                )
            ]
        )

        _ = client.models.generate_content(
            model="models/gemini-1.5-flash",
            contents="What time is it in Asia/Kolkata?",
            config=types.GenerateContentConfig(tools=[tool]),
        )
        print("SUCCESS: Gemini accepted the function tool schema.")
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False


if __name__ == "__main__":
    c1 = test_gemini_connection()
    c2 = test_gemini_tool_schema()
    if c1 and c2:
        print("\nGemini Migration Verification: PASSED")
    else:
        print("\nGemini Migration Verification: FAILED")
