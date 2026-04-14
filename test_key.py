import os

from dotenv import load_dotenv
from google import genai

load_dotenv()


def test_gemini_key():
    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        print("ERROR: GEMINI_API_KEY (or GOOGLE_API_KEY) not found in .env")
        return

    print(f"Testing key prefix: {api_key[:10]}...")
    try:
        client = genai.Client(api_key=api_key, http_options={"api_version": "v1"})
        response = client.models.generate_content(
            model="models/gemini-1.5-flash",
            contents="Reply with exactly: Key is valid",
        )
        print("SUCCESS: API call worked!")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"FAILED: {e}")


if __name__ == "__main__":
    test_gemini_key()
