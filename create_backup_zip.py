import zipfile
import os
from datetime import datetime

backup_name = f"CompanyAi_Backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
exclude_dirs = {
    'node_modules', 'venv', '.git', '__pycache__', 'dist', 
    'coverage', '.idea', '.vscode'
}

print(f"📦 Creating full backup: {backup_name}...")

with zipfile.ZipFile(backup_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk('.'):
        # Filter excluded dirs
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            file_path = os.path.join(root, file)
            # Skip zip itself
            if file == backup_name or file.endswith('.zip') or file.endswith('.tar.gz'):
                continue
                
            arcname = os.path.relpath(file_path, '.')
            zipf.write(file_path, arcname)

print("✅ Backup completed successfully!")
