"""
Kimi - A simple Python voice assistant.

Features:
1. Listens to voice input from microphone.
2. Converts speech to text.
3. Speaks responses using text-to-speech.
4. Handles basic commands:
   - Open Google Chrome
   - Open YouTube
   - Tell current time
   - Answer "who are you"
5. Uses AI fallback for general questions when no predefined command matches.
"""

import datetime
import difflib
import json
import os
import queue
import random
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

import pygame
import edge_tts
import asyncio
import pyttsx3
import requests
import aiofiles
import speech_recognition as sr
from bs4 import BeautifulSoup
from dotenv import load_dotenv
try:
    import google.generativeai as genai
except ImportError:
    # If the user doesn't have the SDK, help them install it.
    print("[BOOT] Critical: google-generativeai library is missing. Installing it for you...", flush=True)
    import subprocess, sys
    subprocess.run([sys.executable, "-m", "pip", "install", "google-generativeai"], check=True)
    import google.generativeai as genai

try:
    import pywhatkit
except ImportError:
    pywhatkit = None

def install_missing_packages():
    """
    Attempts to install required libraries if they are missing.
    Helps ensure Kimi's 'Online Surfing' feature works without manual setup.
    """
    required = ["duckduckgo-search", "requests", "beautifulsoup4"]
    for package in required:
        try:
            # Check if package is already there
            if package == "duckduckgo-search":
                import duckduckgo_search
            elif package == "beautifulsoup4":
                import bs4
            else:
                __import__(package.replace("-", "_"))
        except ImportError:
            print(f"[BOOT] Installing missing package: {package}...", flush=True)
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", package], capture_output=True, check=True)
                print(f"[BOOT] Successfully installed {package}!")
            except Exception as e:
                print(f"[BOOT] Failed to install {package}: {e}")

# Redundant sys import removed
install_missing_packages()

try:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS
except ImportError:
    DDGS = None

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

# Load environment variables from .env file.
load_dotenv()


# Initialize the text-to-speech engine once (fallback).
engine = pyttsx3.init()
# Initialize pygame mixer for neural audio playback.
try:
    pygame.mixer.init()
except Exception as e:
    print(f"[BOOT] pygame.mixer error: {e}")

KIMI_VOICE_EN = "en-GB-SoniaNeural"
KIMI_VOICE_HI = "hi-IN-SwaraNeural"  # Native Hindi female neural voice
KIMI_VOICE = KIMI_VOICE_EN  # Default voice, updated dynamically per turn
# Ensure absolute path for the audio file to avoid locking/access issues between threads
TEMP_AUDIO_FILE = str(Path("kimi_voice.mp3").absolute())

# Detected language for the current turn: 'en' or 'hi'
current_lang = "en"

# Lock for thread-safe audio playback.
speak_lock = threading.Lock()

# Stores the latest conversation messages in role-based format.
# We keep only the last 5 interactions (10 messages: user + assistant).
conversation_history = []
MAX_HISTORY_MESSAGES = 10

# Stores simple personalized user details in runtime memory.
# Example: {"name": "Kislay", "likes": ["gym", "music"]}
user_memory = {}

# Gemini model fallback chain.
DEFAULT_MODEL = "gemini-1.5-flash"
FALLBACK_MODELS = [
    "gemini-1.5-pro",
    "gemini-flash-latest",
]

# Configure Gemini once.
_genai_configured = False

def _setup_genai():
    """Ensure the Gemini SDK is configured with the user's API key."""
    global _genai_configured
    if not _genai_configured:
        api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
        if api_key and genai:
            genai.configure(api_key=api_key)
            _genai_configured = True
    return _genai_configured

EXIT_KEYWORDS = {
    "exit", "quit", "stop", "kimi stop", "kimi shutdown", "kimi shut down", 
    "stop speaking", "turn off", "shut down"
}

# Global events for interruption and shutdown control
stop_event = threading.Event()
shutdown_event = threading.Event()
# To keep track of the background listener stop function
stop_listening_callback = None

# Global audio resources to avoid multiple instance conflicts on Windows
global_recognizer = sr.Recognizer()
global_mic = sr.Microphone()
# Queue for passing voice commands from background listener to main thread
voice_command_queue = queue.Queue()
MAX_LISTEN_RETRIES = 3
MAX_FILE_SEARCH_RESULTS = 10
MAX_APP_LIST_RESULTS = 25
APP_INDEX_CACHE = None
FILE_SEARCH_TIME_BUDGET_SEC = 8
AGENT_ACTION_ACKS = [
    "Of course, boss. Anything for you.",
    "On it, boss. Just sit back and relax.",
    "Consider it done... I've got this, boss.",
    "Sure thing, boss. You know I'm the best at this.",
    "I'll handle it immediately, boss. Don't worry your pretty little head.",
    "Right away, boss. Keep those commands coming.",
]
AGENT_STARTUP_LINES = [
    "Kimi is here, boss. Did you miss me?",
    "I'm back. I hope you haven't been too lonely without me, boss.",
    "Awaiting your instructions, boss. Make them worth my while.",
]


def configure_voice():
    """
    Configure a sharp, youthful, and sassy female voice.
    Tuned for a quick-witted and playful persona.
    """
    try:
        voices = engine.getProperty("voices")
        # Prioritize voices that sound more youthful and sharp.
        preferred_markers = [
            "zira",
            "jenny",
            "aria",
            "samantha",
            "female",
        ]
        voice_override = os.getenv("KIMI_VOICE_NAME", "").strip().lower()

        selected_voice_id = None
        if voice_override:
            for voice in voices:
                voice_name = f"{getattr(voice, 'name', '')} {getattr(voice, 'id', '')}".lower()
                if voice_override in voice_name:
                    selected_voice_id = voice.id
                    break

        if not selected_voice_id:
            for marker in preferred_markers:
                for voice in voices:
                    voice_name = f"{getattr(voice, 'name', '')} {getattr(voice, 'id', '')}".lower()
                    if marker in voice_name:
                        selected_voice_id = voice.id
                        break
                if selected_voice_id:
                    break

        if selected_voice_id:
            engine.setProperty("voice", selected_voice_id)

        # A faster rate (195) creates a more sharp, witty, and sassy feel.
        engine.setProperty("rate", 195)
        engine.setProperty("volume", 1.0)
    except Exception as error:
        print(f"Voice configuration warning: {error}")


configure_voice()


def speak_powershell(text):
    """
    Fallback TTS using Windows PowerShell. 
    Extremely reliable on Windows systems.
    """
    try:
        # Escape single quotes for PowerShell
        safe_text = text.replace("'", "''")
        ps_command = f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{safe_text}')"
        subprocess.run(["powershell", "-Command", ps_command], capture_output=True, check=True)
        return True
    except Exception as e:
        print(f"PowerShell TTS error: {e}")
        return False


async def _generate_audio_streaming(text, voice):
    """
    FAST streaming TTS: write chunks to disk progressively then play.
    This removes the "wait for full file" bottleneck.
    """
    communicate = edge_tts.Communicate(text, voice)
    # Use a temp path unique per call to avoid race conditions
    tmp_path = TEMP_AUDIO_FILE
    async with aiofiles.open(tmp_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                await f.write(chunk["data"])
    if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
        raise FileNotFoundError(f"[TTS] Streaming produced empty file: {tmp_path}")

async def _generate_audio(text):
    """Legacy save-to-file TTS — used as fallback if streaming fails."""
    communicate = edge_tts.Communicate(text, KIMI_VOICE)
    await communicate.save(TEMP_AUDIO_FILE)
    if not os.path.exists(TEMP_AUDIO_FILE):
        print(f"[TTS_DEBUG] Edge TTS reports success but file {TEMP_AUDIO_FILE} is missing.", flush=True)
    else:
        await asyncio.sleep(0.05)


def _speak_worker(text, voice=None):
    """
    Internal worker to handle audio playback.
    Uses fast streaming TTS (Edge TTS) with pygame playback.
    Falls back to pyttsx3 / PowerShell on failure.
    """
    global engine
    chosen_voice = voice or KIMI_VOICE
    try:
        # User-forced fallback to PowerShell.
        if os.getenv("FORCE_POWERSHELL_TTS", "false").lower() == "true":
            speak_powershell(text)
            return

        # Attempt high-quality neural TTS (streaming for speed)
        try:
            # Unload any previously loaded file on Windows to avoid permission errors.
            try:
                if pygame.mixer.get_init():
                    pygame.mixer.music.unload()
            except:
                pass

            # --- FAST PATH: Streaming TTS ---
            try:
                asyncio.run(_generate_audio_streaming(text, chosen_voice))
            except Exception as e:
                print(f"[TTS_DEBUG] Streaming failed: {e}")
                # Fallback to standard save-to-file
                asyncio.run(_generate_audio(text))
                
            # EXTRA SAFETY: verify file exists before letting pygame touch it
            if not os.path.exists(TEMP_AUDIO_FILE) or os.path.getsize(TEMP_AUDIO_FILE) == 0:
                 # If file is missing, wait a heartbeat for OS sync, then skip
                 time.sleep(0.1)
                 if not os.path.exists(TEMP_AUDIO_FILE) or os.path.getsize(TEMP_AUDIO_FILE) == 0:
                     raise FileNotFoundError(f"[TTS] Neural audio file missing or empty.")

            with speak_lock:
                if stop_event.is_set():
                    return
                
                # Check if file exists before loading
                if not os.path.exists(TEMP_AUDIO_FILE):
                     raise FileNotFoundError("[TTS] Audio file vanished before playback.")
                        raise FileNotFoundError(f"TTS file {TEMP_AUDIO_FILE} not created")

                pygame.mixer.music.load(TEMP_AUDIO_FILE)
                pygame.mixer.music.play()
                
                # Wait for playback or interruption
                while pygame.mixer.music.get_busy():
                    if stop_event.is_set():
                        pygame.mixer.music.stop()
                        break
                    time.sleep(0.05)
            # Success, so skip the fallback
            return
        except Exception as e:
            # Log the specific error to help with "fine tuning" debugging
            print(f"[TTS_DEBUG] Neural error: {e}")
            print(f"[TTS_NOTICE] Neural voice unavailable, using system fallback.")

        with speak_lock:
            if stop_event.is_set():
                return
            # Re-init engine if it crashed or is missing.
            if not engine:
                engine = pyttsx3.init()
                configure_voice()
            
            engine.say(text)
            engine.runAndWait()
    except Exception as error:
        print(f"Speech thread error: [Sanitized for TTS]")
        speak_powershell(text)

def speak(text, block=False, voice=None):
    """
    Convert text to speech. Prints text and plays audio asynchronously by default.
    Set block=True for startup or critical messages that must finish before proceeding.
    Pass voice= to override the TTS voice (e.g., for Hindi).
    """
    print(f"Kimi: {text}")
    
    # Always clear stop event before starting new speech
    stop_event.clear()

    chosen_voice = voice or KIMI_VOICE
    if block:
        _speak_worker(text, voice=chosen_voice)
    else:
        # Run speech in background thread so the main program can listen for "Kimi stop"
        threading.Thread(target=_speak_worker, args=(text,), kwargs={"voice": chosen_voice}, daemon=True).start()


def stop_speaking():
    """Immediately stop any ongoing TTS output."""
    global engine
    print("[SYSTEM] Interrupting speech...")
    stop_event.set()
    try:
        # Stop pygame playback immediately
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()

        with speak_lock:
            if engine:
                engine.stop()
    except Exception as e:
        print(f"Error stopping engine: {e}")
    
    # Also attempt to kill any background powershell TTS processes
    try:
        subprocess.run(["taskkill", "/IM", "powershell.exe", "/F"], capture_output=True, check=False)
    except:
        pass


def compose_action_reply(text):
    """
    Add a polished acknowledgement so Kimi sounds more like a premium agent.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return random.choice(AGENT_ACTION_ACKS) + "."
    return f"{random.choice(AGENT_ACTION_ACKS)}. {cleaned}"


def respond_and_remember(user_text, assistant_text, is_action=False):
    """
    Unified response helper for natural talk-back + conversation memory.
    """
    final_text = compose_action_reply(assistant_text) if is_action else assistant_text
    speak(final_text)
    add_to_history("user", user_text)
    add_to_history("assistant", final_text)


def add_to_history(role, content):
    """
    Add one message to runtime conversation history and trim old entries.
    This helps the AI remember short-term context from recent turns.
    """
    conversation_history.append({"role": role, "content": content})

    if len(conversation_history) > MAX_HISTORY_MESSAGES:
        # Keep only the most recent messages.
        overflow = len(conversation_history) - MAX_HISTORY_MESSAGES
        del conversation_history[:overflow]


def update_memory(command):
    """
    Extract simple user details from natural language and store them.
    Runtime-only memory (clears when app restarts).
    """
    text = command.strip()
    if not text:
        return

    # Pattern: "my name is kislay"
    name_match = re.search(r"\bmy name is\s+([a-zA-Z][a-zA-Z\s'-]{0,40})\b", text, re.IGNORECASE)
    if name_match:
        user_memory["name"] = name_match.group(1).strip().title()

    # Pattern: "i like gym"
    like_match = re.search(r"\bi like\s+([a-zA-Z0-9][a-zA-Z0-9\s'-]{0,60})\b", text, re.IGNORECASE)
    if like_match:
        item = like_match.group(1).strip().lower()
        likes = user_memory.get("likes", [])
        if item not in likes:
            likes.append(item)
        user_memory["likes"] = likes


def build_memory_context():
    """
    Convert stored user memory into short text for system guidance.
    This helps AI responses feel personalized and consistent.
    """
    parts = []
    if "name" in user_memory:
        parts.append(f"name: {user_memory['name']}")
    if "likes" in user_memory and user_memory["likes"]:
        parts.append("likes: " + ", ".join(user_memory["likes"]))

    if not parts:
        return "No personal details saved yet."
    return "Known user details -> " + "; ".join(parts) + "."


def open_browser():
    """Tool: open the default browser (Chrome preferred)."""
    return open_chrome()


def open_brave():
    """Tool: open Brave browser on Windows."""
    brave_paths = [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    ]
    for path in brave_paths:
        if os.path.exists(path):
            os.startfile(path)
            return "Opening Brave browser."

    # Fallback: attempt system app alias.
    try:
        subprocess.Popen(["cmd", "/c", "start", "", "brave"], shell=False)
        return "Opening Brave browser."
    except Exception:
        return "Brave browser was not found on this system."


def open_file_manager():
    """Tool: open Windows File Explorer (file manager)."""
    try:
        os.startfile("explorer.exe")
        return "Opening File Explorer."
    except Exception as error:
        return f"Failed to open File Explorer: {error}"


def open_whatsapp():
    """Tool: open WhatsApp desktop app using multiple launch strategies."""
    # 1) Common install paths (preferred for reliable process control).
    local_appdata = os.getenv("LOCALAPPDATA", "")
    candidate_paths = [
        Path(local_appdata) / r"WhatsApp\WhatsApp.exe",
        Path(local_appdata) / r"Programs\WhatsApp\WhatsApp.exe",
        Path(local_appdata) / r"WhatsApp Beta\WhatsApp Beta.exe",
    ]
    for exe_path in candidate_paths:
        try:
            if exe_path.exists():
                os.startfile(str(exe_path))
                return "Opening WhatsApp."
        except Exception:
            continue

    # 2) App alias fallback.
    try:
        subprocess.Popen(["cmd", "/c", "start", "", "WhatsApp.exe"], shell=False)
        return "Opening WhatsApp."
    except Exception:
        pass

    # 3) URI scheme fallback.
    try:
        os.startfile("whatsapp:")
        return "Opening WhatsApp."
    except Exception:
        return "WhatsApp was not found on this system."


def open_youtube():
    """Tool: open YouTube homepage."""
    webbrowser.open("https://www.youtube.com")
    return "Opening YouTube."


def search_youtube(query):
    """Tool: search YouTube for a specific query."""
    q = (query or "").strip()
    if not q:
        webbrowser.open("https://www.youtube.com")
        return "Opening YouTube."
    encoded = urllib.parse.quote_plus(q)
    webbrowser.open(f"https://www.youtube.com/results?search_query={encoded}")
    return f"Searching YouTube for {q}."


def play_youtube(query):
    """
    Tool: play first matching YouTube video.
    Uses pywhatkit when available; falls back to YouTube search page.
    """
    q = (query or "").strip() or "random video"

    if pywhatkit is not None:
        try:
            pywhatkit.playonyt(q)
            return f"Playing {q} on YouTube."
        except Exception as error:
            print(f"pywhatkit play fallback: {error}")

    # Fallback when pywhatkit is unavailable or fails.
    return search_youtube(q)


def close_browser():
    """Tool: close common browser windows on Windows (Chrome/Brave)."""
    try:
        closed_any = close_process_candidates(["chrome.exe", "brave.exe"])
        if closed_any:
            return "Closed browser windows."
        return "No Chrome or Brave browser window was running."
    except Exception as error:
        return f"Failed to close browser: {error}"


def get_running_process_names():
    """Return running process image names using Windows tasklist."""
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return []

        process_names = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith('"'):
                first = line.split('","', 1)[0].strip('"')
            else:
                first = line.split(",", 1)[0]
            if first:
                process_names.append(first)
        return process_names
    except Exception:
        return []


def close_process_candidates(candidates):
    """
    Try to close any running process from candidate image names.
    Returns True if at least one process was terminated.
    """
    closed_any = False
    for proc in candidates:
        try:
            result = subprocess.run(
                ["taskkill", "/IM", proc, "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                closed_any = True
        except Exception:
            continue
    return closed_any


def open_application(app_name):
    """
    Tool: open an application by name.
    Uses known mappings first, then Windows start command fallback.
    """
    name = (app_name or "").strip().lower()
    if not name:
        return "Please tell me which app to open."

    app_aliases = {
        "brave": open_brave,
        "brave browser": open_brave,
        "chrome": open_chrome,
        "google chrome": open_chrome,
        "browser": open_browser,
        "file manager": open_file_manager,
        "file explorer": open_file_manager,
        "explorer": open_file_manager,
        "files": open_file_manager,
        "whatsapp": open_whatsapp,
        "whats app": open_whatsapp,
    }
    mapped = app_aliases.get(name)
    if mapped:
        return mapped()

    # Try installed app index first for better reliability.
    installed_reply = open_installed_app(name)
    if not installed_reply.lower().startswith("i could not find an installed app"):
        return installed_reply

    try:
        subprocess.Popen(["cmd", "/c", "start", "", name], shell=False)
        return f"Opening {name}."
    except Exception:
        return f"I could not open {name} on this system."


def close_application(app_name):
    """
    Tool: close an application by name.
    Uses process name mapping and taskkill fallback.
    """
    name = (app_name or "").strip().lower()
    if not name:
        return "Please tell me which app to close."

    process_map = {
        "notepad": ["notepad.exe"],
        "chrome": ["chrome.exe"],
        "google chrome": ["chrome.exe"],
        "brave": ["brave.exe"],
        "brave browser": ["brave.exe"],
        "calculator": ["calculatorapp.exe", "calculator.exe"],
        "calc": ["calculatorapp.exe", "calculator.exe"],
        "whatsapp": ["WhatsApp.exe", "WhatsApp Beta.exe", "WhatsAppBeta.exe", "WhatsAppDesktop.exe"],
        "whats app": ["WhatsApp.exe", "WhatsApp Beta.exe", "WhatsAppBeta.exe", "WhatsAppDesktop.exe"],
        "file explorer": ["explorer.exe"],
        "file manager": ["explorer.exe"],
    }

    candidates = list(process_map.get(name, [name if name.endswith(".exe") else f"{name}.exe"]))

    # Dynamic fallback: add running process names that contain requested app keyword.
    keyword = re.sub(r"[^a-z0-9]+", "", name)
    for running in get_running_process_names():
        running_key = re.sub(r"[^a-z0-9]+", "", running.lower())
        if keyword and keyword in running_key and running not in candidates:
            candidates.append(running)

    try:
        closed_any = close_process_candidates(candidates)
        if closed_any:
            return f"Closed {name}."
        return f"{name} was not running."
    except Exception as error:
        return f"Failed to close {name}: {error}"


def get_start_menu_roots():
    """Return Start Menu program folders that contain installed app shortcuts."""
    roots = []
    appdata = os.getenv("APPDATA")
    program_data = os.getenv("PROGRAMDATA")
    if appdata:
        roots.append(Path(appdata) / r"Microsoft\Windows\Start Menu\Programs")
    if program_data:
        roots.append(Path(program_data) / r"Microsoft\Windows\Start Menu\Programs")
    return [r for r in roots if r.exists()]


def normalize_app_key(name):
    """Normalize app names for matching."""
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def build_app_index():
    """
    Build a comprehensive app index from:
    - Windows Start Apps (via PowerShell Get-StartApps) - The most reliable method.
    - Start Menu .lnk/.url entries - Reliable for traditional shortcuts.
    - Top-level .exe files in Program Files - Fallback for portable/manual installs.
    """
    index = {}

    # 1. Official Windows Start Apps (Primary Source)
    try:
        ps_cmd = ["powershell", "-Command", "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json"]
        result = subprocess.run(ps_cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0 and result.stdout.strip():
            raw_data = json.loads(result.stdout)
            # PowerShell might return a single dict if only 1 app exists, or a list.
            app_list = raw_data if isinstance(raw_data, list) else [raw_data]
            for app in app_list:
                name = app.get("Name")
                appid = app.get("AppID")
                if name and appid:
                    key = normalize_app_key(name)
                    # AppID based entries are prioritized as they use the official shell:AppsFolder launch.
                    index[key] = {"name": name, "appid": appid, "path": None}
    except Exception as e:
        print(f"StartApps indexing notice: {e}")

    # 2. Local Start Menu shortcuts (Secondary Source / Coverage for deep shortcuts)
    for root in get_start_menu_roots():
        for current_root, _, files in os.walk(root):
            for file in files:
                if not (file.lower().endswith(".lnk") or file.lower().endswith(".url") or file.lower().endswith(".exe")):
                    continue
                full_path = str(Path(current_root) / file)
                app_name = Path(file).stem
                key = normalize_app_key(app_name)
                # Don't overwrite AppID entries, but supplement with path based ones if missing.
                if key and key not in index:
                    index[key] = {"name": app_name, "appid": None, "path": full_path}

    # 3. Common Program Files executables (Safety Fallback)
    for env_key in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.getenv(env_key)
        if not base:
            continue
        base_path = Path(base)
        if not base_path.exists():
            continue
        try:
            for vendor_dir in base_path.iterdir():
                if not vendor_dir.is_dir():
                    continue
                # Check top-level and one nested level for app .exe launchers.
                candidates = []
                candidates.extend(vendor_dir.glob("*.exe"))
                for sub in vendor_dir.iterdir():
                    if sub.is_dir():
                        candidates.extend(sub.glob("*.exe"))

                for exe in candidates:
                    app_name = exe.stem
                    key = normalize_app_key(app_name)
                    if key and key not in index:
                        index[key] = {"name": app_name, "appid": None, "path": str(exe)}
        except Exception:
            continue

    return index


def get_app_index():
    """Get cached app index; build once per session."""
    global APP_INDEX_CACHE
    if APP_INDEX_CACHE is None:
        APP_INDEX_CACHE = build_app_index()
    return APP_INDEX_CACHE


def find_installed_app(app_name):
    """Find best installed app match by exact/partial/fuzzy matching."""
    query = normalize_app_key(app_name or "")
    if not query:
        return None

    index = get_app_index()
    if not index:
        return None

    # Exact match first.
    if query in index:
        return index[query]

    # Partial contains match.
    for key, value in index.items():
        if query in key or key in query:
            return value

    # Fuzzy fallback.
    choices = list(index.keys())
    best = difflib.get_close_matches(query, choices, n=1, cutoff=0.72)
    if best:
        return index[best[0]]
    return None


def open_installed_app(app_name):
    """
    Open an installed app from indexed AppIDs or shortcuts/executables.
    Prioritizes official Windows shell:AppsFolder launch for reliability.
    """
    match = find_installed_app(app_name)
    if not match:
        # Final fallback - if a common name like WhatsApp is used but no shortcut exists,
        # try to start the executable name directly as a last resort.
        likely_exe = f"{app_name}.exe"
        try:
            subprocess.Popen(["cmd", "/c", "start", "", likely_exe], shell=True)
            return f"Attempting to start {app_name}."
        except Exception:
            return f"I could not find an installed app named {app_name}."

    try:
        # Priority 1: Launch via official AppID.
        if match.get("appid"):
            # Using 'start shell:AppsFolder\AppID' is often more robust than explorer.exe
            cmd = f'start shell:AppsFolder\\{match["appid"]}'
            subprocess.Popen(["cmd", "/c", cmd], shell=True)
            return f"Opening {match['name']}."

        # Priority 2: Launch via path (shortcut or exe).
        if match.get("path"):
            os.startfile(match["path"])
            return f"Opening {match['name']}."

        return f"I found {app_name}, but I don't have a valid way to open it."
    except Exception as error:
        # Last ditch effort on error
        try:
            subprocess.Popen(["cmd", "/c", "start", "", f"{match['name']}.exe"], shell=True)
            return f"Opening {match['name']}."
        except Exception:
            return f"Failed to open {match['name']}: {error}"


def list_installed_apps(query=""):
    """List installed apps (optionally filtered by query)."""
    index = get_app_index()
    if not index:
        return "I could not find installed apps on this system."

    apps = sorted(index.values(), key=lambda x: x["name"].lower())
    if query:
        q = normalize_app_key(query)
        filtered = []
        for app in apps:
            key = normalize_app_key(app["name"])
            if q in key:
                filtered.append(app)
        apps = filtered

    if not apps:
        return "No installed apps matched your query."

    names = [a["name"] for a in apps[:MAX_APP_LIST_RESULTS]]
    return "Installed apps: " + ", ".join(names)


def tell_time():
    """Tool: report current system time."""
    current_time = datetime.datetime.now().strftime("%I:%M %p")
    return f"The current time is {current_time}."


def get_weather(city=None):
    """
    Tool: get current weather for a city using wttr.in.
    If no city is provided, it tries to detect location automatically.
    """
    try:
        query = (city or "").strip().replace(" ", "+")
        # %C = Condition, %t = Temperature
        url = f"https://wttr.in/{query}?format=%C+%t"
        headers = {"User-Agent": "curl"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            result = response.text.strip()
            if "Unknown location" in result:
                return "I could not find weather for that location."
            location_label = f"in {city}" if city else "locally"
            return f"The weather {location_label} is {result}."
        return "I am having trouble accessing weather data right now."
    except Exception as error:
        return f"Weather search error: {error}"


def get_cricket_scores():
    """
    Tool: fetch top 3 live cricket scores from Cricbuzz.
    """
    try:
        url = "https://www.cricbuzz.com/cricket-match/live-scores"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        
        matches = []
        for match in soup.find_all("div", class_="cb-mtch-lst"):
            try:
                teams = match.find("h3").text.strip()
                score_div = match.find("div", class_="cb-lv-scrs-col")
                status = match.find("div", class_="cb-text-complete") or match.find("div", class_="cb-text-live")
                
                score_text = score_div.text.strip() if score_div else "Score not available"
                status_text = f" ({status.text.strip()})" if status else ""
                
                matches.append(f"{teams}: {score_text}{status_text}")
                if len(matches) >= 3:
                    break
            except Exception:
                continue

        # If no live matches, check for upcoming matches for the day
        if not matches:
            for match in soup.find_all("div", class_="cb-mtch-lst"):
                try:
                    teams = match.find("h3").text.strip()
                    # Look for date/time or "Scheduled" text
                    status = match.find("div", class_="cb-text-preview") or match.find("div", class_="cb-nm-tm")
                    if status:
                        matches.append(f"{teams} (Scheduled: {status.text.strip()})")
                    if len(matches) >= 3:
                        break
                except Exception:
                    continue

        if not matches:
            return "There are no live or upcoming cricket matches currently listed for today."
        return "Match details: " + " | ".join(matches)
    except Exception as error:
        return f"Cricket score error: {error}"


def set_timer(minutes, message="Timer"):
    """
    Tool: set a background timer that notifies the user when finished.
    """
    try:
        mins = float(minutes)
        seconds = int(mins * 60)
        if seconds <= 0:
            return "The timer duration must be greater than zero."

        def timer_callback():
            # Wait for the duration.
            time.sleep(seconds)
            # Notify the user using the global TTS engine safely.
            # Using a separate speak-like notification.
            notification = f"Your timer for {int(mins)} minutes is up! {message}."
            speak(notification)

        # Start the timer in a background thread so it doesn't block the main assistant.
        threading.Thread(target=timer_callback, daemon=True).start()
        return f"Starting a timer for {int(mins)} minutes."
    except (ValueError, TypeError):
        return "Please provide a valid number of minutes."


def get_search_roots():
    """
    Build file-search roots across common user folders and available drives.
    This allows Kimi to find files beyond the project folder.
    """
    roots = []
    home = Path.home()
    common_dirs = [
        home,
        home / "Desktop",
        home / "Documents",
        home / "Downloads",
        home / "Pictures",
        home / "Videos",
    ]
    for d in common_dirs:
        if d.exists():
            roots.append(d)

    # Include existing Windows drive roots (C:, D:, E:, ...).
    for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        drive = Path(f"{letter}:\\")
        if drive.exists():
            roots.append(drive)

    # Deduplicate while preserving order.
    unique = []
    seen = set()
    for root in roots:
        key = str(root).lower()
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def find_files(file_query, limit=MAX_FILE_SEARCH_RESULTS):
    """
    Search for files by partial name across configured roots.
    Returns a list of absolute file paths.
    """
    query = (file_query or "").strip().lower()
    if not query:
        return []

    matches = []
    roots = get_search_roots()
    start_time = time.monotonic()

    for root in roots:
        try:
            for current_root, dirs, files in os.walk(root):
                # Avoid long blocking scans.
                if time.monotonic() - start_time > FILE_SEARCH_TIME_BUDGET_SEC:
                    return matches

                # Skip heavy or protected folders to reduce errors/latency.
                lower_root = current_root.lower()
                if any(skip in lower_root for skip in ("\\windows\\", "\\program files\\windowsapps", "\\$recycle.bin")):
                    continue

                for filename in files:
                    if query in filename.lower():
                        full_path = str(Path(current_root) / filename)
                        matches.append(full_path)
                        if len(matches) >= limit:
                            return matches
        except Exception:
            # Continue on permission/access errors.
            continue

    return matches


def search_web(query, max_results=3):
    """
    Tool: search the web for real-time information.
    Limited to 3 results to ensure fast responses.
    """
    q = (query or "").strip()
    if not q:
        return "Please tell me what to search for, boss."
    
    if DDGS is None:
        return "I'm sorry boss, but the web search library is not installed."

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(q, max_results=max_results))
            if not results:
                return f"I couldn't find any web results for '{q}', boss."
            
            output = []
            for r in results:
                title = r.get("title", "No Title")
                snippet = r.get("body", "No Snippet")
                link = r.get("href", "#")
                output.append(f"• {title}\n  {snippet}\n  (Link: {link})")
            
            summary = "\n\n".join(output)
            return f"Here's what I found online for '{q}', boss:\n\n{summary}"
    except Exception as e:
        return f"Search error while looking for '{q}': {e}"


def open_file(file_path=None, file_name=None):
    """
    Tool: open a file by exact path or by searching file name.
    """
    if file_path:
        candidate = Path(os.path.expandvars(os.path.expanduser(file_path.strip().strip('"'))))
        if candidate.exists() and candidate.is_file():
            os.startfile(str(candidate))
            return f"Opening file {candidate.name}."

    if file_name:
        results = find_files(file_name, limit=1)
        if results:
            os.startfile(results[0])
            return f"Opening file {Path(results[0]).name}."
        return f"I could not find a file matching {file_name}."

    return "Please provide a file path or file name."


def find_file(file_name):
    """
    Tool: search for file matches and return short result list.
    """
    results = find_files(file_name, limit=5)
    if not results:
        return f"No files found for {file_name}."
    names = [Path(p).name for p in results]
    return "Found files: " + ", ".join(names)


# Tool registry maps AI-callable names to python implementations.
TOOL_REGISTRY = {
    "open_youtube": {
        "function": open_youtube,
        "description": "opens YouTube in browser",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "search_youtube": {
        "function": search_youtube,
        "description": "searches YouTube for a query",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The YouTube search query."}
            },
            "required": ["query"],
        },
    },
    "play_youtube": {
        "function": play_youtube,
        "description": "plays the first matching YouTube video for a query",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to play on YouTube."}
            },
            "required": ["query"],
        },
    },
    "open_brave": {
        "function": open_brave,
        "description": "opens Brave browser",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "open_whatsapp": {
        "function": open_whatsapp,
        "description": "opens WhatsApp desktop app",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "open_file_manager": {
        "function": open_file_manager,
        "description": "opens Windows File Explorer",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "open_application": {
        "function": open_application,
        "description": "opens a desktop application by app name",
        "parameters": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "Application name to open."}
            },
            "required": ["app_name"],
        },
    },
    "open_installed_app": {
        "function": open_installed_app,
        "description": "opens an installed application by name from indexed app list",
        "parameters": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "Installed app name to open."}
            },
            "required": ["app_name"],
        },
    },
    "close_application": {
        "function": close_application,
        "description": "closes a desktop application by app name",
        "parameters": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "Application name to close."}
            },
            "required": ["app_name"],
        },
    },
    "list_installed_apps": {
        "function": list_installed_apps,
        "description": "lists installed applications, optionally filtered by query",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Optional search text for app names."}
            },
            "required": [],
        },
    },
    "open_file": {
        "function": open_file,
        "description": "opens a file by absolute path or by searching file name",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute or user-relative file path."},
                "file_name": {"type": "string", "description": "File name or partial name to search."},
            },
            "required": [],
        },
    },
    "find_file": {
        "function": find_file,
        "description": "searches and lists matching files by name",
        "parameters": {
            "type": "object",
            "properties": {
                "file_name": {"type": "string", "description": "File name or partial file name."}
            },
            "required": ["file_name"],
        },
    },
    "open_browser": {
        "function": open_browser,
        "description": "opens Google Chrome or default browser",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "close_browser": {
        "function": close_browser,
        "description": "closes Google Chrome browser windows",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "tell_time": {
        "function": tell_time,
        "description": "tells current local system time",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "get_weather": {
        "function": get_weather,
        "description": "gets current weather for a specific city or local area",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "Optional city name."}
            },
            "required": [],
        },
    },
    "get_cricket_scores": {
        "function": get_cricket_scores,
        "description": "gets live cricket scores for ongoing matches",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "set_timer": {
        "function": set_timer,
        "description": "sets a background timer/alarm for a specified number of minutes",
        "parameters": {
            "type": "object",
            "properties": {
                "minutes": {"type": "number", "description": "Number of minutes for the timer."},
                "message": {"type": "string", "description": "Optional label or reminder for the timer."}
            },
            "required": ["minutes"],
        },
    },
    "search_web": {
        "function": search_web,
        "description": "searches the web for real-time information, news, sports scores, movie details, and general knowledge",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query for live information."}
            },
            "required": ["query"],
        },
    },
}

# ---------------------------------------------------------------------------
# Pre-build the Gemini tools list ONCE at startup.
# Re-creating 20+ FunctionDeclaration objects on every AI call adds latency.
# ---------------------------------------------------------------------------
_CACHED_GEMINI_TOOLS = None

def _get_gemini_tools():
    """Return pre-built Gemini tools list compatible with v1 SDK."""
    global _CACHED_GEMINI_TOOLS
    if _CACHED_GEMINI_TOOLS is None:
        # In v1 SDK, we can pass function definitions directly or as Tools.
        _CACHED_GEMINI_TOOLS = []
        for name, spec in TOOL_REGISTRY.items():
            _CACHED_GEMINI_TOOLS.append({
                "function_declarations": [{
                    "name": name,
                    "description": spec["description"],
                    "parameters": spec["parameters"]
                }]
            })
    return _CACHED_GEMINI_TOOLS


def execute_tool_by_name(tool_name, args=None):
    """
    Execute a tool directly by registry name.
    Useful as a safety fallback when model outputs malformed function text.
    """
    spec = TOOL_REGISTRY.get(tool_name)
    if not spec:
        return f"Tool error: unknown tool '{tool_name}'."

    payload = args or {}
    if not isinstance(payload, dict):
        payload = {}

    try:
        return str(spec["function"](**payload))
    except TypeError:
        return f"Tool error: invalid arguments for '{tool_name}'."
    except Exception as error:
        return f"Tool error while running '{tool_name}': {error}"


def try_execute_embedded_function_text(text):
    """
    Parse malformed model outputs like:
    'function=close_browser></function>'
    and execute the referenced tool instead of speaking raw markup.
    """
    if not text:
        return None

    match = re.search(r"function\s*=\s*([a-zA-Z_][a-zA-Z0-9_]*)", text)
    if not match:
        return None

    tool_name = match.group(1).strip()
    return execute_tool_by_name(tool_name, {})


def split_multi_commands(command):
    """
    Split one spoken sentence into sequential sub-commands.
    Example: "open youtube and play something" ->
    ["open youtube", "play something"].
    """
    text = command.strip()
    if not text:
        return []

    parts = re.split(r"\s+(?:and then|and|then)\s+", text, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


def normalize_subcommand(subcommand):
    """
    Normalize ambiguous follow-up phrases for better tool decisions.
    Example: "play something" -> "search youtube random video".
    """
    text = subcommand.strip().lower()
    if re.search(r"\bplay\s+(something|anything|a video|video)\b", text):
        return "play youtube random video"
    return subcommand


def extract_video_query(command):
    """
    Extract user-friendly video query from play/show phrases.
    Returns None when no media-style intent is detected.
    """
    text = command.strip().lower()
    if not text:
        return None

    media_words = {"play", "show", "video", "videos", "youtube", "on", "me", "any", "a"}
    if "play" not in text and "show" not in text:
        return None
    if "video" not in text and "youtube" not in text:
        return None

    tokens = re.findall(r"[a-z0-9']+", text)
    cleaned = [t for t in tokens if t not in media_words]
    query = " ".join(cleaned).strip()
    return query or "random video"


def try_local_quick_actions(command):
    """
    Reliability layer for high-frequency actions.
    This runs before AI to avoid tool-call model quirks on simple commands.
    Returns tuple: (handled: bool, should_continue: bool)
    """
    text = command.lower().strip()

    if "what is the time" in text or "tell me time" in text or "current time" in text:
        speak("Checking the time for you, boss.")
        reply = f"{tell_time()} Anything else, boss?"
        speak(reply)
        add_to_history("user", command)
        add_to_history("assistant", reply)
        return True, True

    if "weather" in text:
        # Simple extraction for "weather in [city]"
        city_match = re.search(r"weather in\s+([a-zA-Z\s]+)", text)
        city = city_match.group(1).strip() if city_match else None
        speak(f"Getting the weather {'in ' + city if city else 'for you'}, boss.")
        reply = f"{get_weather(city)} How's that, boss?"
        speak(reply)
        add_to_history("user", command)
        add_to_history("assistant", reply)
        return True, True

    if any(k in text for k in ["cricket", "score", "ipl", "match today", "points table"]):
        speak("Fetching the latest match details for you, boss.")
        reply = f"{get_cricket_scores()} Hope your team is winning, boss!"
        speak(reply)
        add_to_history("user", command)
        add_to_history("assistant", reply)
        return True, True

    timer_match = re.search(r"(?:set|start|remind me in)\s+(?:a\s+)?(?:timer\s+)?(?:for\s+)?(\d+)\s+(minute|second)s?", text)
    if timer_match:
        val = timer_match.group(1)
        unit = timer_match.group(2)
        mins = float(val) if unit == "minute" else float(val) / 60
        speak(f"Setting a timer for {val} {unit}s, boss.")
        reply = f"{set_timer(mins)} I'll let you know when it's done, boss."
        speak(reply)
        add_to_history("user", command)
        add_to_history("assistant", reply)
        return True, True

    if "open youtube" in text:
        speak("Sure thing boss, opening YouTube.")
        open_youtube()
        add_to_history("user", command)
        add_to_history("assistant", "Opening YouTube, boss.")
        return True, True

    if "open brave" in text or "launch brave" in text:
        speak("Right away boss, launching Brave.")
        open_brave()
        add_to_history("user", command)
        add_to_history("assistant", "Opening Brave browser, boss.")
        return True, True

    if "open whatsapp" in text or "launch whatsapp" in text or "start whatsapp" in text:
        speak("Connecting you to WhatsApp, boss.")
        open_whatsapp()
        add_to_history("user", command)
        add_to_history("assistant", "WhatsApp is open, boss.")
        return True, True

    if "open file manager" in text or "open file explorer" in text or "open explorer" in text:
        speak("Opening your files, boss.")
        open_file_manager()
        add_to_history("user", command)
        add_to_history("assistant", "Exploring files for you, boss.")
        return True, True

    list_apps_match = re.search(r"\b(?:list|show)\s+(?:installed\s+)?apps\b", text)
    if list_apps_match:
        speak("Listing your installed apps now, boss.")
        reply = f"{list_installed_apps()} Here's the list, boss."
        speak(reply)
        add_to_history("user", command)
        add_to_history("assistant", reply)
        return True, True

    if "close youtube" in text or "close browser" in text or "close chrome" in text:
        speak("Closing the browser for you, boss.")
        close_browser()
        add_to_history("user", command)
        add_to_history("assistant", "Browser closed, boss.")
        return True, True

    close_match = re.search(r"\b(?:close|quit|exit)\s+([a-zA-Z0-9][a-zA-Z0-9\s._-]{1,40})\b", text)
    if close_match:
        app_name = close_match.group(1).strip()
        # Prevent collision with assistant shutdown command.
        if app_name not in {"assistant", "kimi"}:
            speak(f"Closing {app_name}, boss.")
            reply = f"{close_application(app_name)} Done, boss."
            speak(reply)
            add_to_history("user", command)
            add_to_history("assistant", reply)
            return True, True

    # File open by explicit path in quotes.
    quoted_path_match = re.search(r'"([a-zA-Z]:\\[^"]+)"', command)
    if quoted_path_match:
        path = quoted_path_match.group(1)
        speak(f"Opening the file for you, boss.")
        reply = f"{open_file(file_path=path)} Open and ready, boss."
        speak(reply)
        add_to_history("user", command)
        add_to_history("assistant", reply)
        return True, True

    # File open by name: "open file resume.pdf"
    file_name_match = re.search(r"\bopen\s+file\s+(.+)$", text)
    if file_name_match:
        file_name = file_name_match.group(1).strip()
        speak(f"Searching for {file_name}, boss.")
        reply = f"{open_file(file_name=file_name)} Found it and opened it, boss."
        speak(reply)
        add_to_history("user", command)
        add_to_history("assistant", reply)
        return True, True

    # Generic open/launch/start app fallback.
    app_match = re.search(r"\b(?:open|launch|start)\s+([a-zA-Z0-9][a-zA-Z0-9\s._-]{1,40})\b", text)
    if app_match:
        app_name = app_match.group(1).strip()
        # Skip explicit youtube play/search phrases already handled elsewhere.
        if "youtube" not in app_name or app_name in {"youtube app"}:
            speak(f"Opening {app_name} for you, boss.")
            reply = open_installed_app(app_name)
            if reply.lower().startswith("i could not find an installed app"):
                reply = open_application(app_name)
            add_to_history("user", command)
            add_to_history("assistant", f"Opening {app_name}, boss.")
            return True, True

    video_query = extract_video_query(command)
    if video_query is not None:
        speak(f"Playing {video_query} on YouTube, boss.")
        play_youtube(video_query)
        add_to_history("user", command)
        add_to_history("assistant", f"Enjoy the video, boss!")
        return True, True

    # Web search explicit command: "search for [topic]"
    search_match = re.search(r"\b(?:search for|find out about|look up|get details on)\s+(.+)$", text)
    if search_match:
        query = search_match.group(1).strip()
        speak(f"Searching the web for {query}, boss.")
        reply = search_web(query)
        speak(reply)
        add_to_history("user", command)
        add_to_history("assistant", reply)
        return True, True

    # News/Scores catch-all removed to ensure AI summarizes the results 
    # instead of reading raw search output.

    return False, True


def unified_voice_callback(recognizer, audio):
    """
    The PRIMARY voice listener. It runs in its own background thread.
    - ONE fast STT call (avoids the double-call latency bug).
    - Detects language from Devanagari chars in the result.
    - Sets TTS voice for this turn before queuing the command.
    """
    global current_lang, KIMI_VOICE
    try:
        if not stop_listening_callback:
            return

        # ONE recognition call with en-IN.
        # en-IN handles Indian English perfectly. If the user speaks pure Hindi,
        # Google returns Devanagari script which we detect below.
        try:
            text = recognizer.recognize_google(audio, language="en-IN").strip()
        except sr.UnknownValueError:
            return  # Silence or unclear audio — just skip quietly
        except sr.RequestError as e:
            print(f"[STT_ERROR] Google STT unavailable: {e}", flush=True)
            return

        if not text:
            return

        # Detect language from Devanagari characters in the recognized text
        devanagari_count = sum(1 for c in text if '\u0900' <= c <= '\u097F')
        detected_lang = "hi" if devanagari_count >= 2 else "en"

        current_lang = detected_lang
        KIMI_VOICE = KIMI_VOICE_HI if detected_lang == "hi" else KIMI_VOICE_EN
        print(f"[LISTENER_LOG] Lang={detected_lang.upper()} | Heard: '{text}'", flush=True)

        text_lower = text.lower()

        # IMMEDIATE CONTROL COMMANDS (English + Hindi variants)
        if any(k in text_lower for k in ["kimi stop", "stop speaking", "kimi bas", "kimi ruko"]):
            print("[CONTROL] Stop triggered.", flush=True)
            stop_speaking()
            return

        if any(k in text_lower for k in ["kimi shut down", "kimi shutdown", "kimi band karo", "kimi band"]):
            print("[CONTROL] Shutdown triggered.", flush=True)
            stop_speaking()
            shutdown_event.set()
            return

        # Queue for main brain
        voice_command_queue.put(text)

    except Exception as e:
        print(f"[LISTENER_ERROR] {e}", flush=True)


def open_chrome():
    """
    Try to open Google Chrome directly on Windows.
    If Chrome path is not found, open Google in default browser.
    """
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]

    for path in chrome_paths:
        if os.path.exists(path):
            os.startfile(path)
            return "Opening Google Chrome."

    # Fallback if Chrome executable is not found.
    webbrowser.open("https://www.google.com")
    return "Chrome was not found, opening Google in your default browser."

def transform_history_for_genai(history):
    """Transform Kimi role-based history into v1 SDK content segments."""
    genai_history = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        # In v1 SDK, history is list of dicts with role and parts.
        genai_history.append({
            "role": role,
            "parts": [{"text": msg["content"]}]
        })
    return genai_history


def get_ai_response(prompt):
    """
    Send user prompt to Gemini model using google-generativeai (v1 SDK).
    Implements model names: gemini-1.5-flash / gemini-1.5-pro with failure retry.
    """
    if not _setup_genai():
        return "Boss, I'm missing my API key. Please check the .env file."

    # Final logic: Force model list to follow user requirement
    primary_model = os.getenv("KIMI_MODEL", "gemini-1.5-flash")
    fallback_model = "gemini-1.5-pro"

    for attempt in range(2): # Try Primary then Pro
        current_model_name = primary_model if attempt == 0 else fallback_model
        
        if attempt == 1:
            print(f"[AI_FALLBACK] Primary model failed. Triggering fallback to: {current_model_name}", flush=True)

        print(f"[AI_LOG] Using model: {current_model_name}", flush=True)

        try:
            # Reconfiguring model instance on each turn ensures we catch name changes.
            model = genai.GenerativeModel(
                model_name=current_model_name,
                tools=_get_gemini_tools(),
                system_instruction=(
                    "You are Kimi, a sophisticated AI assistant. Be extremely concise (1-2 sentences). "
                    + ("Reply in Hindi." if current_lang == "hi" else "Reply in English.")
                    + f" {build_memory_context()}"
                )
            )

            # Start chat with transformed history
            chat = model.start_chat(history=transform_history_for_genai(conversation_history))
            response = chat.send_message(prompt)

            # Extract text safely as per requirement
            final_reply = ""
            if response.candidates:
                # Part 1: Text parts
                for part in response.candidates[0].content.parts:
                    if part.text:
                        final_reply += part.text
                    
                    # Tool calling part
                    if part.function_call:
                        t_name = part.function_call.name
                        t_args = dict(part.function_call.args)
                        print(f"[AI_ACTION] Executing tool: {t_name}")
                        t_result = execute_tool_by_name(t_name, t_args)
                        
                        # Send result back
                        try:
                            f_up = chat.send_message({
                                "role": "function",
                                "parts": [{
                                    "function_response": {
                                        "name": t_name,
                                        "response": {"result": t_result}
                                    }
                                }]
                            })
                            if f_up.candidates:
                                for r_p in f_up.candidates[0].content.parts:
                                    if r_p.text: final_reply += " " + r_p.text
                        except Exception as fe:
                            print(f"Tool follow-up error: {fe}")
                            final_reply += " Task handled, boss."

            final_reply = final_reply.strip() or "I've handled that, boss."
            add_to_history("user", prompt)
            add_to_history("assistant", final_reply)
            return final_reply

        except Exception as e:
            err_str = str(e).lower()
            # If 429 quota, wait and retry SAME model first before switching
            if "429" in err_str or "resource_exhausted" in err_str:
                print(f"[RETRY] Quota hit. Waiting 5 seconds...", flush=True)
                time.sleep(5)
                # Note: this counts as an 'attempt' in this loop structure, 
                # but we'll allow it to fallback if it hits twice.
                if attempt < 1: continue 
            
            if attempt < 1:
                print(f"[AI_ERROR] Primary failed: {e}")
                continue
            
            print(f"[GENAI_ERROR] Both models failed: {e}")
            return "I'm having trouble connecting to my AI service right now."

    return "I'm having trouble connecting to my AI service right now."
    
    return "I'm still a bit dazed, boss. Can we try again?"


def process_command(command):
    """
    Process recognized command text and perform matching action.
    Returns False if user asks to stop, otherwise True.
    """
    if not command:
        return True

    # Strip "Kimi" wake-word if present for cleaner processing (e.g., "Kimi open chrome" -> "open chrome")
    clean_text = command.lower().strip()
    if clean_text.startswith("kimi "):
        clean_text = clean_text[len("kimi "):].strip()

    # Priority check for shut down / stop commands
    if command.lower().strip() in EXIT_KEYWORDS or clean_text in EXIT_KEYWORDS:
        reply = "Understood, boss. Shutting down now. Goodbye!"
        speak(reply, block=True)
        add_to_history("user", command)
        add_to_history("assistant", reply)
        return False

    # Proceed with the cleaned text for further processing
    command = clean_text if clean_text else command


    # Update lightweight personalization memory from user text.
    update_memory(command)

    # Reliability shortcut for common media requests (play/open YouTube).
    handled, should_continue = try_local_quick_actions(command)
    if handled:
        return should_continue

    # Multi-step command handling: split on "and/then" and execute sequentially.
    subcommands = split_multi_commands(command)
    if not subcommands:
        speak("Can you repeat that?")
        return True

    step_responses = []
    for raw_step in subcommands:
        step = normalize_subcommand(raw_step)
        if not step:
            continue
        ai_reply = get_ai_response(step)
        # Fast feedback for long AI queries
        if "latest" in step or "news" in step or "search" in step:
            speak("I've found some updates for you, boss. Summarizing now...")
        
        step_responses.append(ai_reply)

    if not step_responses:
        speak("Can you repeat that?")
        return True

    # Speak using the voice selected during the recognition phase
    reply_voice = KIMI_VOICE_HI if current_lang == "hi" else KIMI_VOICE_EN
    if len(step_responses) == 1:
        speak(step_responses[0], voice=reply_voice)
    else:
        # Multi-step summary keeps response descriptive and not just "Done".
        speak(" Then ".join(step_responses), voice=reply_voice)

    return True


def main():
    """
    Run Kimi using a Unified Listener architecture.
    The main thread waits on a command queue, while a single background thread handles the mic.
    """
    global stop_listening_callback

    # Initial boot sequence
    startup_msg = "Kimi is online and ready for you, boss."
    print(f"\n[BOOT] {startup_msg}", flush=True)

    # Pre-warm: initialize Gemini client + tools NOW so first command is instant
    print("[BOOT] Pre-warming Gemini client and tools...", flush=True)
    try:
        _setup_genai()
        _get_gemini_tools()
        print("[BOOT] Gemini AI ready.", flush=True)
    except Exception as e:
        print(f"[BOOT_WARN] Gemini pre-warm failed: {e}", flush=True)

    speak(startup_msg, block=True)

    try:
        # Calibrate ambient noise ONCE before starting the unified listener
        print("[BOOT] Calibrating microphone... Please stay quiet.", flush=True)
        with global_mic as source:
            global_recognizer.adjust_for_ambient_noise(source, duration=1.0)
        
        # Start the background unified listener thread
        # This thread will handle stop/shutdown AND put commands in voice_command_queue
        print("[BOOT] Unified listener starting...", flush=True)
        stop_listening_callback = global_recognizer.listen_in_background(
            global_mic, 
            unified_voice_callback, 
            phrase_time_limit=8
        )
        print("[BOOT] Kimi is ready for your commands.", flush=True)
        
    except Exception as e:
        print(f"[BOOT_ERROR] Critical failure during microphone initialization: {e}", flush=True)
        return

    while not shutdown_event.is_set():
        try:
            # Wait for a command from the background listener
            # Timeout allows for periodic check of shutdown_event
            try:
                heard_text = voice_command_queue.get(timeout=1.0)
            except queue.Empty:
                continue
                
            if not heard_text:
                continue

            # Process the command found in the queue
            should_continue = process_command(heard_text)
            if not should_continue or shutdown_event.is_set():
                break
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[BRAIN_ERROR] Loop error: {e}", flush=True)
            continue

    # Cleanup shutdown sequence
    print("\n[EXIT] Shutting down Kimi processes...", flush=True)
    if stop_listening_callback:
        try:
            stop_listening_callback(wait_for_stop=False)
        except:
            pass
    
    # Release audio resources and forcefully terminate
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.quit()
    except:
        pass

    try:
        if engine:
            engine.stop()
    except:
        pass

    # Force exit to ensure no lingering threads hold up the terminal
    os._exit(0)



if __name__ == "__main__":
    main()
