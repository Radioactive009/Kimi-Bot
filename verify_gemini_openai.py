import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def test_gemini_openai_connection():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not found in .env")
        return False

    print(f"Testing Gemini OpenAI-compatible connection with key: {api_key[:10]}...")
    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        response = client.chat.completions.create(
            model="gemini-1.5-flash-latest",
            messages=[{"role": "user", "content": "Say 'Gemini OpenAI Bridge is ready!'"}]
        )
        print(f"SUCCESS: {response.choices[0].message.content}")
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False

def test_gemini_openai_tools():
    print("\nTesting tool calling via OpenAI Bridge...")
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        client = OpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "parameters": {
                        "type": "object",
                        "properties": {"location": {"type": "string"}},
                    },
                },
            }
        ]
        
        response = client.chat.completions.create(
            model="gemini-1.5-flash-latest",
            messages=[{"role": "user", "content": "What is the weather in London?"}],
            tools=tools,
            tool_choice="auto"
        )
        
        if response.choices[0].message.tool_calls:
            print(f"SUCCESS: Gemini called tool '{response.choices[0].message.tool_calls[0].function.name}'")
            return True
        else:
            print("FAILED: No tool call received.")
            return False
    except Exception as e:
        print(f"FAILED: {e}")
        return False

if __name__ == "__main__":
    c1 = test_gemini_openai_connection()
    c2 = test_gemini_openai_tools()
    if c1 and c2:
        print("\nGemini OpenAI Migration Verification: PASSED")
    else:
        print("\nGemini OpenAI Migration Verification: FAILED")
