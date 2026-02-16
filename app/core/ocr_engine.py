"""OCR Motor Entegrasyonu (v4.4.0)

Görsellerden metin çıkarma — EasyOCR tabanlı.
Desteklenen özellikler:
- Çok dilli OCR (Türkçe + İngilizce)
- PDF'ten metin çıkarma (resim tabanlı PDF)
- Etiket / fatura / tablo okuma
- Güven skoru ile sonuç döndürme
"""

import io
import re
import structlog
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = structlog.get_logger()

# EasyOCR — GPU destekli, çok dilli
try:
    import easyocr
    _reader = None
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    _reader = None
    logger.warning("easyocr_not_installed", message="OCR özellikleri devre dışı. Kurulum: pip install easyocr")

# Pillow
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def get_ocr_reader():
    """EasyOCR reader'ı lazy-load et (singleton, GPU otomatik)."""
    global _reader
    if not EASYOCR_AVAILABLE:
        return None
    if _reader is None:
        try:
            # GPU varsa otomatik kullanır, yoksa CPU
            _reader = easyocr.Reader(
                ['tr', 'en'],
                gpu=True,
                verbose=False,
            )
            logger.info("easyocr_initialized", languages=["tr", "en"], gpu=True)
        except Exception as e:
            try:
                _reader = easyocr.Reader(['tr', 'en'], gpu=False, verbose=False)
                logger.info("easyocr_initialized", languages=["tr", "en"], gpu=False)
            except Exception as e2:
                logger.error("easyocr_init_failed", error=str(e2))
                return None
    return _reader


def extract_text_from_image(
    image_path: str,
    detail: bool = True,
    paragraph: bool = True,
) -> Dict[str, Any]:
    """Görseldan metin çıkar.
    
    Args:
        image_path: Görsel dosya yolu
        detail: Detaylı sonuç (konum + güven) döndür
        paragraph: Paragraf modunda birleştir
    
    Returns:
        {
            "text": str,              # Çıkarılan tam metin
            "blocks": [...],          # Detaylı bloklar (konum, güven)
            "confidence": float,      # Ortalama güven (0-1)
            "word_count": int,        # Kelime sayısı
            "language_detected": str, # Algılanan dil
            "has_table": bool,        # Tablo yapısı var mı
        }
    """
    reader = get_ocr_reader()
    if not reader:
        return {"text": "", "blocks": [], "confidence": 0, "word_count": 0,
                "error": "OCR motoru kullanılamıyor. EasyOCR yüklü mü?"}
    
    try:
        # EasyOCR ile tanıma
        results = reader.readtext(
            image_path,
            detail=1,  # Her zaman detay al
            paragraph=paragraph,
        )
        
        if not results:
            return {"text": "", "blocks": [], "confidence": 0, "word_count": 0}
        
        blocks = []
        texts = []
        confidences = []
        
        for item in results:
            if len(item) == 3:
                bbox, text, conf = item
            elif len(item) == 2:
                text, conf = item
                bbox = None
            else:
                continue
            
            texts.append(text)
            confidences.append(conf)
            
            if detail:
                block = {
                    "text": text,
                    "confidence": round(float(conf), 3),
                }
                if bbox:
                    block["bbox"] = bbox
                blocks.append(block)
        
        full_text = "\n".join(texts)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # Tablo tespiti (basit heuristik)
        has_table = _detect_table_structure(full_text)
        
        return {
            "text": full_text,
            "blocks": blocks if detail else [],
            "confidence": round(avg_confidence, 3),
            "word_count": len(full_text.split()),
            "has_table": has_table,
        }
        
    except Exception as e:
        logger.error("ocr_extract_failed", error=str(e), path=image_path)
        return {"text": "", "blocks": [], "confidence": 0, "word_count": 0, "error": str(e)}


def extract_text_from_image_bytes(
    image_bytes: bytes,
    detail: bool = True,
) -> Dict[str, Any]:
    """Byte dizisinden OCR yap (upload edilen dosyalar için).
    
    Args:
        image_bytes: Görsel dosyasının byte içeriği
        detail: Detaylı sonuç döndür
    
    Returns:
        OCR sonuç dict'i
    """
    reader = get_ocr_reader()
    if not reader:
        return {"text": "", "blocks": [], "confidence": 0, "word_count": 0,
                "error": "OCR motoru kullanılamıyor"}
    
    try:
        # PIL ile aç, numpy array'e çevir
        if PIL_AVAILABLE:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            import numpy as np
            img_array = np.array(img)
        else:
            # Geçici dosyaya yaz
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(image_bytes)
                tmp_path = tmp.name
            return extract_text_from_image(tmp_path, detail=detail)
        
        results = reader.readtext(img_array, detail=1, paragraph=True)
        
        blocks = []
        texts = []
        confidences = []
        
        for item in results:
            if len(item) >= 2:
                text = item[-2] if len(item) == 3 else item[0]
                conf = item[-1] if len(item) == 3 else (item[1] if len(item) == 2 else 0.5)
                if isinstance(conf, str):
                    text, conf = conf, 0.8
                texts.append(str(text))
                confidences.append(float(conf))
                if detail:
                    blocks.append({"text": str(text), "confidence": round(float(conf), 3)})
        
        full_text = "\n".join(texts)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        return {
            "text": full_text,
            "blocks": blocks if detail else [],
            "confidence": round(avg_confidence, 3),
            "word_count": len(full_text.split()),
            "has_table": _detect_table_structure(full_text),
        }
        
    except Exception as e:
        logger.error("ocr_bytes_failed", error=str(e))
        return {"text": "", "blocks": [], "confidence": 0, "word_count": 0, "error": str(e)}


def extract_text_from_pdf_images(
    pdf_bytes: bytes,
    max_pages: int = 20,
) -> Dict[str, Any]:
    """Resim tabanlı PDF'lerden OCR ile metin çıkar.
    
    Args:
        pdf_bytes: PDF dosyasının byte içeriği
        max_pages: Maksimum işlenecek sayfa sayısı
    
    Returns:
        {
            "text": str,
            "pages": [{"page": int, "text": str, "confidence": float}],
            "total_pages": int,
            "avg_confidence": float,
        }
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return {"text": "", "pages": [], "total_pages": 0,
                "error": "PyMuPDF (fitz) yüklü değil. Kurulum: pip install PyMuPDF"}
    
    reader = get_ocr_reader()
    if not reader:
        return {"text": "", "pages": [], "total_pages": 0,
                "error": "OCR motoru kullanılamıyor"}
    
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        pages_to_process = min(total_pages, max_pages)
        
        all_text = []
        page_results = []
        all_confidences = []
        
        for page_num in range(pages_to_process):
            page = doc[page_num]
            
            # Önce doğrudan metin çıkar
            direct_text = page.get_text("text").strip()
            if len(direct_text) > 50:
                # Zaten metin tabanlı sayfa — OCR'a gerek yok
                all_text.append(direct_text)
                page_results.append({
                    "page": page_num + 1,
                    "text": direct_text,
                    "confidence": 1.0,
                    "method": "direct",
                })
                all_confidences.append(1.0)
                continue
            
            # Resim tabanlı sayfa — OCR uygula
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            
            ocr_result = extract_text_from_image_bytes(img_bytes, detail=False)
            page_text = ocr_result.get("text", "")
            page_conf = ocr_result.get("confidence", 0)
            
            if page_text:
                all_text.append(page_text)
                all_confidences.append(page_conf)
            
            page_results.append({
                "page": page_num + 1,
                "text": page_text,
                "confidence": page_conf,
                "method": "ocr",
            })
        
        doc.close()
        
        full_text = "\n\n--- Sayfa ---\n\n".join(all_text)
        avg_conf = sum(all_confidences) / len(all_confidences) if all_confidences else 0
        
        return {
            "text": full_text,
            "pages": page_results,
            "total_pages": total_pages,
            "processed_pages": pages_to_process,
            "avg_confidence": round(avg_conf, 3),
            "word_count": len(full_text.split()),
        }
        
    except Exception as e:
        logger.error("pdf_ocr_failed", error=str(e))
        return {"text": "", "pages": [], "total_pages": 0, "error": str(e)}


def extract_structured_data(
    image_path_or_bytes,
    data_type: str = "auto",
) -> Dict[str, Any]:
    """Yapılandırılmış veri çıkarma — fatura, etiket, tablo.
    
    Args:
        image_path_or_bytes: Görsel dosya yolu veya byte dizisi
        data_type: "fatura", "etiket", "tablo", "auto"
    
    Returns:
        Çıkarılmış yapılandırılmış veri
    """
    # OCR ile metin çıkar
    if isinstance(image_path_or_bytes, bytes):
        ocr_result = extract_text_from_image_bytes(image_path_or_bytes)
    else:
        ocr_result = extract_text_from_image(str(image_path_or_bytes))
    
    text = ocr_result.get("text", "")
    if not text:
        return {"error": "Görselden metin çıkarılamadı", "raw_ocr": ocr_result}
    
    # Otomatik tip tespiti
    if data_type == "auto":
        data_type = _detect_document_type(text)
    
    structured = {
        "type": data_type,
        "raw_text": text,
        "confidence": ocr_result.get("confidence", 0),
    }
    
    if data_type == "fatura":
        structured["extracted"] = _parse_invoice(text)
    elif data_type == "etiket":
        structured["extracted"] = _parse_label(text)
    elif data_type == "tablo":
        structured["extracted"] = _parse_table_text(text)
    else:
        structured["extracted"] = {"text": text}
    
    return structured


# ── Yardımcı Fonksiyonlar ──

def _detect_table_structure(text: str) -> bool:
    """Metinde tablo yapısı var mı kontrol et."""
    lines = text.strip().split('\n')
    if len(lines) < 2:
        return False
    
    # Çoklu boşluk/tab ile ayrılmış sütunlar
    multi_col_lines = sum(1 for line in lines if len(re.split(r'\s{2,}|\t', line)) >= 3)
    return multi_col_lines >= 2


def _detect_document_type(text: str) -> str:
    """OCR metninden doküman tipini algıla."""
    t = text.lower()
    
    if re.search(r'(fatura|invoice|kdv|vergi|toplam\s*tutar|ödeme)', t):
        return "fatura"
    if re.search(r'(etiket|label|lot|parti|gramaj|en\s*cm|boyut)', t):
        return "etiket"
    if _detect_table_structure(text):
        return "tablo"
    return "genel"


def _parse_invoice(text: str) -> Dict:
    """Fatura metninden yapılandırılmış veri çıkar."""
    result = {}
    
    # Tarih
    date_match = re.search(r'(\d{1,2}[./]\d{1,2}[./]\d{2,4})', text)
    if date_match:
        result["tarih"] = date_match.group(1)
    
    # Tutar — en büyük tutarı bul (toplam)
    amounts = re.findall(r'([\d.,]+)\s*(?:TL|₺)', text)
    if amounts:
        try:
            parsed = [float(a.replace('.', '').replace(',', '.')) for a in amounts]
            result["toplam_tutar"] = max(parsed)
            result["tum_tutarlar"] = sorted(parsed)
        except ValueError:
            pass
    
    # KDV
    kdv_match = re.search(r'KDV[:\s]*([\d.,]+)', text, re.I)
    if kdv_match:
        try:
            result["kdv"] = float(kdv_match.group(1).replace('.', '').replace(',', '.'))
        except ValueError:
            pass
    
    # Fatura No
    fatura_no = re.search(r'(?:fatura|invoice)\s*(?:no|#|numarası?)[:\s]*([A-Z0-9\-]+)', text, re.I)
    if fatura_no:
        result["fatura_no"] = fatura_no.group(1)
    
    return result


def _parse_label(text: str) -> Dict:
    """Tekstil etiketinden veri çıkar."""
    result = {}
    
    # Lot / Parti numarası
    lot_match = re.search(r'(?:lot|parti|batch)[:\s#]*([A-Z0-9\-]+)', text, re.I)
    if lot_match:
        result["lot_no"] = lot_match.group(1)
    
    # Gramaj
    gramaj_match = re.search(r'(\d+)\s*(?:gr?/m²|gsm|gram)', text, re.I)
    if gramaj_match:
        result["gramaj"] = int(gramaj_match.group(1))
    
    # En (cm)
    en_match = re.search(r'(?:en|width)[:\s]*(\d+)\s*(?:cm|mm)?', text, re.I)
    if en_match:
        result["en_cm"] = int(en_match.group(1))
    
    # Metraj
    metraj_match = re.search(r'(\d+[.,]?\d*)\s*(?:mt?|metre|meter)', text, re.I)
    if metraj_match:
        result["metraj"] = float(metraj_match.group(1).replace(',', '.'))
    
    # Renk kodu
    renk_match = re.search(r'(?:renk|color)[:\s]*([A-Z0-9\-/]+)', text, re.I)
    if renk_match:
        result["renk_kodu"] = renk_match.group(1)
    
    # Kompozisyon
    komp_match = re.search(r'(\d+%?\s*(?:pamuk|cotton|polyester|pes|viskon|elastan|lycra)[\s,/]+)+', text, re.I)
    if komp_match:
        result["kompozisyon"] = komp_match.group(0).strip()
    
    return result


def _parse_table_text(text: str) -> Dict:
    """Tablo yapısındaki metni parse et."""
    lines = text.strip().split('\n')
    rows = []
    
    for line in lines:
        cells = re.split(r'\s{2,}|\t', line.strip())
        if len(cells) >= 2:
            rows.append(cells)
    
    if not rows:
        return {"rows": [], "columns": 0}
    
    return {
        "rows": rows,
        "columns": max(len(r) for r in rows),
        "row_count": len(rows),
        "header": rows[0] if rows else [],
    }


def get_ocr_capabilities() -> Dict:
    """OCR motor yetenek bilgisi."""
    return {
        "available": EASYOCR_AVAILABLE,
        "pil_available": PIL_AVAILABLE,
        "languages": ["tr", "en"] if EASYOCR_AVAILABLE else [],
        "features": [
            "Görsel metin çıkarma",
            "PDF OCR (resim tabanlı)",
            "Fatura tanıma",
            "Etiket okuma",
            "Tablo çıkarma",
        ] if EASYOCR_AVAILABLE else [],
    }
