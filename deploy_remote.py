
import os
import sys
import paramiko
from scp import SCPClient
import tarfile
import time

# Configuration
HOST = "192.168.0.12"
USER = "root"
PASS = "435102"
REMOTE_PATH = "/opt/companyai"
ARCHIVE_NAME = "deploy_package.tar.gz"

def create_archive():
    print("📦 Proje dosyaları paketleniyor (tar.gz)...")
    exclude_dirs = {'node_modules', 'venv', '.git', '__pycache__', 'dist', 'coverage', '.idea', '.vscode', 'keys'}
    exclude_extensions = {'.pyc', '.pyo', '.pyd', '.db', '.sqlite', '.log'}
    
    with tarfile.open(ARCHIVE_NAME, "w:gz") as tar:
        for root, dirs, files in os.walk('.'):
            # Exclude directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                if any(file.endswith(ext) for ext in exclude_extensions):
                    continue
                if file == ARCHIVE_NAME or file.endswith('.zip'):
                    continue
                
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, '.').replace(os.sep, '/')
                tar.add(file_path, arcname=arcname)
    
    # Verify content
    with tarfile.open(ARCHIVE_NAME, "r:gz") as tar:
         names = tar.getnames()
         print(f"Files in tar: {len(names)}")
         # Check important files
         important_files = ['app/main.py', 'frontend/src/pages/Ask.tsx', 'frontend/src/components/FileUploadModal.tsx']
         for f in important_files:
             if f in names:
                 print(f"  ✓ {f}")
             else:
                 print(f"  ✗ {f} - MISSING!")
                 
    print(f"✅ Paketlendi: {ARCHIVE_NAME}")

def deploy():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"🔌 Sunucuya bağlanılıyor: {HOST}...")
        ssh.connect(HOST, username=USER, password=PASS)
        
        # Setup directories
        print("📂 Uzak dizinler hazırlanıyor...")
        commands_setup = [
            f"rm -rf {REMOTE_PATH}/*",
            f"mkdir -p {REMOTE_PATH}",
        ]
        for cmd in commands_setup:
            ssh.exec_command(cmd)
            time.sleep(0.5)
        
        # Upload
        print("🚀 Dosyalar yükleniyor...")
        remote_archive_path = f"{REMOTE_PATH}/{ARCHIVE_NAME}"
        
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(ARCHIVE_NAME, remote_path=remote_archive_path)
        
        print("✅ Dosyalar yüklendi, açılıyor...")
            
        # Extract tar
        extract_cmd = f"cd {REMOTE_PATH} && tar -xzf {ARCHIVE_NAME} && rm {ARCHIVE_NAME}"
        stdin, stdout, stderr = ssh.exec_command(extract_cmd)
        stdout.read()
        err = stderr.read().decode()
        if err:
            print(f"Extract error: {err}")
        
        # Verify extraction
        print("📁 Dosyalar kontrol ediliyor...")
        stdin, stdout, stderr = ssh.exec_command(f"ls -la {REMOTE_PATH}/")
        print(stdout.read().decode())
        
        # Install Node.js if not present
        print("📦 Node.js kontrol ediliyor...")
        stdin, stdout, stderr = ssh.exec_command("node --version || (curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt install -y nodejs)")
        print(stdout.read().decode())
        
        # Build frontend
        print("🔨 Frontend build ediliyor...")
        build_commands = [
            f"cd {REMOTE_PATH}/frontend && npm install",
            f"cd {REMOTE_PATH}/frontend && npm run build",
        ]
        
        for cmd in build_commands:
            print(f"Exec: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            output = stdout.read().decode()
            if output:
                print(output[-500:] if len(output) > 500 else output)
            err = stderr.read().decode()
            if err and 'warn' not in err.lower():
                print(f"STDERR: {err[:500]}")
        
        # Copy built files to nginx directory
        print("📋 Frontend dosyaları nginx'e kopyalanıyor...")
        nginx_commands = [
            "mkdir -p /var/www/html",
            f"rm -rf /var/www/html/*",
            f"cp -r {REMOTE_PATH}/frontend/dist/* /var/www/html/",
            "ls -la /var/www/html/"
        ]
        
        for cmd in nginx_commands:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            output = stdout.read().decode()
            if output:
                print(output)
        
        # Restart services
        print("🔄 Servisler yeniden başlatılıyor...")
        restart_commands = [
            "systemctl restart companyai-backend || echo 'Backend service not found'",
            "systemctl restart nginx || echo 'Nginx not found'",
            "systemctl status companyai-backend --no-pager -l || echo 'Status check failed'"
        ]
        
        for cmd in restart_commands:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            print(stdout.read().decode())
                
        print("\n✅ DEPLOYMENT TAMAMLANDI!")
        print(f"API: http://{HOST}:8000")
        print(f"Frontend: http://{HOST}")
        
    except Exception as e:
        print(f"\n❌ HATA: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        ssh.close()
        if os.path.exists(ARCHIVE_NAME):
            os.remove(ARCHIVE_NAME)

if __name__ == "__main__":
    create_archive()
    deploy()
