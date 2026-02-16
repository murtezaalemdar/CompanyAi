#!/usr/bin/env python3
"""
OrhanKarakoçTekstilSunum.pdf yeniden işleme scripti.

Görüntü tabanlı PDF'i easyocr + PyMuPDF ile OCR'dan geçirir,
eski boş kaydı siler ve ChromaDB'ye gerçek içerikle kaydeder.

Kullanım (sunucuda):
  cd /opt/companyai && python reprocess_pdf_ocr.py
"""

import os
import sys
import glob
import time

# ── ChromaDB bağlantısı ──
CHROMA_PERSIST_DIR = os.environ.get("CHROMA_PERSIST_DIR", "/opt/companyai/data/chromadb")
COLLECTION_NAME = "company_documents"
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

# PDF dosya adı
PDF_FILENAME = "OrhanKarakoçTekstilSunum.pdf"
# Sunucudaki olası yollar
PDF_SEARCH_PATHS = [
    "/opt/companyai/uploads/",
    "/opt/companyai/data/uploads/",
    "/opt/companyai/",
    "/tmp/",
    "/root/",
]


def find_pdf():
    """PDF dosyasını sunucuda bul."""
    # Önce tam yollarla dene
    for base_path in PDF_SEARCH_PATHS:
        full_path = os.path.join(base_path, PDF_FILENAME)
        if os.path.exists(full_path):
            return full_path
    
    # Glob ile recursive ara
    for pattern in ["/opt/companyai/**/" + PDF_FILENAME, "/tmp/**/" + PDF_FILENAME]:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            return matches[0]
    
    # Benzer isimle ara
    for base_path in PDF_SEARCH_PATHS:
        if os.path.isdir(base_path):
            for f in os.listdir(base_path):
                if "karakoc" in f.lower() and f.endswith(".pdf"):
                    return os.path.join(base_path, f)
                if "sunum" in f.lower() and f.endswith(".pdf"):
                    return os.path.join(base_path, f)
    
    return None


def chunk_text(text, chunk_size=2000, overlap=300):
    """Metni parçalara böl."""
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        
        # Paragraf veya cümle sınırında kes
        if end < len(text):
            for sep in ['\n\n', '\n', '. ', ', ', ' ']:
                last_sep = text[start:end].rfind(sep)
                if last_sep > chunk_size * 0.5:
                    end = start + last_sep + len(sep)
                    break
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        start = end - overlap
        if start >= len(text):
            break
    
    return chunks


def main():
    print("=" * 60)
    print("PDF OCR Yeniden İşleme Scripti")
    print("=" * 60)
    
    # 1) Bağımlılıkları kontrol et
    print("\n[1/6] Bağımlılıklar kontrol ediliyor...")
    try:
        import chromadb
        print(f"  ✓ chromadb {chromadb.__version__}")
    except ImportError:
        print("  ✗ chromadb yüklü değil!")
        sys.exit(1)
    
    try:
        from sentence_transformers import SentenceTransformer
        print("  ✓ sentence-transformers")
    except ImportError:
        print("  ✗ sentence-transformers yüklü değil!")
        sys.exit(1)
    
    try:
        import easyocr
        print(f"  ✓ easyocr {easyocr.__version__}")
    except ImportError:
        print("  ✗ easyocr yüklü değil!")
        sys.exit(1)
    
    try:
        import fitz  # PyMuPDF
        print(f"  ✓ PyMuPDF {fitz.version}")
    except ImportError:
        print("  ✗ PyMuPDF yüklü değil!")
        sys.exit(1)
    
    # 2) PDF dosyasını bul
    print("\n[2/6] PDF dosyası aranıyor...")
    pdf_path = find_pdf()
    if not pdf_path:
        print(f"  ✗ '{PDF_FILENAME}' bulunamadı!")
        print("  Aranan yollar:", PDF_SEARCH_PATHS)
        print("\n  Manuel yol belirtmek için:")
        print(f"  PDF_PATH=/path/to/{PDF_FILENAME} python reprocess_pdf_ocr.py")
        
        # Env'den yol al
        pdf_path = os.environ.get("PDF_PATH")
        if pdf_path and os.path.exists(pdf_path):
            print(f"  → PDF_PATH ortam değişkeninden: {pdf_path}")
        else:
            sys.exit(1)
    
    file_size_mb = os.path.getsize(pdf_path) / 1024 / 1024
    print(f"  ✓ Bulundu: {pdf_path}")
    print(f"    Boyut: {file_size_mb:.1f} MB")
    
    # 3) ChromaDB'den eski kaydı sil
    print("\n[3/6] ChromaDB'den eski kayıt siliniyor...")
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    
    # Eski kayıtları bul
    try:
        existing = collection.get(
            where={"source": PDF_FILENAME},
            include=["metadatas", "documents"]
        )
        if existing and existing['ids']:
            old_count = len(existing['ids'])
            old_content_preview = ""
            if existing['documents']:
                old_content_preview = existing['documents'][0][:100]
            print(f"  Eski kayıt sayısı: {old_count}")
            print(f"  Eski içerik önizleme: {old_content_preview}...")
            
            collection.delete(ids=existing['ids'])
            print(f"  ✓ {old_count} eski kayıt silindi")
        else:
            print("  ℹ Eski kayıt bulunamadı (yeni ekleme yapılacak)")
    except Exception as e:
        print(f"  ⚠ Eski kayıt silme hatası: {e}")
        # source ile bulamadıysa, ID paterni ile dene
        try:
            # OrhanKarakoçTekstilSunum.pdf_0, _1, vs.
            old_ids = [f"{PDF_FILENAME}_{i}" for i in range(100)]
            collection.delete(ids=old_ids)
            print("  ✓ ID paterni ile silindi")
        except Exception:
            print("  ℹ Devam ediliyor...")
    
    # 4) PDF'i OCR ile işle
    print("\n[4/6] PDF OCR ile işleniyor (bu birkaç dakika sürebilir)...")
    
    import fitz
    pdf_doc = fitz.open(pdf_path)
    page_count = len(pdf_doc)
    print(f"  Sayfa sayısı: {page_count}")
    
    # EasyOCR reader (CPU modunda — GPU LLM için ayrılmış)
    print("  EasyOCR yükleniyor (CPU modu)...")
    reader = easyocr.Reader(['tr', 'en'], gpu=False)
    print("  ✓ EasyOCR hazır")
    
    all_pages_text = []
    total_chars = 0
    
    for page_num in range(page_count):
        page = pdf_doc[page_num]
        
        # Sayfayı 200 DPI resme çevir
        mat = fitz.Matrix(200/72, 200/72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        
        # OCR
        start_t = time.time()
        try:
            results = reader.readtext(img_bytes, detail=0, paragraph=True)
            page_text = "\n".join(results)
            elapsed = time.time() - start_t
            
            if page_text.strip():
                all_pages_text.append(f"--- Sayfa {page_num + 1} ---\n{page_text}")
                total_chars += len(page_text)
                print(f"  Sayfa {page_num + 1}/{page_count}: {len(page_text)} karakter ({elapsed:.1f}s)")
            else:
                print(f"  Sayfa {page_num + 1}/{page_count}: boş ({elapsed:.1f}s)")
        except Exception as e:
            print(f"  Sayfa {page_num + 1}/{page_count}: HATA - {e}")
    
    pdf_doc.close()
    
    if not all_pages_text:
        print("  ✗ Hiçbir sayfadan metin çıkarılamadı!")
        sys.exit(1)
    
    full_content = "\n\n".join(all_pages_text)
    print(f"\n  ✓ Toplam: {total_chars} karakter, {len(all_pages_text)} sayfa içerik var")
    
    # İçerik önizleme
    preview = full_content[:500].replace('\n', ' ')
    print(f"  Önizleme: {preview}...")
    
    # 5) Chunk'lara böl ve ChromaDB'ye kaydet
    print("\n[5/6] ChromaDB'ye kaydediliyor...")
    
    chunks = chunk_text(full_content, chunk_size=2000, overlap=300)
    print(f"  Chunk sayısı: {len(chunks)}")
    
    # Embedding modeli yükle
    print("  Embedding modeli yükleniyor...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    print("  ✓ Embedding modeli hazır")
    
    from datetime import datetime
    created_at = datetime.utcnow().isoformat()
    
    for i, chunk in enumerate(chunks):
        doc_id = f"{PDF_FILENAME}_{i}"
        embedding = model.encode(chunk).tolist()
        
        metadata = {
            "source": PDF_FILENAME,
            "type": "pdf",
            "chunk_index": i,
            "total_chunks": len(chunks),
            "created_at": created_at,
            "department": "Genel",
            "ocr_processed": "true",
            "page_count": str(page_count),
        }
        
        collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[chunk],
            metadatas=[metadata]
        )
        print(f"  Chunk {i+1}/{len(chunks)} kaydedildi ({len(chunk)} karakter)")
    
    # 6) Doğrulama
    print("\n[6/6] Doğrulama...")
    verify = collection.get(
        where={"source": PDF_FILENAME},
        include=["metadatas", "documents"]
    )
    if verify and verify['ids']:
        print(f"  ✓ ChromaDB'de {len(verify['ids'])} chunk kayıtlı")
        print(f"  ✓ İlk chunk önizleme: {verify['documents'][0][:200]}...")
    else:
        print("  ✗ Doğrulama başarısız — kayıt bulunamadı!")
    
    print("\n" + "=" * 60)
    print("✓ PDF başarıyla OCR ile işlendi ve ChromaDB'ye kaydedildi!")
    print(f"  Dosya: {PDF_FILENAME}")
    print(f"  Sayfalar: {page_count}")
    print(f"  Toplam karakter: {total_chars}")
    print(f"  Chunk sayısı: {len(chunks)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
