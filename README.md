# Kimi Voice Assistant

Kimi is a Python voice assistant with:
- always-on microphone listening
- local tool actions (open apps/files, timer, weather, etc.)
- Gemini fallback for general queries
- optional FastAPI + React dashboard control

## Project Files

- `kimi.py`: main assistant runtime
- `kimi_server.py`: FastAPI process manager (`/status`, `/toggle`)
- `frontend/`: Vite React dashboard
- `requirements.txt`: Python dependencies

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Create `.env` in project root:

```text
GEMINI_API_KEY=your_key_here
# Optional override
KIMI_MODEL=gemini-1.5-flash
```

3. Run Kimi directly:

```bash
python kimi.py
```

## Backend Server (Optional)

Run:

```bash
python kimi_server.py
```

Security and network options:

```text
# Optional: require this token on POST /toggle via X-Kimi-Token header
KIMI_SERVER_TOKEN=change_me

# Optional CORS allowlist (comma-separated)
KIMI_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# Optional bind settings
KIMI_SERVER_HOST=127.0.0.1
KIMI_SERVER_PORT=8000
```

## Frontend (Optional)

From `frontend/`:

```bash
npm install
npm run dev
```

Optional frontend env (`frontend/.env`):

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_KIMI_SERVER_TOKEN=change_me
```

## Verification Scripts

- `python check_imports.py`
- `python verification_test.py`
- `python verify_gemini.py`
- `python test_key.py`
- `python list_models.py`

## Notes

- Kimi no longer auto-installs packages at runtime.
- Missing dependencies now fail safely with clear install guidance.
- The server is localhost-first by default and supports optional auth for toggling.
