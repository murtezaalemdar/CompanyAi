"""PDF Görsel Yönetimi — Çıkarma, Saklama ve Sunma Altyapısı (v6.02.00)

PDF dokümanlarından görselleri çıkarıp diske kaydeder ve HTTP ile sunar.
engine.py ve documents.py tarafından kullanılır.
"""

import io
import json
import os
import re
import structlog
from pathlib import Path

logger = structlog.get_logger()

# ═══════════════════════════════════════════════════════════════
# DEPOLAMA DİZİNİ
# ═══════════════════════════════════════════════════════════════
PDF_IMAGES_DIR = Path(os.environ.get(
    "PDF_IMAGES_DIR",
    "/opt/companyai/data/pdf_images"
))


def _safe_dirname(source: str) -> str:
    """Dosya adından güvenli dizin adı üretir (özel karakterleri temizler)"""
    safe = re.sub(r'[^\w\s\-\.]', '_', source)
    return safe.strip()[:100]


# ═══════════════════════════════════════════════════════════════
# GÖRSEL ÇIKARMA
# ═══════════════════════════════════════════════════════════════

def extract_pdf_images(source: str, file_content: bytes) -> dict:
    """
    PDF'den görselleri çıkarır ve diske kaydeder.
    
    PyMuPDF (fitz) ile her sayfadan görsel çıkarma.
    Küçük görseller (<5KB, logolar/ikonlar) filtrelenir.
    Her görsel WebP formatında optimize edilir.
    
    Args:
        source: Kaynak dosya adı (ör. "OrhanKarakoçTekstilSunum.pdf")
        file_content: PDF dosyasının byte içeriği
    
    Returns:
        dict: {page_no: ["filename1.webp", ...], ...}
        Boş dict eğer görsel bulunamazsa
    """
    try:
        import fitz  # PyMuPDF
        from PIL import Image
    except ImportError:
        logger.warning("pdf_image_extract_no_fitz", source=source)
        return {}
    
    page_images = {}
    safe_dir = _safe_dirname(source)
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
                    
                    # Küçük görselleri filtrele (logolar, ikonlar, dekoratif öğeler)
                    if len(img_bytes) < 5000:  # <5KB
                        continue
                    
                    # PIL ile aç ve boyut kontrolü
                    pil_img = Image.open(io.BytesIO(img_bytes))
                    w, h = pil_img.size
                    
                    # Çok küçük görselleri atla (ikon/logo boyutu)
                    if w < 80 or h < 80:
                        continue
                    
                    # RGBA → RGB dönüşümü (WebP uyumluluğu)
                    if pil_img.mode in ("RGBA", "P", "LA"):
                        pil_img = pil_img.convert("RGB")
                    elif pil_img.mode != "RGB":
                        pil_img = pil_img.convert("RGB")
                    
                    # WebP olarak kaydet (iyi sıkıştırma + kalite)
                    filename = f"page_{page_num + 1}_img_{img_idx}.webp"
                    filepath = img_dir / filename
                    pil_img.save(str(filepath), "WEBP", quality=85)
                    
                    page_saved.append(filename)
                    total_saved += 1
                    
                except Exception as img_err:
                    logger.debug("pdf_image_extract_single_error",
                                source=source, page=page_num + 1,
                                img_idx=img_idx, error=str(img_err))
                    continue
            
            if page_saved:
                page_images[page_num + 1] = page_saved  # 1-indexed sayfa
        
        pdf_doc.close()
        
        # Manifest dosyası kaydet — sayfa→görsel eşlemesi
        if page_images:
            manifest = {
                "source": source,
                "total_images": total_saved,
                "pages": {str(k): v for k, v in page_images.items()},
            }
            manifest_path = img_dir / "manifest.json"
            with open(str(manifest_path), "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
            
            logger.info("pdf_images_extracted",
                        source=source,
                        total_images=total_saved,
                        pages_with_images=len(page_images))
        else:
            logger.info("pdf_no_images_found", source=source)
        
        return page_images
        
    except Exception as e:
        logger.error("pdf_image_extract_error", source=source, error=str(e))
        return {}


# ═══════════════════════════════════════════════════════════════
# GÖRSEL SORGULAMA
# ═══════════════════════════════════════════════════════════════

def get_pdf_images_for_pages(source: str, page_numbers: list) -> list:
    """
    Belirtilen sayfalardaki görsellerin bilgilerini döndürür.
    
    Args:
        source: PDF dosya adı
        page_numbers: Sayfa numaraları listesi [1, 2, 5, ...]
    
    Returns:
        list: [{"src": "/api/rag/images/...", "title": "Sayfa N", ...}, ...]
    """
    safe_dir = _safe_dirname(source)
    manifest_path = PDF_IMAGES_DIR / safe_dir / "manifest.json"
    
    if not manifest_path.exists():
        return []
    
    try:
        with open(str(manifest_path), "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception:
        return []
    
    pages_data = manifest.get("pages", {})
    images = []
    
    for page_no in page_numbers:
        page_key = str(page_no)
        if page_key not in pages_data:
            continue
        
        for img_filename in pages_data[page_key]:
            img_url = f"/api/rag/images/{safe_dir}/{img_filename}"
            images.append({
                "src": img_url,
                "thumbnail": img_url,
                "title": f"{source} — Sayfa {page_no}",
                "source": source,
                "link": img_url,
            })
    
    return images


def get_all_pdf_images(source: str) -> list:
    """
    Bir PDF'in tüm çıkarılmış görsellerini döndürür.
    
    Args:
        source: PDF dosya adı
    
    Returns:
        list: [{"src": ..., "thumbnail": ..., "title": ..., "source": ..., "link": ...}, ...]
    """
    safe_dir = _safe_dirname(source)
    manifest_path = PDF_IMAGES_DIR / safe_dir / "manifest.json"
    
    if not manifest_path.exists():
        return []
    
    try:
        with open(str(manifest_path), "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception:
        return []
    
    pages_data = manifest.get("pages", {})
    images = []
    
    for page_key in sorted(pages_data.keys(), key=lambda x: int(x)):
        for img_filename in pages_data[page_key]:
            img_url = f"/api/rag/images/{safe_dir}/{img_filename}"
            images.append({
                "src": img_url,
                "thumbnail": img_url,
                "title": f"{source} — Sayfa {page_key}",
                "source": source,
                "link": img_url,
            })
    
    return images
