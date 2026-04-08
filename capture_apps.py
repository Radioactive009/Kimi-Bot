import subprocess
import json

def get_apps():
    cmd = ["powershell", "-Command", "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except Exception as e:
        return str(e)

content = get_apps()
with open("apps_snapshot.json", "w") as f:
    f.write(content)

print(f"Captured {len(content)} bytes")
