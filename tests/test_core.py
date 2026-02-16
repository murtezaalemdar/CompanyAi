"""CompanyAI Test Altyapısı (v4.4.0)

Temel pytest test suite — kritik modüllerin birim testleri.

Çalıştırma: pytest tests/ -v
"""

import pytest
import sys
import os

# Proje kökünü path'e ekle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ══════════════════════════════════════════════════════════════
# 1. TOKEN BUDGET TESTLERİ
# ══════════════════════════════════════════════════════════════

class TestTokenBudget:
    """token_budget.py modülünün testleri."""
    
    def test_estimate_tokens(self):
        from app.core.token_budget import estimate_tokens
        assert estimate_tokens("") == 0
        assert estimate_tokens("test") > 0
        # Türkçe karakter: ~3.5 char/token
        tokens = estimate_tokens("a" * 350)
        assert 95 <= tokens <= 105  # ~100 token bekleniyor
    
    def test_truncate_basic(self):
        from app.core.token_budget import truncate_to_budget
        short = "Kısa metin."
        assert truncate_to_budget(short, "rag_context") == short
    
    def test_truncate_long(self):
        from app.core.token_budget import truncate_to_budget
        long_text = "Bu bir test cümlesidir. " * 5000
        result = truncate_to_budget(long_text, "rag_context")
        assert len(result) < len(long_text)
        assert "[...kırpıldı" in result
    
    def test_compress_text(self):
        from app.core.token_budget import compress_text
        text = "Bu bir test cümlesidir. " * 100
        result = compress_text(text, target_ratio=0.5)
        assert len(result) < len(text)
    
    def test_compress_short_passthrough(self):
        from app.core.token_budget import compress_text
        short = "Kısa."
        assert compress_text(short) == short
    
    def test_check_total_budget(self):
        from app.core.token_budget import check_total_budget
        result = check_total_budget({
            "system_prompt": "Kısa prompt",
            "rag_context": "Kısa context",
        })
        assert "total_tokens" in result
        assert "over_budget" in result
        assert result["over_budget"] is False


# ══════════════════════════════════════════════════════════════
# 2. REFLECTION / SAYISAL DOĞRULAMA TESTLERİ
# ══════════════════════════════════════════════════════════════

class TestReflection:
    """reflection.py modülünün testleri."""
    
    def test_extract_numbers(self):
        from app.core.reflection import _extract_numbers
        nums = _extract_numbers("Fire oranı %3.5, üretim 1500 metre")
        assert len(nums) >= 2
    
    def test_validate_numbers_match(self):
        from app.core.reflection import validate_numbers_against_source
        answer = "Üretim 1500 metre, fire %3.5"
        context = "Kaynak: üretim miktarı 1500 metre, fire oranı %3.5"
        result = validate_numbers_against_source(answer, context)
        assert result["score"] >= 70
        assert result["fabricated"] == 0
    
    def test_validate_numbers_fabricated(self):
        from app.core.reflection import validate_numbers_against_source
        answer = "Üretim 9999 metre, maliyet 50000 TL"
        context = "Kaynak: üretim 100 metre"
        result = validate_numbers_against_source(answer, context)
        assert result["fabricated"] > 0


# ══════════════════════════════════════════════════════════════
# 3. KNOWLEDGE EXTRACTOR TESTLERİ
# ══════════════════════════════════════════════════════════════

class TestKnowledgeExtractor:
    """knowledge_extractor.py kalite filtresi testleri."""
    
    def test_score_high_quality(self):
        from app.core.knowledge_extractor import score_knowledge_quality
        text = (
            "Lot 2345-A için yapılan kalite testinde kopma mukavemeti 245 N/5cm, "
            "boncuklanma 4.5 puan olarak ölçülmüştür. Bu değerler ISO 12945-2 "
            "standardına uygundur. Üretim tarihi: 15.06.2025."
        )
        score = score_knowledge_quality(text, "correction")
        assert score > 0.5
    
    def test_score_low_quality(self):
        from app.core.knowledge_extractor import score_knowledge_quality
        text = "ok tamam"
        score = score_knowledge_quality(text, "general")
        assert score < 0.35
    
    def test_should_save_filter(self):
        from app.core.knowledge_extractor import _should_save
        assert _should_save("ok", "general") is False
        long_text = "Detaylı bir bilgi: stok numarası XY-123, miktar 500 mt, birim fiyat 45.50 TL/mt."
        assert _should_save(long_text, "correction") is True


# ══════════════════════════════════════════════════════════════
# 4. RAPOR ŞABLON TESTLERİ
# ══════════════════════════════════════════════════════════════

class TestReportTemplates:
    """report_templates.py testleri."""
    
    def test_list_templates(self):
        from app.core.report_templates import list_templates
        templates = list_templates()
        assert len(templates) >= 5
    
    def test_list_by_department(self):
        from app.core.report_templates import list_templates
        prod = list_templates(department="Üretim")
        assert all(t["department"] in ("Üretim", "Genel") for t in prod)
    
    def test_render_empty(self):
        from app.core.report_templates import render_template_markdown
        md = render_template_markdown("uretim_performans")
        assert "Üretim Performans Raporu" in md
        assert "[Bu bölüm doldurulmalıdır]" in md
    
    def test_render_with_data(self):
        from app.core.report_templates import render_template_markdown
        md = render_template_markdown("kpi_scorecard", data={
            "scorecard": [["Verimlilik", "%", "95", "92", "97", "↑"]],
            "basarili": ["Verimlilik hedefi aşıldı"],
        })
        assert "Verimlilik" in md
        assert "hedefi aşıldı" in md
    
    def test_detect_template(self):
        from app.core.report_templates import detect_report_template
        assert detect_report_template("üretim performans raporu hazırla") == "uretim_performans"
        assert detect_report_template("maliyet analiz raporu") == "maliyet_analiz"
        assert detect_report_template("kpi scorecard göster") == "kpi_scorecard"
    
    def test_build_prompt(self):
        from app.core.report_templates import build_report_prompt
        prompt = build_report_prompt("kalite_kontrol", "son haftanın kalite raporu")
        assert "Kalite Kontrol" in prompt
        assert "son haftanın" in prompt


# ══════════════════════════════════════════════════════════════
# 5. CHART ENGINE TESTLERİ
# ══════════════════════════════════════════════════════════════

class TestChartEngine:
    """chart_engine.py testleri."""
    
    def test_extract_chart_data(self):
        from app.core.chart_engine import extract_chart_data_from_text
        text = "Verimlilik: 92\nFire: 3.5\nKalite: 88"
        data = extract_chart_data_from_text(text)
        assert data is not None
        assert len(data) >= 2
    
    def test_auto_chart_detection(self):
        from app.core.chart_engine import auto_chart_from_data
        data = {"A": 30, "B": 50, "C": 20}
        result = auto_chart_from_data(data)
        # Pie chart seçilmeli (toplamları 100)
        assert result is not None
        assert result.get("chart_type") in ("pie", "bar")


# ══════════════════════════════════════════════════════════════
# 6. OCR ENGINE TESTLERİ  
# ══════════════════════════════════════════════════════════════

class TestOcrEngine:
    """ocr_engine.py temel import testleri."""
    
    def test_module_importable(self):
        from app.core.ocr_engine import extract_text_from_image_bytes
        assert callable(extract_text_from_image_bytes)
    
    def test_detect_document_type(self):
        from app.core.ocr_engine import _detect_document_type
        assert _detect_document_type("Fatura No: 12345, KDV: %18") == "fatura"
        assert _detect_document_type("Lot No: ABC-123, Gramaj: 250 gr") == "etiket"


# ══════════════════════════════════════════════════════════════
# 7. WHISPER STT TESTLERİ
# ══════════════════════════════════════════════════════════════

class TestWhisperSTT:
    """whisper_stt.py temel testleri."""
    
    def test_status(self):
        from app.core.whisper_stt import get_whisper_status
        status = get_whisper_status()
        assert "available" in status
        assert "supported_formats" in status
        assert ".wav" in status["supported_formats"]
    
    def test_unsupported_format(self):
        from app.core.whisper_stt import transcribe_audio
        result = transcribe_audio(b"fake data", filename="test.xyz")
        assert result["success"] is False
        assert "Desteklenmeyen" in result.get("error", "")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
