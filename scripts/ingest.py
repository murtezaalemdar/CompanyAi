
import os
import sys
import glob
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag.vector_store import add_document, get_stats, clear_all_documents

DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "docs")

def ingest_all():
    print(f"Scanning documents in: {DOCS_DIR}")
    
    if not os.path.exists(DOCS_DIR):
        os.makedirs(DOCS_DIR)
        print("Created docs directory. Please put files there.")
        return

    # Supported extensions
    extensions = ["*.txt", "*.pdf", "*.docx", "*.md"]
    files = []
    for ext in extensions:
        files.extend(glob.glob(os.path.join(DOCS_DIR, ext)))
        
    print(f"Found {len(files)} documents.")
    
    for file_path in files:
        filename = os.path.basename(file_path)
        print(f"Processing: {filename}...", end=" ", flush=True)
        
        try:
            content = ""
            doc_type = "text"
            
            if file_path.endswith(".pdf"):
                import PyPDF2
                doc_type = "pdf"
                with open(file_path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        content += page.extract_text() + "\n"
                        
            elif file_path.endswith(".docx"):
                import docx
                doc_type = "docx"
                doc = docx.Document(file_path)
                for para in doc.paragraphs:
                    content += para.text + "\n"
                    
            else: # Text/MD
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            
            if content.strip():
                success = add_document(content, source=filename, doc_type=doc_type)
                if success:
                    print("OK")
                else:
                    print("FAILED (Vector Store Error)")
            else:
                print("SKIPPED (Empty content)")
                
        except Exception as e:
            print(f"ERROR: {e}")

    stats = get_stats()
    print("\n--- RAG Stats ---")
    print(stats)

if __name__ == "__main__":
    confirm = input("Clear existing database before ingestion? (y/n): ")
    if confirm.lower() == 'y':
        clear_all_documents()
        print("Database cleared.")
        
    ingest_all()
