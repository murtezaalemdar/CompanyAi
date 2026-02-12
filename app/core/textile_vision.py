"""Textile Vision — Tekstile Özel Görüntü Analiz Modülü

Mevcut multimodal.py'ı güçlendirir:
- Kumaş hatası tespiti (LLM Vision prompt)
- Renk analizi (dominant renkler, sapma)
- Desen karşılaştırma
- Etiket OCR (mevcut pytesseract'ı tekstil odaklı kullanır)
- Kalite kontrol raporu oluşturma
"""

import base64
import io
import json
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
import structlog

logger = structlog.get_logger()

try:
    from PIL import Image, ImageStat, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import numpy as np
    NP_AVAILABLE = True
except ImportError:
    NP_AVAILABLE = False


# ── Renk Analizi ────────────────────────────────────────────────

def analyze_colors(image_path: str, top_n: int = 5) -> Dict:
    """Görseldeki dominant renkleri analiz et."""
    if not PIL_AVAILABLE:
        return {"error": "Pillow kütüphanesi yüklü değil"}

    try:
        img = Image.open(image_path).convert("RGB")
        # Performans için küçült
        img_small = img.resize((150, 150))

        if NP_AVAILABLE:
            pixels = np.array(img_small).reshape(-1, 3)
            # Basit k-means benzeri en sık renkler
            from collections import Counter
            # Renkleri 16'lık gruplara yuvarla
            quantized = (pixels // 16) * 16
            color_counts = Counter(map(tuple, quantized))
            top_colors = color_counts.most_common(top_n)

            colors = []
            total = sum(c for _, c in top_colors)
            for (r, g, b), count in top_colors:
                hex_color = f"#{r:02x}{g:02x}{b:02x}"
                name = _color_name(r, g, b)
                colors.append({
                    "hex": hex_color,
                    "rgb": [int(r), int(g), int(b)],
                    "name": name,
                    "percentage": round(count / total * 100, 1),
                })
        else:
            # PIL fallback — ortalama renk
            stat = ImageStat.Stat(img_small)
            r, g, b = [int(x) for x in stat.mean[:3]]
            colors = [{
                "hex": f"#{r:02x}{g:02x}{b:02x}",
                "rgb": [r, g, b],
                "name": _color_name(r, g, b),
                "percentage": 100,
            }]

        # Genel istatistikler
        stat = ImageStat.Stat(img)
        brightness = sum(stat.mean[:3]) / 3
        contrast = sum(stat.stddev[:3]) / 3

        return {
            "dominant_colors": colors,
            "brightness": round(brightness, 1),
            "contrast": round(contrast, 1),
            "image_size": {"width": img.width, "height": img.height},
            "color_space": "RGB",
        }
    except Exception as e:
        logger.error("color_analysis_failed", error=str(e))
        return {"error": str(e)}


def _color_name(r: int, g: int, b: int) -> str:
    """RGB → Türkçe renk adı (basit harita)."""
    colors = {
        "Kırmızı": (255, 0, 0), "Koyu Kırmızı": (139, 0, 0),
        "Turuncu": (255, 165, 0), "Sarı": (255, 255, 0),
        "Yeşil": (0, 128, 0), "Açık Yeşil": (144, 238, 144),
        "Mavi": (0, 0, 255), "Açık Mavi": (135, 206, 235),
        "Lacivert": (0, 0, 128), "Mor": (128, 0, 128),
        "Pembe": (255, 192, 203), "Kahverengi": (139, 69, 19),
        "Beyaz": (255, 255, 255), "Gri": (128, 128, 128),
        "Koyu Gri": (64, 64, 64), "Siyah": (0, 0, 0),
        "Bej": (245, 222, 179), "Krem": (255, 253, 208),
        "Bordo": (128, 0, 32), "Haki": (195, 176, 145),
    }
    min_dist = float("inf")
    closest = "Bilinmiyor"
    for name, (cr, cg, cb) in colors.items():
        dist = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2
        if dist < min_dist:
            min_dist = dist
            closest = name
    return closest


# ── Desen Analizi ───────────────────────────────────────────────

def analyze_pattern(image_path: str) -> Dict:
    """Kumaş desen yapısını analiz et (edge detection + tekrar analizi)."""
    if not PIL_AVAILABLE:
        return {"error": "Pillow kütüphanesi yüklü değil"}

    try:
        img = Image.open(image_path).convert("L")  # Grayscale
        img_small = img.resize((200, 200))

        # Edge detection
        edges = img_small.filter(ImageFilter.FIND_EDGES)
        edge_stat = ImageStat.Stat(edges)
        edge_intensity = edge_stat.mean[0]

        # Texture analizi (varyans)
        texture = img_small.filter(ImageFilter.DETAIL)
        texture_stat = ImageStat.Stat(texture)
        texture_variance = texture_stat.stddev[0]

        # Desen sınıflandırma (basit kural bazlı)
        if edge_intensity < 15:
            pattern_type = "düz"
            pattern_desc = "Düz / tek renk kumaş"
        elif edge_intensity < 40:
            pattern_type = "hafif_desenli"
            pattern_desc = "Hafif desenli (ince çizgi/puan)"
        elif edge_intensity < 80:
            pattern_type = "orta_desenli"
            pattern_desc = "Orta yoğunlukta desen"
        else:
            pattern_type = "yoğun_desenli"
            pattern_desc = "Yoğun/karmaşık desen"

        # Homojenlik (düzgünlük)
        homogeneity = max(0, 100 - texture_variance)

        return {
            "pattern_type": pattern_type,
            "pattern_description": pattern_desc,
            "edge_intensity": round(edge_intensity, 1),
            "texture_variance": round(texture_variance, 1),
            "homogeneity_score": round(homogeneity, 1),
        }
    except Exception as e:
        logger.error("pattern_analysis_failed", error=str(e))
        return {"error": str(e)}


# ── Kumaş Hata Tespiti (Vision LLM Prompt) ─────────────────────

DEFECT_DETECTION_PROMPT = """Sen bir tekstil kalite kontrol uzmanısın. Aşağıdaki kumaş/tekstil görseli hakkında detaylı analiz yap.

Şu başlıklar altında değerlendir:

1. **Hata Tespiti:**
   - Yırtık, delik, ip çekimi, leke, renk sapması var mı?
   - Dokuma hatası (atlama, kopuş, düzensizlik) var mı?
   - Baskı hatası (kayma, bulanıklık, renk karışması) var mı?
   - Tespit edilen hataların konumu ve şiddeti

2. **Kumaş Türü Tahmini:**
   - Dokuma mı, örme mi, dokusuz mu?
   - Tahmini lif türü (pamuk, polyester, viskon, karışım, vb.)

3. **Kalite Notu (0-100):**
   - 90-100: A kalite (ihracat uygun)
   - 70-89:  B kalite (iç piyasa)
   - 50-69:  C kalite (outlet/indirim)
   - 0-49:   Ret (fire/hurda)

4. **Öneriler:**
   - Tespit edilen hatalar giderilebilir mi?
   - Hangi üretim aşamasında sorun oluşmuş olabilir?

JSON formatında yanıtla:
```json
{
  "defects": [{"type": "...", "severity": "...", "location": "..."}],
  "fabric_type": "...",
  "fiber_estimate": "...",
  "quality_score": 85,
  "quality_grade": "B",
  "recommendations": ["..."],
  "summary": "..."
}
```"""

COLOR_COMPARISON_PROMPT = """Sen bir tekstil renk kontrol uzmanısın. Verilen iki görsel arasındaki renk farklılığını analiz et.

Şu kriterleri değerlendir:
1. **Delta E (Renk Farkı):** Gözle görülebilir fark var mı?
2. **Ton Sapması:** Hangi yöne sapma var? (kırmızıya mı, maviye mi, vb.)
3. **Parlaklık Farkı:** Bir görsel diğerinden daha açık/koyu mu?
4. **Kabul Edilebilirlik:** Tekstil sektörü standartlarına göre (AATCC, ISO 105) kabul edilebilir mi?

JSON formatında yanıtla:
```json
{
  "color_match": true/false,
  "delta_e_estimate": "düşük/orta/yüksek",
  "tone_shift": "...",
  "brightness_diff": "...",
  "acceptable": true/false,
  "notes": "..."
}
```"""


def build_defect_prompt(additional_context: str = "") -> str:
    """Kumaş hata tespiti için LLM prompt'u oluştur."""
    prompt = DEFECT_DETECTION_PROMPT
    if additional_context:
        prompt += f"\n\nEk Bilgi: {additional_context}"
    return prompt


def build_color_comparison_prompt() -> str:
    """Renk karşılaştırma prompt'u."""
    return COLOR_COMPARISON_PROMPT


# ── Görüntü Karşılaştırma ──────────────────────────────────────

def compare_images(image_path_a: str, image_path_b: str) -> Dict:
    """İki görseli karşılaştır (renk + yapı)."""
    if not PIL_AVAILABLE:
        return {"error": "Pillow kütüphanesi yüklü değil"}

    try:
        img_a = Image.open(image_path_a).convert("RGB").resize((200, 200))
        img_b = Image.open(image_path_b).convert("RGB").resize((200, 200))

        stat_a = ImageStat.Stat(img_a)
        stat_b = ImageStat.Stat(img_b)

        # Ortalama renk farkı
        color_diff = sum(abs(a - b) for a, b in zip(stat_a.mean[:3], stat_b.mean[:3])) / 3
        brightness_a = sum(stat_a.mean[:3]) / 3
        brightness_b = sum(stat_b.mean[:3]) / 3

        # Pixel bazlı fark
        if NP_AVAILABLE:
            arr_a = np.array(img_a, dtype=float)
            arr_b = np.array(img_b, dtype=float)
            pixel_diff = np.mean(np.abs(arr_a - arr_b))
            similarity = max(0, 100 - pixel_diff / 2.55)
        else:
            similarity = max(0, 100 - color_diff)

        return {
            "similarity_percent": round(similarity, 1),
            "avg_color_diff": round(color_diff, 1),
            "brightness_diff": round(abs(brightness_a - brightness_b), 1),
            "match": similarity > 85,
            "verdict": "Eşleşme" if similarity > 85 else "Farklı" if similarity < 60 else "Benzer",
        }
    except Exception as e:
        logger.error("image_comparison_failed", error=str(e))
        return {"error": str(e)}


# ── Kalite Kontrol Raporu ───────────────────────────────────────

def generate_quality_report(
    image_path: str,
    order_no: str = "",
    lot_no: str = "",
    fabric_type: str = "",
) -> Dict:
    """Tek görselden kapsamlı kalite kontrol raporu oluştur."""
    report = {
        "order_no": order_no,
        "lot_no": lot_no,
        "fabric_type": fabric_type,
        "timestamp": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    # Renk analizi
    report["color_analysis"] = analyze_colors(image_path)

    # Desen analizi
    report["pattern_analysis"] = analyze_pattern(image_path)

    # Genel kalite skoru (renk + desen bazlı)
    color_score = 80  # varsayılan
    pattern = report["pattern_analysis"]
    if not pattern.get("error"):
        homogeneity = pattern.get("homogeneity_score", 70)
        color_score = min(100, int(homogeneity * 0.7 + 30))

    report["preliminary_quality_score"] = color_score
    report["note"] = "Bu ön analiz sonucudur. Kesin değerlendirme için Vision LLM ile detaylı analiz yapılmalıdır."

    return report


def get_textile_vision_capabilities() -> Dict:
    """Mevcut textile vision yetenekleri."""
    return {
        "color_analysis": PIL_AVAILABLE,
        "pattern_analysis": PIL_AVAILABLE,
        "image_comparison": PIL_AVAILABLE and NP_AVAILABLE,
        "defect_detection": True,  # LLM Vision ile — her zaman mevcut
        "ocr": True,  # pytesseract ile — ayrı modül
        "quality_report": PIL_AVAILABLE,
        "dependencies": {
            "pillow": PIL_AVAILABLE,
            "numpy": NP_AVAILABLE,
        },
    }
