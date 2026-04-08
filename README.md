# Kimi Voice Assistant

This project contains a beginner-friendly Python voice assistant named **Kimi** with command handling + AI fallback.

## Files

- `kimi.py` - Main assistant script (speech + command handling + AI integration).
- `requirements.txt` - Python libraries required to run the assistant.
- `README.md` - Setup and usage guide.

## Install Required Libraries

Open terminal in this folder (`Kimi`) and run:

```bash
pip install -r requirements.txt
```

### If `PyAudio` installation fails (common on Windows)

Try:

```bash
pip install pipwin
pipwin install pyaudio
```

## Set API Key (Required for AI replies)

Kimi reads API credentials from a `.env` file in the project root.

1. Create a file named `.env` in the same folder as `kimi.py`.
2. Add your Groq API key to the file:
   ```text
   GROQ_API_KEY=your_groq_api_key_here
   ```
3. (Optional) Set the model:
   ```text
   KIMI_MODEL=llama-3.1-8b-instant
   ```

Using a `.env` file ensures your key is loaded automatically every time you run Kimi.

## Run Kimi

```bash
python kimi.py
```

## Supported Voice Commands

- "open chrome"
- "open youtube"
- "what is the time" / "current time"
- "who are you"
- "exit" / "quit" / "stop" (to close assistant)

## How AI Integration Works

1. Kimi sends your prompt, memory context, and available tools to Groq.
2. The model decides whether to:
   - call a tool (function), or
   - return a normal text response.
3. If a tool is called, Kimi executes it dynamically and sends tool result back to model.
4. Kimi then speaks the final assistant response.

If API key is missing or API call fails, Kimi responds with a friendly error message instead of crashing.

### Model deprecation safety

If one model is unavailable or deprecated, Kimi automatically retries fallback models.

## AI Agent Tool Calling

Kimi now works as a tool-using AI agent with a tool registry:

- `open_youtube()` -> opens YouTube in browser
- `search_youtube(query)` -> searches YouTube for a query
- `play_youtube(query)` -> plays first matching YouTube video
- `open_browser()` -> opens Chrome/default browser
- `open_brave()` -> opens Brave browser
- `open_whatsapp()` -> opens WhatsApp desktop app
- `open_file_manager()` -> opens Windows File Explorer
- `open_application(app_name)` -> opens apps by name
- `open_installed_app(app_name)` -> opens installed app by indexed name
- `close_browser()` -> closes Chrome
- `close_application(app_name)` -> closes apps by name
- `open_file(file_path/file_name)` -> opens files by path or name search
- `find_file(file_name)` -> finds matching files by name
- `list_installed_apps(query)` -> lists installed apps (optional filter)
- `tell_time()` -> reports current local time

The model chooses tools using function/tool calling instead of hardcoded intent routes for most actions.
For reliability, Kimi also uses a local quick-action layer for common media commands like "play video".
It also handles "close youtube" / "close browser" via a direct local action.
It also handles "open brave" and generic "open <app>" via local quick actions.
It also handles generic "close <app>" commands (example: "close notepad").
It also handles file commands like "open file resume.pdf" and quoted paths.
It can also index and open installed apps from Start Menu + Program Files.
It includes direct support for "open whatsapp" and "open file manager".

## Always-Listening Mode

Kimi now processes your instructions directly without requiring a wake word.
- No need to say "hey kimi" before every command.
- If speech is unclear, Kimi asks: "Can you repeat that?"

## Memory and Personalization

Kimi now includes two runtime memory layers:

1. Conversation history:
   - Stores recent role-based messages (`user`, `assistant`).
   - Keeps only the latest 10 messages (about 5 interactions).
   - This context is sent to Groq so replies stay consistent across turns.

2. User memory:
   - Extracts details from patterns like:
     - "my name is Kislay"
     - "I like gym"
   - Stores them in a dictionary and includes them in AI system guidance.
   - Helps Kimi personalize responses naturally.

### Limitation

Memory is runtime-only for now. If you stop/restart `kimi.py`, conversation history and user memory are cleared.

## Speech and Multi-Step Improvements

- Speech recognition now includes:
  - ambient noise calibration
  - retry attempts (up to 3)
  - improved timeout settings
- If speech remains unclear, Kimi asks: "Can you repeat that?"
- Multi-step commands are split and executed sequentially.
  - Example: "open youtube and play something"
  - Kimi executes two steps in order and gives a combined response.

## Voice Output

Kimi now tries to use a female voice profile automatically (when available on your system voice list).
If speech playback fails at runtime, Kimi auto-reinitializes the TTS engine and retries.
You can force a specific installed voice by setting:

```text
KIMI_VOICE_NAME=zira
```

Use any part of the installed voice name or id (for example: `zira`, `samantha`, `aria`).

## Media Playback Note

Kimi uses `pywhatkit` (when available) to play YouTube videos directly.
If direct playback fails, it falls back to opening/searching YouTube in the browser.

## File Access and Opening

Kimi can now search and open files on your PC using voice instructions:
- "open file report.pdf"
- "open file assignment"
- `open "C:\Users\YourName\Documents\notes.txt"`

Behavior:
- If exact path is given, Kimi opens that file directly.
- If only file name is given, Kimi searches common folders and available drives, then opens the best match.
- File search has a time budget to avoid long freezes during huge disk scans.

## Installed Apps Access

Kimi now builds an installed-app index and can open apps by name:
- "open photoshop"
- "open visual studio code"
- "open telegram"
- "list installed apps"

It searches Start Menu app entries and common Program Files executables for matching installed apps.
