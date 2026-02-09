
import paramiko
import time

# Configuration
HOST = "192.168.0.12"
USER = "root"
PASS = "435102"
REMOTE_PATH = "/opt/companyai"

def diagnose():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"🔌 Sunucuya bağlanılıyor: {HOST}...")
        ssh.connect(HOST, username=USER, password=PASS)
        
        commands = [
            "echo '--- VERIFY OLLAMA MODELS ---'",
            "ollama list",
            "echo '\n--- AI RESPONSE TEST (FROM API) ---'",
            "docker exec companyai-api python -c 'import urllib.request, json; data = json.dumps({\"question\": \"merhaba\"}).encode(); req = urllib.request.Request(\"http://localhost:8000/api/ask\", data=data, headers={\"Content-Type\": \"application/json\"}); print(urllib.request.urlopen(req, timeout=30).read().decode())'"
        ]
        
        for cmd in commands:
            print(f"\n> {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            print(stdout.read().decode())
            err = stderr.read().decode()
            if err and "ping" not in cmd: # Ignore ping errors in stderr if host not found
                print(f"STDERR: {err}")
                
    except Exception as e:
        print(f"\n❌ BAĞLANTI HATASI: {str(e)}")
    finally:
        ssh.close()

if __name__ == "__main__":
    diagnose()
