"""Server'lar arası ağ bağlantısı testi"""
import paramiko

# 1) Server 1'e bağlan
ssh1 = paramiko.SSHClient()
ssh1.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh1.connect('192.168.0.12', port=22, username='root', key_filename='keys/companyai_key', timeout=10)
print("Server 1 baglandi")

# 2) Server 1'den Server 2'ye erişilebilirlik
print("\n--- Server 1 -> Server 2 (88.246.13.23:2013) ---")
test_cmd = 'python3 -c "import socket; s=socket.socket(); s.settimeout(5); s.connect((\'88.246.13.23\', 2013)); print(\'REACHABLE\'); s.close()" 2>&1 || echo UNREACHABLE'
_, stdout, stderr = ssh1.exec_command(test_cmd, timeout=15)
print(f"  Sonuc: {stdout.read().decode().strip()}")
err = stderr.read().decode().strip()
if err:
    print(f"  Stderr: {err}")

# Ping test
_, stdout, _ = ssh1.exec_command("ping -c 2 -W 3 88.246.13.23 2>&1 | tail -3", timeout=15)
print(f"  Ping: {stdout.read().decode().strip()}")

# 3) Server 2'ye bağlan
ssh2 = paramiko.SSHClient()
ssh2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh2.connect('88.246.13.23', port=2013, username='root', password='Kc435102mn', timeout=10)
print("\nServer 2 baglandi")

# 4) Server 2'den Server 1'e erişilebilirlik
print("\n--- Server 2 -> Server 1 (192.168.0.12:22) ---")
test_cmd2 = 'python3 -c "import socket; s=socket.socket(); s.settimeout(5); s.connect((\'192.168.0.12\', 22)); print(\'REACHABLE\'); s.close()" 2>&1 || echo UNREACHABLE'
_, stdout, stderr = ssh2.exec_command(test_cmd2, timeout=15)
print(f"  Sonuc: {stdout.read().decode().strip()}")
err2 = stderr.read().decode().strip()
if err2:
    print(f"  Stderr: {err2}")

# Ping test
_, stdout, _ = ssh2.exec_command("ping -c 2 -W 3 192.168.0.12 2>&1 | tail -3", timeout=15)
print(f"  Ping: {stdout.read().decode().strip()}")

# Route bilgisi
_, stdout, _ = ssh2.exec_command("ip route | head -5", timeout=10)
print(f"  Route: {stdout.read().decode().strip()}")

ssh1.close()
ssh2.close()
print("\nTest tamamlandi")
