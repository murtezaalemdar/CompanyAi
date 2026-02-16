"""
CompanyAI — Knowledge Extractor Unit Tests
=============================================
classify_knowledge fonksiyonu ve filtreleme regex'leri testleri.
"""

import pytest
from app.core.knowledge_extractor import (
    classify_knowledge,
    SKIP_PATTERNS,
    PURE_QUESTION_PATTERNS,
    SYSTEM_NOISE,
    FACT_PATTERNS,
    PROCESS_PATTERNS,
    DEFINITION_PATTERNS,
    CORRECTION_PATTERNS,
    COMPANY_PATTERNS,
    PREFERENCE_PATTERNS,
    PERSON_ORG_PATTERNS,
)


# ═══════════════════════════════════════════════════
# 1. SKIP_PATTERNS — Kaydetmeye değmeyen mesajlar
# ═══════════════════════════════════════════════════

class TestSkipPatterns:
    """SKIP_PATTERNS regex testleri — bu mesajlar filtrelenmeli."""

    @pytest.mark.parametrize("text", [
        "merhaba",
        "selam",
        "hey",
        "hi",
        "hello",
        "günaydın",
        "iyi akşamlar",
        "hoşça kal",
        "bye",
        "görüşürüz",
        "iyi günler",
    ])
    def test_greetings_filtered(self, text):
        assert SKIP_PATTERNS.match(text) is not None

    @pytest.mark.parametrize("text", [
        "ok", "tamam", "evet", "hayır", "olur", "anladım",
        "teşekkür", "sağol", "eyw", "peki",
    ])
    def test_short_reactions_filtered(self, text):
        assert SKIP_PATTERNS.match(text) is not None

    @pytest.mark.parametrize("text", [
        "güzel", "harika", "süper", "mükemmel", "iyi", "kötü",
    ])
    def test_single_word_opinions_filtered(self, text):
        assert SKIP_PATTERNS.match(text) is not None

    @pytest.mark.parametrize("text", [
        "nasılsın", "ne haber", "naber",
    ])
    def test_smalltalk_filtered(self, text):
        assert SKIP_PATTERNS.match(text) is not None

    def test_meaningful_text_not_filtered(self):
        """Anlamlı metin filtrelenmemeli."""
        assert SKIP_PATTERNS.match("Fabrikamızda 500 ton üretim yapıyoruz") is None

    @pytest.mark.parametrize("text", [
        "???", "!!!", "...", "...",
    ])
    def test_punctuation_only_filtered(self, text):
        assert SKIP_PATTERNS.match(text) is not None


# ═══════════════════════════════════════════════════
# 2. SYSTEM_NOISE — Sistem hata mesajları
# ═══════════════════════════════════════════════════

class TestSystemNoise:
    """Sistem gürültüsü filtreleme testleri."""

    @pytest.mark.parametrize("text", [
        "[Hata] Bağlantı kesildi",
        "[Sistem Notu] Yeniden başlatılıyor",
        "LLM şu an erişilemez",
        "traceback (most recent call last)",
        "exception occurred in handler",
        "status 500 internal server error",
    ])
    def test_system_messages_detected(self, text):
        assert SYSTEM_NOISE.search(text) is not None

    def test_normal_text_not_detected(self):
        assert SYSTEM_NOISE.search("Yıllık üretim raporumuz hazır") is None


# ═══════════════════════════════════════════════════
# 3. classify_knowledge — Ana sınıflandırma
# ═══════════════════════════════════════════════════

class TestClassifyKnowledge:
    """Ana bilgi sınıflandırma fonksiyonu testleri."""

    # ── None dönmesi gereken durumlar ──

    def test_none_for_empty(self):
        assert classify_knowledge("") is None
        assert classify_knowledge(None) is None

    def test_none_for_short_text(self):
        """20 karakterden kısa metin → None."""
        assert classify_knowledge("kısa") is None
        assert classify_knowledge("on karakter") is None

    def test_none_for_greeting(self):
        assert classify_knowledge("merhaba") is None

    def test_none_for_system_noise(self):
        assert classify_knowledge("[Hata] Bu bir hata mesajıdır ve kaydedilmemeli") is None

    def test_none_for_pure_short_question(self):
        """Bilgi içermeyen kısa soru → None."""
        assert classify_knowledge("Nedir bu?") is None
        assert classify_knowledge("Nasıl yapılır?") is None

    def test_none_for_medium_reaction(self):
        """20-50 karakter arası tepki → None."""
        assert classify_knowledge("bu çok güzel olmuş ya") is None

    # ── Düzeltme (correction) ──

    def test_correction_detected(self):
        text = "Hayır, aslında fiyat 150 TL değil 200 TL olmalı."
        assert classify_knowledge(text) == "correction"

    def test_correction_wrong_detected(self):
        text = "Yanlış, doğrusu şöyle olmalıdır bu hesaplamanın sonucu."
        assert classify_knowledge(text) == "correction"

    # ── Fact (somut bilgi) ──

    def test_fact_numeric_data(self):
        assert classify_knowledge("Yıllık üretimimiz 500 ton civarında gerçekleşiyor") == "fact"

    def test_fact_year(self):
        assert classify_knowledge("Şirketimiz 2015 yılında kuruldu ve o zamandan beri büyüyor") == "fact"

    def test_fact_email(self):
        assert classify_knowledge("İletişim için mehmet@company.com adresine yazabilirsiniz") == "fact"

    def test_fact_phone(self):
        assert classify_knowledge("Müşteri hizmetleri numarası 212 555 44 33 olarak güncellenmiştir") == "fact"

    # ── Process (süreç/prosedür) ──

    def test_process_detected(self):
        text = "Önce kalite kontrol yapılır, sonra paketleme aşamasına geçilir."
        assert classify_knowledge(text) == "process"

    def test_process_numbered_list(self):
        text = "1. Sipariş alınır 2. Üretim başlar 3. Kalite kontrol yapılır"
        assert classify_knowledge(text) == "process"

    # ── Definition (tanım) ──

    def test_definition_detected(self):
        text = "Gramaj demektir kumaşın birim alan başına ağırlığıdır"
        assert classify_knowledge(text) == "definition"

    def test_definition_meaning(self):
        text = "Apre işlemi, kumaşa son görünümü veren terbiye işlemleri anlamına gelir."
        assert classify_knowledge(text) == "definition"

    # ── Company (şirket bilgisi) ──

    def test_company_product(self):
        text = "Firmamız polyester iplik üretimi konusunda uzmanlaşmıştır."
        assert classify_knowledge(text) == "company"

    def test_company_machinery(self):
        text = "Fabrikamızda 20 adet rapier dokuma tezgahı bulunmaktadır."
        result = classify_knowledge(text)
        assert result in ("fact", "company")  # Rapier + sayı → fact veya company

    # ── Preference (tercih) ──

    def test_preference_detected(self):
        text = "Yeni ERP yazılımını kullanıyoruz ve eski sistemi terk ettik."
        result = classify_knowledge(text)
        assert result in ("preference", "company")  # company pattern daha geniş, öncelikli

    # ── Person/Org ──

    def test_person_org_detected(self):
        text = "Ahmet Bey satın alma birimi müdürü olarak bu konuda yetkili"
        result = classify_knowledge(text)
        assert result in ("person_org", "company")  # company pattern daha geniş, öncelikli

    # ── General (genel) ──

    def test_general_for_long_unclassified(self):
        """50+ karakter ama hiçbir pattern'e uymayan → general."""
        text = "Bu konu hakkında daha detaylı bir araştırma yapmamız gerekiyor gibi görünüyor"
        result = classify_knowledge(text)
        assert result is not None  # None olmamalı, en az 'general'

    # ── Edge Cases ──

    def test_question_with_info_saved(self):
        """Bilgi de içeren uzun soru kaydedilmeli."""
        text = "Fabrikamızda 500 ton üretim kapasitesi varken neden bu kadar az satış yapıyoruz?"
        result = classify_knowledge(text)
        assert result is not None  # Sayısal bilgi var → kaydedilmeli

    def test_whitespace_only_returns_none(self):
        assert classify_knowledge("                    ") is None
