"""Ollama model indirme takibi — Server 2"""
import paramiko
import time
import sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('88.246.13.23', port=2013, username='root', password='Kc435102mn',
            timeout=30, allow_agent=False, look_for_keys=False)

print("=" * 60)
print("  Ollama Model İndirme Takibi — qwen2.5:72b")
print("=" * 60)

while True:
    # Log son satır
    si, so, se = ssh.exec_command('tail -1 /tmp/ollama_pull.log 2>/dev/null')
    so.channel.recv_exit_status()
    log = so.read().decode().strip()

    # Model listesi
    si, so, se = ssh.exec_command('ollama list 2>/dev/null | grep -v NAME')
    so.channel.recv_exit_status()
    models = so.read().decode().strip()

    # Process kontrol
    si, so, se = ssh.exec_command('ps aux | grep "ollama pull" | grep -v grep | wc -l')
    so.channel.recv_exit_status()
    running = so.read().decode().strip()

    ts = time.strftime("%H:%M:%S")

    if models and "qwen2.5:72b" in models:
        print(f"\n  [{ts}] ✅ MODEL İNDİRME TAMAMLANDI!")
        print(f"  {models}")
        break
    elif running == "0" and not models:
        print(f"\n  [{ts}] ⚠️ İndirme process bulunamadı. Log: {log}")
        # Tekrar başlat?
        si, so, se = ssh.exec_command('tail -5 /tmp/ollama_pull.log 2>/dev/null')
        so.channel.recv_exit_status()
        print(f"  Son loglar: {so.read().decode().strip()}")
        break
    else:
        # İlerleme göster
        sys.stdout.write(f"\r  [{ts}] {log[:100]}")
        sys.stdout.flush()

    time.sleep(10)

ssh.close()
