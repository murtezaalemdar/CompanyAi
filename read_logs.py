import subprocess

cmd = ["journalctl", "-u", "companyai-backend", "--since", "2 minutes ago", "--no-pager"]
result = subprocess.run(cmd, capture_output=True, text=True)

print(result.stdout)
