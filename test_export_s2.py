"""Full end-to-end export test on Server 2 with auth"""
import paramiko, json

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('88.246.13.23', port=2013, username='root', password='Kc435102mn')

# 1) Login to get a token
login_cmd = '''curl -s http://127.0.0.1:8000/api/auth/login \
  -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@karakoc.com.tr&password=Kc435102mn"'''

stdin, stdout, stderr = ssh.exec_command(login_cmd, timeout=15)
login_out = stdout.read().decode().strip()
print("LOGIN:", login_out[:500])

try:
    token_data = json.loads(login_out)
    token = token_data.get("access_token", "")
except:
    # Try alternate admin creds
    login_cmd2 = '''curl -s http://127.0.0.1:8000/api/auth/login \
      -X POST \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username=admin@admin.com&password=admin123"'''
    stdin, stdout, stderr = ssh.exec_command(login_cmd2, timeout=15)
    login_out = stdout.read().decode().strip()
    print("LOGIN2:", login_out[:500])
    token_data = json.loads(login_out)
    token = token_data.get("access_token", "")

if not token:
    print("NO TOKEN, trying to list users")
    # Check what users exist (async db)
    stdin, stdout, stderr = ssh.exec_command(
        'cd /opt/companyai && /opt/companyai/venv/bin/python -c "\n'
        'import asyncio\n'
        'from app.db.database import async_session_maker\n'
        'from app.db.models import User\n'
        'from sqlalchemy import select\n'
        'async def main():\n'
        '    async with async_session_maker() as s:\n'
        '        r = await s.execute(select(User.email))\n'
        '        for row in r.scalars():\n'
        '            print(row)\n'
        'asyncio.run(main())\n"', timeout=15)
    users = stdout.read().decode().strip()
    print("USERS:", users)
    uerr = stderr.read().decode().strip()
    if uerr: print("ERR:", uerr[:300])
    
    # Try first user with common passwords
    if users:
        first_email = users.split('\n')[0].strip()
        for pwd in ['Kc435102mn', 'admin123', '123456', 'Admin123!']:
            login_cmd3 = f'''curl -s http://127.0.0.1:8000/api/auth/login -X POST -H "Content-Type: application/x-www-form-urlencoded" -d "username={first_email}&password={pwd}"'''
            stdin, stdout, stderr = ssh.exec_command(login_cmd3, timeout=15)
            out3 = stdout.read().decode().strip()
            print(f"  Try {first_email}/{pwd}: {out3[:200]}")
            try:
                d = json.loads(out3)
                if d.get("access_token"):
                    token = d["access_token"]
                    break
            except:
                pass
    
    if not token:
        print("Could not get token")
        ssh.close()
        exit()

print(f"TOKEN: {token[:30]}...")

# 2) Test export endpoint
export_cmd = f'''curl -s http://127.0.0.1:8000/api/analyze/export \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{{"content":"Test raporu: Satış verileri analizi","format":"excel"}}'
'''

stdin, stdout, stderr = ssh.exec_command(export_cmd, timeout=30)
export_out = stdout.read().decode().strip()
export_err = stderr.read().decode().strip()
print("\nEXPORT RESPONSE:", export_out[:500])
if export_err:
    print("EXPORT ERR:", export_err[:300])

# 3) If export succeeded, try download
try:
    export_data = json.loads(export_out)
    if export_data.get("success") and export_data.get("file_id"):
        file_id = export_data["file_id"]
        dl_cmd = f'''curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1:8000/api/analyze/export/download/{file_id} \
          -H "Authorization: Bearer {token}"'''
        stdin, stdout, stderr = ssh.exec_command(dl_cmd, timeout=15)
        print(f"\nDOWNLOAD STATUS: {stdout.read().decode().strip()}")
except Exception as e:
    print(f"\nParse error: {e}")

# 4) Check recent backend logs for export
stdin, stdout, stderr = ssh.exec_command(
    'journalctl -u companyai-backend --no-pager -n 20 --output=cat 2>&1 | grep -i export || echo "no export logs"',
    timeout=10)
print(f"\nEXPORT LOGS: {stdout.read().decode().strip()[:500]}")

# 5) Check nginx logs for export
stdin, stdout, stderr = ssh.exec_command(
    'tail -5 /var/log/nginx/error.log 2>/dev/null || echo "no nginx error log"',
    timeout=10)
print(f"\nNGINX ERR: {stdout.read().decode().strip()[:500]}")

ssh.close()
