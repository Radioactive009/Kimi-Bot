import asyncio
import edge_tts
import os

async def test_voice():
    voice = "en-GB-SoniaNeural"
    text = "Hello, I am testing the neural voice."
    output_file = "test_voice.mp3"
    
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)
        print(f"SUCCESS: Saved voice to {output_file}")
        if os.path.exists(output_file):
            print(f"File size: {os.path.getsize(output_file)} bytes")
            os.remove(output_file)
    except Exception as e:
        print(f"FAILURE: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_voice())
