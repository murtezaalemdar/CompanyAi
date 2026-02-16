"""Sync sonrası her iki sunucudaki ChromaDB kayıt sayılarını karşılaştır"""
import paramiko

def check_server(name, host, port, python_cmd="python3", **kwargs):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, port=port, timeout=10, **kwargs)

    cmd = f"""{python_cmd} -c "
import chromadb
c = chromadb.PersistentClient(path='/opt/companyai/data/chromadb')
cols = c.list_collections()
total = 0
for col in cols:
    data = col.get(include=[])
    count = len(data['ids']) if data and data.get('ids') else 0
    total += count
    print(f'  {{col.name}}: {{count}}')
print(f'  TOPLAM: {{total}}')
" 2>&1"""

    _, stdout, _ = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode().strip()
    print(f"\n{name} ({host}):")
    print(out)
    ssh.close()

check_server("Server 2", "88.246.13.23", 2013, "/opt/companyai/venv/bin/python", username="root", password="Kc435102mn")
check_server("Server 1", "192.168.0.12", 22, "python3", username="root", key_filename="keys/companyai_key")
