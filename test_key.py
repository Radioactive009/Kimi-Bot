import os
from groq import Groq
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

def test_groq_key():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("ERROR: GROQ_API_KEY not found in .env")
        return

    print(f"Testing key: {api_key[:10]}...")
    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "Hello, responder with 'Key is valid'"}],
            max_tokens=10
        )
        print("SUCCESS: API call worked!")
        print(f"Response: {response.choices[0].message.content}")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    test_groq_key()
