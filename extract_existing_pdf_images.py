#!/usr/bin/env python3
"""
v6.02.00 Migration Script — Mevcut PDF'lerden görsel çıkarma

Sunucuda /opt/companyai/ altında çalıştırılmalıdır.
ChromaDB'deki PDF kaynaklarını tarar ve görselleri çıkarır.

Kullanım:
    cd /opt/companyai
    python3 extract_existing_pdf_images.py

Not: Bu script sadece bir kez çalıştırılır. Sonraki yüklemeler
     otomatik olarak görsel çıkaracaktır.
"""

import os
import sys
import json
import io
import re
from pathlib import Path

# PDF görselleri kayıt dizini
PDF_IMAGES_DIR = Path(os.environ.get(
    "PDF_IMAGES_DIR",
    "/opt/companyai/data/pdf_images"
))

def safe_dirname(source: str) -> str:
    """Dosya adından güvenli dizin adı üretir"""
    safe = re.sub(r'[^\w\s\-\.]', '_', source)
    return safe.strip()[:100]


def extract_images_from_pdf(source: str, pdf_path: str) -> dict:
    """PDF dosyasından görselleri çıkarır ve diske kaydeder."""
    try:
        import fitz  # PyMuPDF
        from PIL import Image
    except ImportError:
        print(f"  HATA: PyMuPDF veya PIL yüklü değil!")
        return {}
    
    with open(pdf_path, 'rb') as f:
        file_content = f.read()
    
    page_images = {}
    safe_dir = safe_dirname(source)
    img_dir = PDF_IMAGES_DIR / safe_dir
    img_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        pdf_doc = fitz.open(stream=file_content, filetype="pdf")
        total_saved = 0
        
        for page_num in range(len(pdf_doc)):
            page = pdf_doc[page_num]
            image_list = page.get_images(full=True)
            
            if not image_list:
                continue
            
            page_saved = []
            for img_idx, img_info in enumerate(image_list):
                xref = img_info[0]
                
                try:
                    base_image = pdf_doc.extract_image(xref)
                    if not base_image:
                        continue
                    
                    img_bytes = base_image["image"]
                    
                    # Küçük görselleri filtrele
                    if len(img_bytes) < 5000:
                        continue
                    
                    pil_img = Image.open(io.BytesIO(img_bytes))
                    w, h = pil_img.size
                    
                    if w < 80 or h < 80:
                        continue
                    
                    if pil_img.mode in ("RGBA", "P", "LA"):
                        pil_img = pil_img.convert("RGB")
                    elif pil_img.mode != "RGB":
                        pil_img = pil_img.convert("RGB")
                    
                    filename = f"page_{page_num + 1}_img_{img_idx}.webp"
                    filepath = img_dir / filename
                    pil_img.save(str(filepath), "WEBP", quality=85)
                    
                    page_saved.append(filename)
                    total_saved += 1
                    
                except Exception as e:
                    print(f"  Sayfa {page_num+1}, görsel {img_idx}: HATA - {e}")
                    continue
            
            if page_saved:
                page_images[page_num + 1] = page_saved
        
        pdf_doc.close()
        
        # Manifest kaydet
        if page_images:
            manifest = {
                "source": source,
                "total_images": total_saved,
                "pages": {str(k): v for k, v in page_images.items()},
            }
            manifest_path = img_dir / "manifest.json"
            with open(str(manifest_path), "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
        
        return page_images
        
    except Exception as e:
        print(f"  HATA: {e}")
        return {}


def find_pdf_files():
    """
    Sunucudaki bilinen PDF dosyalarını bul.
    Birkaç olası konum taranır.
    """
    pdf_files = {}
    
    # 1) /opt/companyai/ altındaki PDF dosyaları
    search_dirs = [
        "/opt/companyai/",
        "/opt/companyai/uploads/",
        "/opt/companyai/data/",
        "/tmp/",
        os.path.expanduser("~"),
    ]
    
    for search_dir in search_dirs:
        if not os.path.exists(search_dir):
            continue
        for root, dirs, files in os.walk(search_dir):
            # Çok derin dizinlere girme
            depth = root.replace(search_dir, '').count(os.sep)
            if depth > 3:
                continue
            for f in files:
                if f.lower().endswith('.pdf'):
                    full_path = os.path.join(root, f)
                    if f not in pdf_files:
                        pdf_files[f] = full_path
    
    return pdf_files


def get_chromadb_pdf_sources():
    """ChromaDB'den PDF kaynaklarını listele"""
    try:
        sys.path.insert(0, '/opt/companyai')
        import chromadb
        
        chroma_dir = os.environ.get("CHROMA_PERSIST_DIR", "/opt/companyai/data/chromadb")
        client = chromadb.PersistentClient(path=chroma_dir)
        
        pdf_sources = set()
        
        for coll_name in ["company_documents", "learned_knowledge"]:
            try:
                coll = client.get_collection(coll_name)
                results = coll.get(include=["metadatas"])
                if results and results.get("metadatas"):
                    for meta in results["metadatas"]:
                        source = meta.get("source", "")
                        if source.lower().endswith(".pdf"):
                            pdf_sources.add(source)
            except Exception as e:
                print(f"  Koleksiyon {coll_name}: {e}")
        
        return pdf_sources
        
    except Exception as e:
        print(f"ChromaDB bağlantı hatası: {e}")
        return set()


def main():
    print("=" * 60)
    print("v6.02.00 — PDF Görsel Çıkarma Migration Script")
    print("=" * 60)
    
    # 1) ChromaDB'deki PDF kaynaklarını bul
    print("\n[1/3] ChromaDB taranıyor...")
    pdf_sources = get_chromadb_pdf_sources()
    print(f"  Bulunan PDF kaynakları: {len(pdf_sources)}")
    for src in sorted(pdf_sources):
        print(f"    - {src}")
    
    # 2) Fiziksel PDF dosyalarını bul
    print("\n[2/3] Diskteki PDF dosyaları taranıyor...")
    pdf_files = find_pdf_files()
    print(f"  Bulunan PDF dosyaları: {len(pdf_files)}")
    
    # 3) Eşleştir ve görselleri çıkar
    print(f"\n[3/3] Görseller çıkarılıyor (hedef: {PDF_IMAGES_DIR})...")
    PDF_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    
    processed = 0
    total_images = 0
    
    for source in sorted(pdf_sources):
        safe_dir = safe_dirname(source)
        manifest_path = PDF_IMAGES_DIR / safe_dir / "manifest.json"
        
        # Zaten işlenmiş mi?
        if manifest_path.exists():
            print(f"\n  [{source}] → zaten işlenmiş, atlanıyor")
            continue
        
        # Fiziksel dosyayı bul
        pdf_path = pdf_files.get(source)
        if not pdf_path:
            # Dosya adı eşleşmesi dene
            for fname, fpath in pdf_files.items():
                if fname.lower() == source.lower():
                    pdf_path = fpath
                    break
        
        if not pdf_path:
            print(f"\n  [{source}] → dsyada bulunamadı, atlanıyor")
            continue
        
        print(f"\n  [{source}] → {pdf_path}")
        page_images = extract_images_from_pdf(source, pdf_path)
        
        img_count = sum(len(v) for v in page_images.values())
        total_images += img_count
        processed += 1
        
        if page_images:
            print(f"    ✓ {img_count} görsel çıkarıldı ({len(page_images)} sayfadan)")
        else:
            print(f"    - Görsel bulunamadı")
    
    print(f"\n{'=' * 60}")
    print(f"Tamamlandı: {processed} PDF işlendi, toplam {total_images} görsel çıkarıldı")
    print(f"Görseller: {PDF_IMAGES_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
