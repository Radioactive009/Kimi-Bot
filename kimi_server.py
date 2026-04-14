from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import os
import signal
import psutil
from typing import Optional

app = FastAPI()

# Enable CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class KimiManager:
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None

    def is_running(self):
        if self.process is None:
            return False
        # Check if process is still alive
        if self.process.poll() is None:
            return True
        self.process = None
        return False

    def activate(self):
        if self.is_running():
            return {"status": "already_running"}
        
        # Start kimi.py as a subprocess
        # We use a new session to ensure it doesn't get culled easily
        try:
            # Using absolute path for kimi.py to be safe
            script_path = os.path.join(os.getcwd(), "kimi.py")
            # We use python.exe explicitly for Windows
            self.process = subprocess.Popen(
                ["python", script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
            return {"status": "activated"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def deactivate(self):
        if not self.is_running():
            return {"status": "not_running"}
        
        try:
            # On Windows, we need to kill the process tree
            parent = psutil.Process(self.process.pid)
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
            self.process = None
            return {"status": "deactivated"}
        except Exception as e:
            # Fallback for simple kill
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
def toggle_kimi():
    if manager.is_running():
        return manager.deactivate()
    else:
        return manager.activate()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
