"""Textile Vision — Tekstile Özel Görüntü Analiz Modülü (v2)

Mevcut multimodal.py'ı güçlendirir:
- Kumaş hatası tespiti (LLM Vision prompt)
- Renk analizi (dominant renkler, HSV dönüşümü, histogram, sapma)
- Desen karşılaştırma (kenar tespiti, gelişmiş doku metrikleri)
- Etiket OCR (EasyOCR tabanlı tekstil odaklı analiz)
- Kalite kontrol raporu, hata geçmişi, kalite trendi
- Toplu analiz, palet karşılaştırma, yıpranma tahmini

Singleton TextileVisionAnalyzer sınıfı tüm analizleri yönetir.
Geriye uyumlu modül-seviye fonksiyonlar korunmuştur.
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

# ── Sabit Prompt Metinleri ──────────────────────────────────────

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


# ── TextileVisionAnalyzer — Singleton ───────────────────────────

class TextileVisionAnalyzer:
    """Tekstil görüntü analiz motoru — Singleton deseni.
    İstatistik takibi, hata geçmişi ve kalite trendi sağlar."""

    _instance = None

    def __new__(cls):
        """Singleton: her zaman aynı nesneyi döndür."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """İlk oluşturmada istatistik ve geçmiş yapılarını başlat."""
        if self._initialized:
            return
        self._initialized = True
        self._stats: Dict[str, Any] = {
            "total_analyses": 0, "color_analyses": 0,
            "pattern_analyses": 0, "defects_found": 0,
            "avg_quality_score": 0.0, "images_compared": 0,
            "batch_analyses": 0, "wear_estimations": 0,
            "palette_comparisons": 0, "ocr_analyses": 0,
        }
        self._defect_history: List[Dict] = []
        self._quality_history: List[Dict] = []
        self._quality_score_sum: float = 0.0
        self._quality_score_count: int = 0

    # ── Dashboard ───────────────────────────────────────────
    def get_dashboard(self) -> Dict[str, Any]:
        """Analiz istatistiklerini ve özet bilgileri döndür."""
        return {
            "stats": dict(self._stats),
            "defect_history_count": len(self._defect_history),
            "quality_history_count": len(self._quality_history),
            "recent_defects": self._defect_history[-5:] if self._defect_history else [],
            "recent_quality_scores": self._quality_history[-10:] if self._quality_history else [],
            "pil_available": PIL_AVAILABLE,
            "numpy_available": NP_AVAILABLE,
        }

    # ── Yardımcı: RGB → HSV ────────────────────────────────
    @staticmethod
    def _rgb_to_hsv(r: int, g: int, b: int) -> Tuple[float, float, float]:
        """RGB → HSV dönüşümü (H:0-360, S:0-100, V:0-100)."""
        r_n, g_n, b_n = r / 255.0, g / 255.0, b / 255.0
        c_max, c_min = max(r_n, g_n, b_n), min(r_n, g_n, b_n)
        delta = c_max - c_min
        if delta == 0:
            h = 0.0
        elif c_max == r_n:
            h = 60.0 * (((g_n - b_n) / delta) % 6)
        elif c_max == g_n:
            h = 60.0 * (((b_n - r_n) / delta) + 2)
        else:
            h = 60.0 * (((r_n - g_n) / delta) + 4)
        s = 0.0 if c_max == 0 else (delta / c_max) * 100
        v = c_max * 100
        return round(h, 1), round(s, 1), round(v, 1)

    # ── Yardımcı: Türkçe renk adı ─────────────────────────
    @staticmethod
    def _color_name(r: int, g: int, b: int) -> str:
        """RGB → Türkçe renk adı (en yakın Öklid mesafesi)."""
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

    # ── Renk Histogramı ────────────────────────────────────
    def _compute_color_histogram(self, img: "Image.Image", bins: int = 32) -> Dict:
        """Kanal bazlı (R/G/B) renk histogramı ve dağılım istatistikleri."""
        if not NP_AVAILABLE:
            return {}
        pixels = np.array(img).reshape(-1, 3)
        histogram: Dict[str, Any] = {}
        for i, ch in enumerate(["red", "green", "blue"]):
            hist, _ = np.histogram(pixels[:, i], bins=bins, range=(0, 256))
            histogram[ch] = hist.tolist()
        histogram["mean_rgb"] = [round(float(np.mean(pixels[:, i])), 1) for i in range(3)]
        histogram["std_rgb"] = [round(float(np.std(pixels[:, i])), 1) for i in range(3)]
        return histogram

    # ── Doku Entropi Metrikleri (GLCM benzeri) ─────────────
    def _compute_texture_entropy(self, img_gray: "Image.Image") -> Dict:
        """PIL+numpy ile doku analizi: entropi, yerel varyans, gradyan."""
        if not NP_AVAILABLE:
            return {"entropy_estimate": 0.0}
        arr = np.array(img_gray, dtype=float)
        h, w = arr.shape
        # Yerel varyans (3×3, adım=2)
        local_vars = []
        for y in range(1, h - 1, 2):
            for x in range(1, w - 1, 2):
                local_vars.append(np.var(arr[y - 1:y + 2, x - 1:x + 2]))
        lv = np.array(local_vars) if local_vars else np.array([0.0])
        # Shannon entropisi
        hist, _ = np.histogram(arr.ravel(), bins=64, range=(0, 256))
        total = hist.sum()
        p = hist / total if total > 0 else hist
        nz = p[p > 0]
        entropy = float(-np.sum(nz * np.log2(nz)))
        # Gradyanlar
        h_diff = float(np.mean(np.abs(np.diff(arr, axis=1)))) if w > 1 else 0.0
        v_diff = float(np.mean(np.abs(np.diff(arr, axis=0)))) if h > 1 else 0.0
        lv_mean = float(np.mean(lv))
        return {
            "entropy": round(entropy, 3),
            "local_variance_mean": round(lv_mean, 2),
            "local_variance_std": round(float(np.std(lv)), 2),
            "horizontal_gradient": round(h_diff, 2),
            "vertical_gradient": round(v_diff, 2),
            "texture_uniformity": round(1.0 / (1.0 + lv_mean), 4),
        }

    # ── Renk Analizi ───────────────────────────────────────
    def analyze_colors(self, image_path: str, top_n: int = 5) -> Dict:
        """Görseldeki dominant renkleri analiz et — HSV ve histogram destekli."""
        if not PIL_AVAILABLE:
            return {"error": "Pillow kütüphanesi yüklü değil"}
        self._stats["total_analyses"] += 1
        self._stats["color_analyses"] += 1
        try:
            img = Image.open(image_path).convert("RGB")
            img_small = img.resize((150, 150))
            if NP_AVAILABLE:
                pixels = np.array(img_small).reshape(-1, 3)
                from collections import Counter
                quantized = (pixels // 16) * 16
                color_counts = Counter(map(tuple, quantized))
                top_colors = color_counts.most_common(top_n)
                colors = []
                total = sum(c for _, c in top_colors)
                for (r, g, b), count in top_colors:
                    hex_color = f"#{r:02x}{g:02x}{b:02x}"
                    name = self._color_name(r, g, b)
                    hsv = self._rgb_to_hsv(r, g, b)
                    colors.append({
                        "hex": hex_color,
                        "rgb": [int(r), int(g), int(b)],
                        "hsv": list(hsv),
                        "name": name,
                        "percentage": round(count / total * 100, 1),
                    })
            else:
                stat = ImageStat.Stat(img_small)
                r, g, b = [int(x) for x in stat.mean[:3]]
                hsv = self._rgb_to_hsv(r, g, b)
                colors = [{
                    "hex": f"#{r:02x}{g:02x}{b:02x}",
                    "rgb": [r, g, b], "hsv": list(hsv),
                    "name": self._color_name(r, g, b),
                    "percentage": 100,
                }]
            stat = ImageStat.Stat(img)
            brightness = sum(stat.mean[:3]) / 3
            contrast = sum(stat.stddev[:3]) / 3
            histogram = self._compute_color_histogram(img_small)
            return {
                "dominant_colors": colors,
                "brightness": round(brightness, 1),
                "contrast": round(contrast, 1),
                "image_size": {"width": img.width, "height": img.height},
                "color_space": "RGB+HSV",
                "histogram": histogram,
            }
        except Exception as e:
            logger.error("color_analysis_failed", error=str(e))
            return {"error": str(e)}

    # ── Desen Analizi ──────────────────────────────────────
    def analyze_pattern(self, image_path: str) -> Dict:
        """Kumaş desen yapısını analiz et — gelişmiş doku metrikleri ile."""
        if not PIL_AVAILABLE:
            return {"error": "Pillow kütüphanesi yüklü değil"}
        self._stats["total_analyses"] += 1
        self._stats["pattern_analyses"] += 1
        try:
            img = Image.open(image_path).convert("L")
            img_small = img.resize((200, 200))
            edges = img_small.filter(ImageFilter.FIND_EDGES)
            edge_stat = ImageStat.Stat(edges)
            edge_intensity = edge_stat.mean[0]
            texture = img_small.filter(ImageFilter.DETAIL)
            texture_stat = ImageStat.Stat(texture)
            texture_variance = texture_stat.stddev[0]
            if edge_intensity < 15:
                pattern_type, pattern_desc = "düz", "Düz / tek renk kumaş"
            elif edge_intensity < 40:
                pattern_type, pattern_desc = "hafif_desenli", "Hafif desenli (ince çizgi/puan)"
            elif edge_intensity < 80:
                pattern_type, pattern_desc = "orta_desenli", "Orta yoğunlukta desen"
            else:
                pattern_type, pattern_desc = "yoğun_desenli", "Yoğun/karmaşık desen"
            homogeneity = max(0, 100 - texture_variance)
            texture_metrics = self._compute_texture_entropy(img_small)
            return {
                "pattern_type": pattern_type,
                "pattern_description": pattern_desc,
                "edge_intensity": round(edge_intensity, 1),
                "texture_variance": round(texture_variance, 1),
                "homogeneity_score": round(homogeneity, 1),
                "texture_metrics": texture_metrics,
            }
        except Exception as e:
            logger.error("pattern_analysis_failed", error=str(e))
            return {"error": str(e)}

    # ── Görüntü Karşılaştırma ─────────────────────────────
    def compare_images(self, image_path_a: str, image_path_b: str) -> Dict:
        """İki görseli karşılaştır (renk + yapı benzerliği)."""
        if not PIL_AVAILABLE:
            return {"error": "Pillow kütüphanesi yüklü değil"}
        self._stats["total_analyses"] += 1
        self._stats["images_compared"] += 1
        try:
            img_a = Image.open(image_path_a).convert("RGB").resize((200, 200))
            img_b = Image.open(image_path_b).convert("RGB").resize((200, 200))
            stat_a, stat_b = ImageStat.Stat(img_a), ImageStat.Stat(img_b)
            color_diff = sum(abs(a - b) for a, b in zip(stat_a.mean[:3], stat_b.mean[:3])) / 3
            brightness_a = sum(stat_a.mean[:3]) / 3
            brightness_b = sum(stat_b.mean[:3]) / 3
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

    # ── Kalite Kontrol Raporu ──────────────────────────────
    def generate_quality_report(self, image_path: str, order_no: str = "",
                                lot_no: str = "", fabric_type: str = "") -> Dict:
        """Tek görselden kapsamlı kalite kontrol raporu oluştur."""
        self._stats["total_analyses"] += 1
        report: Dict[str, Any] = {
            "order_no": order_no, "lot_no": lot_no,
            "fabric_type": fabric_type,
            "timestamp": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        report["color_analysis"] = self.analyze_colors(image_path)
        report["pattern_analysis"] = self.analyze_pattern(image_path)
        color_score = 80
        pattern = report["pattern_analysis"]
        if not pattern.get("error"):
            homogeneity = pattern.get("homogeneity_score", 70)
            color_score = min(100, int(homogeneity * 0.7 + 30))
        report["preliminary_quality_score"] = color_score
        report["note"] = ("Bu ön analiz sonucudur. Kesin değerlendirme için "
                          "Vision LLM ile detaylı analiz yapılmalıdır.")
        self._track_quality_score(color_score, image_path)
        return report

    # ── Prompt Oluşturma ───────────────────────────────────
    @staticmethod
    def build_defect_prompt(additional_context: str = "") -> str:
        """Kumaş hata tespiti için LLM prompt'u oluştur."""
        prompt = DEFECT_DETECTION_PROMPT
        if additional_context:
            prompt += f"\n\nEk Bilgi: {additional_context}"
        return prompt

    @staticmethod
    def build_color_comparison_prompt() -> str:
        """Renk karşılaştırma prompt'u döndür."""
        return COLOR_COMPARISON_PROMPT

    # ── OCR ─────────────────────────────────────────────────
    def ocr_analyze_label(self, image_path: str) -> Dict:
        """Tekstil etiketini OCR ile oku ve yapılandırılmış veri çıkar.
        EasyOCR tabanlı — Türkçe + İngilizce destekli.
        """
        self._stats["total_analyses"] += 1
        self._stats["ocr_analyses"] += 1
        try:
            from app.core.ocr_engine import extract_structured_data, EASYOCR_AVAILABLE
            if not EASYOCR_AVAILABLE:
                return {"error": "EasyOCR yüklü değil. pip install easyocr"}
            return extract_structured_data(image_path, data_type="etiket")
        except Exception as e:
            logger.error("ocr_label_failed", error=str(e), path=image_path)
            return {"error": str(e)}

    def ocr_analyze_invoice(self, image_path: str) -> Dict:
        """Fatura görselini OCR ile oku ve yapılandırılmış veri çıkar."""
        self._stats["total_analyses"] += 1
        self._stats["ocr_analyses"] += 1
        try:
            from app.core.ocr_engine import extract_structured_data, EASYOCR_AVAILABLE
            if not EASYOCR_AVAILABLE:
                return {"error": "EasyOCR yüklü değil. pip install easyocr"}
            return extract_structured_data(image_path, data_type="fatura")
        except Exception as e:
            logger.error("ocr_invoice_failed", error=str(e), path=image_path)
            return {"error": str(e)}

    # ── Yetenekler ─────────────────────────────────────────
    def get_capabilities(self) -> Dict:
        """Mevcut textile vision yeteneklerini döndür."""
        try:
            from app.core.ocr_engine import EASYOCR_AVAILABLE
            ocr_available = EASYOCR_AVAILABLE
        except ImportError:
            ocr_available = False
        return {
            "color_analysis": PIL_AVAILABLE,
            "pattern_analysis": PIL_AVAILABLE,
            "image_comparison": PIL_AVAILABLE and NP_AVAILABLE,
            "defect_detection": True,
            "ocr": ocr_available,
            "ocr_engine": "easyocr" if ocr_available else "none",
            "ocr_languages": ["tr", "en"] if ocr_available else [],
            "label_reading": ocr_available,
            "invoice_reading": ocr_available,
            "quality_report": PIL_AVAILABLE,
            "batch_analysis": PIL_AVAILABLE,
            "color_palette_comparison": PIL_AVAILABLE and NP_AVAILABLE,
            "fabric_wear_estimation": PIL_AVAILABLE,
            "dashboard": True,
            "defect_history": True,
            "quality_trending": True,
            "dependencies": {
                "pillow": PIL_AVAILABLE,
                "numpy": NP_AVAILABLE,
                "easyocr": ocr_available,
            },
        }

    # ── Hata Geçmişi ──────────────────────────────────────
    def track_defect(self, defect_type: str, severity: str,
                     image_path: str = "", notes: str = "") -> Dict:
        """Tespit edilen hatayı geçmişe kaydet."""
        self._stats["defects_found"] += 1
        entry = {
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "defect_type": defect_type, "severity": severity,
            "image_path": image_path, "notes": notes,
        }
        self._defect_history.append(entry)
        logger.info("defect_tracked", defect_type=defect_type, severity=severity)
        return entry

    def get_defect_history(self, last_n: int = 50) -> List[Dict]:
        """Son N hata kaydını döndür."""
        return self._defect_history[-last_n:]

    # ── Kalite Trendi ──────────────────────────────────────
    def _track_quality_score(self, score: float, image_path: str = "") -> None:
        """Kalite skorunu trend verisine ekle ve ortalamayı güncelle."""
        self._quality_score_sum += score
        self._quality_score_count += 1
        self._stats["avg_quality_score"] = round(
            self._quality_score_sum / self._quality_score_count, 1)
        self._quality_history.append({
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "score": score, "image_path": image_path,
        })

    def get_quality_trend(self, last_n: int = 30) -> Dict:
        """Kalite trendi: yükseliyor / düşüyor / sabit / yetersiz_veri / veri_yok."""
        recent = self._quality_history[-last_n:]
        if not recent:
            return {"trend": "veri_yok", "scores": [], "average": 0, "count": 0}
        scores = [e["score"] for e in recent]
        avg = sum(scores) / len(scores)
        if len(scores) >= 3:
            mid = len(scores) // 2
            f_avg = sum(scores[:mid]) / mid
            s_avg = sum(scores[mid:]) / len(scores[mid:])
            if s_avg > f_avg + 2:
                trend = "yükseliyor"
            elif s_avg < f_avg - 2:
                trend = "düşüyor"
            else:
                trend = "sabit"
        else:
            trend = "yetersiz_veri"
        return {
            "trend": trend, "scores": recent,
            "average": round(avg, 1),
            "min": min(scores), "max": max(scores),
            "count": len(scores),
        }

    # ── Toplu Analiz ───────────────────────────────────────
    def batch_analyze(self, image_paths: List[str],
                      analyses: Optional[List[str]] = None) -> List[Dict]:
        """Birden fazla görseli toplu analiz et.
        analyses: "color", "pattern", "quality" listesi (None → color+pattern).
        """
        if analyses is None:
            analyses = ["color", "pattern"]
        self._stats["batch_analyses"] += 1
        results: List[Dict] = []
        for path in image_paths:
            result: Dict[str, Any] = {"image_path": path}
            if "color" in analyses:
                result["color"] = self.analyze_colors(path)
            if "pattern" in analyses:
                result["pattern"] = self.analyze_pattern(path)
            if "quality" in analyses:
                result["quality"] = self.generate_quality_report(path)
            results.append(result)
        return results

    # ── Renk Paleti Karşılaştırma ─────────────────────────
    def compare_color_palettes(self, image_path_a: str, image_path_b: str,
                               top_n: int = 5) -> Dict:
        """İki görselin renk paletlerini karşılaştır — eşleşme ve benzerlik."""
        self._stats["palette_comparisons"] += 1
        self._stats["total_analyses"] += 1
        palette_a = self.analyze_colors(image_path_a, top_n=top_n)
        palette_b = self.analyze_colors(image_path_b, top_n=top_n)
        if palette_a.get("error") or palette_b.get("error"):
            return {"error": palette_a.get("error") or palette_b.get("error")}
        colors_a = palette_a.get("dominant_colors", [])
        colors_b = palette_b.get("dominant_colors", [])
        matches: List[Dict] = []
        if colors_a and colors_b:
            for ca in colors_a:
                best_dist, best_match = float("inf"), None
                ra, ga, ba = ca["rgb"]
                for cb in colors_b:
                    rb, gb, bb = cb["rgb"]
                    dist = ((ra - rb) ** 2 + (ga - gb) ** 2 + (ba - bb) ** 2) ** 0.5
                    if dist < best_dist:
                        best_dist, best_match = dist, cb
                matches.append({
                    "color_a": ca, "closest_in_b": best_match,
                    "distance": round(best_dist, 1), "is_close": best_dist < 50,
                })
        if matches:
            avg_dist = sum(m["distance"] for m in matches) / len(matches)
            palette_similarity = max(0.0, 100.0 - (avg_dist / 4.42))
        else:
            avg_dist, palette_similarity = 0.0, 0.0
        return {
            "palette_a": colors_a, "palette_b": colors_b,
            "matches": matches,
            "avg_color_distance": round(avg_dist, 1),
            "palette_similarity": round(palette_similarity, 1),
            "compatible": palette_similarity > 70,
        }

    # ── Kumaş Yıpranma Tahmini ────────────────────────────
    def estimate_fabric_wear(self, image_path: str) -> Dict:
        """Kumaş yıpranma skoru (0-100): kontrast, entropi, homojenlik bazlı."""
        if not PIL_AVAILABLE:
            return {"error": "Pillow kütüphanesi yüklü değil"}
        self._stats["wear_estimations"] += 1
        self._stats["total_analyses"] += 1
        try:
            color_data = self.analyze_colors(image_path)
            pattern_data = self.analyze_pattern(image_path)
            if color_data.get("error") or pattern_data.get("error"):
                return {"error": color_data.get("error") or pattern_data.get("error")}
            indicators: List[str] = []
            wear_score = 0
            # 1. Kontrast → renk solması
            contrast = color_data.get("contrast", 50)
            if contrast < 20:
                indicators.append("Düşük kontrast — olası renk solması")
                wear_score += 25
            elif contrast < 35:
                indicators.append("Orta kontrast — hafif solma olabilir")
                wear_score += 10
            # 2. Homojenlik → yüzey bozulması
            homogeneity = pattern_data.get("homogeneity_score", 70)
            if homogeneity < 40:
                indicators.append("Düşük homojenlik — yüzey bozulması olabilir")
                wear_score += 25
            elif homogeneity < 60:
                indicators.append("Orta homojenlik — hafif yüzey değişimi")
                wear_score += 10
            # 3. Entropi ve yerel varyans
            tex = pattern_data.get("texture_metrics", {})
            entropy = tex.get("entropy", 4.0)
            local_var = tex.get("local_variance_mean", 100)
            if entropy > 6.5:
                indicators.append("Yüksek entropi — düzensiz yüzey")
                wear_score += 15
            if local_var > 500:
                indicators.append("Yüksek yerel varyans — pürüzlü/yıpranmış yüzey")
                wear_score += 15
            # 4. Parlaklık aşırılığı
            brightness = color_data.get("brightness", 128)
            if brightness > 200:
                indicators.append("Çok açık görüntü — ağartma/solma olabilir")
                wear_score += 10
            wear_score = min(100, wear_score)
            if wear_score < 15:
                wear_level, wear_desc = "yeni", "Kumaş yeni veya çok az kullanılmış görünüyor"
            elif wear_score < 35:
                wear_level, wear_desc = "hafif", "Hafif kullanım izleri"
            elif wear_score < 60:
                wear_level, wear_desc = "orta", "Belirgin kullanım/yıpranma izleri"
            else:
                wear_level, wear_desc = "yüksek", "Ciddi yıpranma belirtileri"
            return {
                "wear_score": wear_score,
                "wear_level": wear_level,
                "wear_description": wear_desc,
                "indicators": indicators,
                "raw_metrics": {
                    "contrast": contrast, "homogeneity": homogeneity,
                    "entropy": entropy, "local_variance": local_var,
                    "brightness": brightness,
                },
            }
        except Exception as e:
            logger.error("wear_estimation_failed", error=str(e))
            return {"error": str(e)}


# ── Modül Seviye Fonksiyonlar — Geriye Uyumluluk ───────────────

def _get_analyzer() -> TextileVisionAnalyzer:
    """Singleton analyzer nesnesini döndür."""
    return TextileVisionAnalyzer()


def _color_name(r: int, g: int, b: int) -> str:
    """RGB → Türkçe renk adı (geriye uyumlu sarmalayıcı)."""
    return TextileVisionAnalyzer._color_name(r, g, b)


def analyze_colors(image_path: str, top_n: int = 5) -> Dict:
    """Görseldeki dominant renkleri analiz et."""
    return _get_analyzer().analyze_colors(image_path, top_n)


def analyze_pattern(image_path: str) -> Dict:
    """Kumaş desen yapısını analiz et."""
    return _get_analyzer().analyze_pattern(image_path)


def compare_images(image_path_a: str, image_path_b: str) -> Dict:
    """İki görseli karşılaştır (renk + yapı)."""
    return _get_analyzer().compare_images(image_path_a, image_path_b)


def generate_quality_report(image_path: str, order_no: str = "",
                            lot_no: str = "", fabric_type: str = "") -> Dict:
    """Tek görselden kapsamlı kalite kontrol raporu oluştur."""
    return _get_analyzer().generate_quality_report(image_path, order_no, lot_no, fabric_type)


def build_defect_prompt(additional_context: str = "") -> str:
    """Kumaş hata tespiti için LLM prompt'u oluştur."""
    return TextileVisionAnalyzer.build_defect_prompt(additional_context)


def build_color_comparison_prompt() -> str:
    """Renk karşılaştırma prompt'u."""
    return TextileVisionAnalyzer.build_color_comparison_prompt()


def ocr_analyze_label(image_path: str) -> Dict:
    """Tekstil etiketini OCR ile oku ve yapılandırılmış veri çıkar.
    EasyOCR tabanlı — Türkçe + İngilizce destekli.
    """
    return _get_analyzer().ocr_analyze_label(image_path)


def ocr_analyze_invoice(image_path: str) -> Dict:
    """Fatura görselini OCR ile oku ve yapılandırılmış veri çıkar."""
    return _get_analyzer().ocr_analyze_invoice(image_path)


def get_textile_vision_capabilities() -> Dict:
    """Mevcut textile vision yetenekleri."""
    return _get_analyzer().get_capabilities()
