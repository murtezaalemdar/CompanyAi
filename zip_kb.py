
import zipfile
import os

zip_name = "textile_kb.zip"
print(f"📦 Zipping knowledge base: {zip_name}...")

with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk('textile_knowledge_base'):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, '.')
            zipf.write(file_path, arcname)

print("✅ Zipped successfully!")
