import subprocess
import json
import sys

# Get log lines
cmd = ["journalctl", "-u", "companyai-backend", "--since", "5 minutes ago", "--no-pager", "-o", "cat"]
result = subprocess.run(cmd, capture_output=True, text=True)

lines = result.stdout.splitlines()

print(f"Total lines: {len(lines)}")
for line in lines:
    try:
        data = json.loads(line)
        # Hataları ve önemli eventleri bas
        if data.get("level") == "error" or data.get("event") in ["processing_question", "ollama_not_available", "ollama_health_check_failed"]:
             print(f"LEVEL: {data.get('level')} | EVENT: {data.get('event')}")
             if "error" in data:
                 print(f"ERROR: {data.get('error')}")
             print("-" * 50)
    except json.JSONDecodeError:
        pass # Ignore non-json lines
