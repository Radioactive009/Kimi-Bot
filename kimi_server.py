import os
import subprocess
from pathlib import Path
from typing import Optional

import psutil
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()


def _parse_allowed_origins() -> list[str]:
    raw = os.getenv("KIMI_ALLOWED_ORIGINS", "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


SERVER_TOKEN = os.getenv("KIMI_SERVER_TOKEN", "").strip()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_allowed_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Kimi-Token"],
)


def require_toggle_auth(x_kimi_token: Optional[str] = Header(default=None, alias="X-Kimi-Token")):
    if SERVER_TOKEN and x_kimi_token != SERVER_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Kimi-Token header.")


class KimiManager:
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None

    def is_running(self):
        if self.process is None:
            return False
        if self.process.poll() is None:
            return True
        self.process = None
        return False

    def activate(self):
        if self.is_running():
            return {"status": "already_running"}

        try:
            script_path = Path(__file__).resolve().parent / "kimi.py"
            self.process = subprocess.Popen(
                ["python", str(script_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            return {"status": "activated"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def deactivate(self):
        if not self.is_running():
            return {"status": "not_running"}

        try:
            parent = psutil.Process(self.process.pid)
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
            self.process = None
            return {"status": "deactivated"}
        except Exception as e:
            if self.process:
                self.process.kill()
                self.process = None
                return {"status": "deactivated_fallback"}
            raise HTTPException(status_code=500, detail=str(e))


manager = KimiManager()


@app.get("/status")
def get_status():
    return {"active": manager.is_running()}


@app.post("/toggle")
def toggle_kimi(_: None = Depends(require_toggle_auth)):
    if manager.is_running():
        return manager.deactivate()
    return manager.activate()


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("KIMI_SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("KIMI_SERVER_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
