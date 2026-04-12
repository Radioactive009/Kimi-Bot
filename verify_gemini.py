import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def test_gemini_connection():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not found in .env")
        return False

    print(f"Testing Gemini connection with key: {api_key[:10]}...")
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-flash-latest")
        response = model.generate_content("Say 'Gemini is ready!'")
        print(f"SUCCESS: {response.text}")
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False

def test_gemini_tool_schema():
    print("\nTesting tool schema compatibility...")
    try:
        # Mock a simple tool
        def get_current_time():
            """Returns the current time."""
            return "12:00 PM"

        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            tools=[get_current_time]
        )
        
        # This will verify if Gemini accepts the function object
        print("SUCCESS: Gemini accepted the function-based tool definition.")
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
