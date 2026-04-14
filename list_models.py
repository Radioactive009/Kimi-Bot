import os

from dotenv import load_dotenv
from google import genai

load_dotenv()


def list_models():
    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        print("ERROR: GEMINI_API_KEY (or GOOGLE_API_KEY) not found in .env")
        return

    client = genai.Client(api_key=api_key, http_options={"api_version": "v1"})
    print("Available models:")
    try:
        for model in client.models.list():
            name = getattr(model, "name", "")
            if "gemini" in name:
                print(f"- {name}")
    except Exception as e:
        print(f"Error listing models: {e}")


if __name__ == "__main__":
    list_models()
