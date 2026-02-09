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
        # Filter relevant events
        if data.get("event") in ["ollama_health_check_failed", "processing_question", "question_processed", "ollama_not_available"]:
             print(f"EVENT: {data.get('event')}")
             print(f"DATA: {json.dumps(data, indent=2)}")
             print("-" * 50)
    except json.JSONDecodeError:
        pass # Ignore non-json lines
