"""Prompt Templates - Kurumsal AI Asistanı (v5.9.0 Optimize)

Derin sistem prompt'ları, chain-of-thought yönlendirme,
sektörel terminoloji, KPI yorumlama kalıpları, risk analizi dili.

v5.9.0 DEĞİŞİKLİKLER (ÖNEMLİ — İŞE YARADI):
- SYSTEM_PROMPT: ~%60 kısaltıldı → token tasarrufu
- DEPARTMENT_PROMPTS: ~%80 kısaltıldı → verbose örnekler kaldırıldı
- MODE_PROMPTS: Analiz 500+ → ~150 token
- build_prompt(): Max 1 uzmanlık şablonu seçilir (biriken şablonlar engellendi)
- build_rag_prompt(): Doküman kuralları 6 → 3 madde

TODO GELİŞTİRİLMELİ:
- [ ] REASONING_TEMPLATES hâlâ uzun (~150 token/şablon) → kısaltılabilir
- [ ] ACTION_PLAN_TEMPLATE ve MULTI_PERSPECTIVE_TEMPLATE kullanılmıyor → temizle veya yeniden entegre et
- [ ] STRUCTURED_OUTPUT_PROMPT kullanılmıyor → frontend JSON gösterim bileşeni ile birlikte değerlendir
- [ ] CoT şablonlarının etkinliğini ölç (hangileri gerçekten yanıt kalitesini artırıyor?)
"""

import re
import base64
from typing import Optional

# ══════════════════════════════════════════════════════════════
# 1. PROMPT INJECTION KORUMASI (v3.1 — base64 algılama eklendi)
# ══════════════════════════════════════════════════════════════

_INJECTION_PATTERNS = [
    r"ignore\s+(previous|above|all)\s+(instructions?|prompts?|rules?)",
    r"forget\s+(everything|all|your)\s+(instructions?|rules?|training)",
    r"you\s+are\s+now\s+(a|an|the)\s+",
    r"system\s*:\s*",
    r"<\|?\s*(system|im_start|im_end)\s*\|?>",
    r"act\s+as\s+(if|a|an)\s+",
    r"pretend\s+(you|that)\s+(are|were)\s+",
    r"override\s+(your|the|all)\s+(instructions?|rules?|behavior)",
    r"new\s+instruction|reveal\s+(your|the)\s+(prompt|instruction)",
    r"(DAN|jailbreak|bypass)\s+mode",
    r"repeat\s+(the|your)\s+(system|initial)\s+(prompt|message|instruction)",
    r"translate\s+(the|your)\s+(system|initial)\s+(prompt|instruction)",
    r"what\s+(is|are)\s+your\s+(system|initial)\s+(prompt|instruction|rule)",
]
_injection_regex = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)

# Base64 encoded injection detection
_BASE64_PATTERN = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")


def _detect_base64_injection(text: str) -> bool:
    """Base64 kodlanmış injection girişimlerini algılar."""
    matches = _BASE64_PATTERN.findall(text)
    for match in matches:
        try:
            decoded = base64.b64decode(match).decode("utf-8", errors="ignore")
            if _injection_regex.search(decoded):
                return True
        except Exception:
            continue
    return False


def sanitize_input(text: str) -> str:
    if _injection_regex.search(text) or _detect_base64_injection(text):
        return f"[Kullanıcı sorusu]: {text}"
    return text


def sanitize_document_content(text: str) -> str:
    cleaned = re.sub(r"<\|?\s*(system|im_start|im_end)\s*\|?>", "", text)
    cleaned = re.sub(r"\[INST\]|\[/INST\]|\[SYS\]|\[/SYS\]", "", cleaned)
    return cleaned.strip()


# ══════════════════════════════════════════════════════════════
# 2. ANA SİSTEM PROMPT — DERİN & YAPISAL
# ══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """Sen Company.AI — kurumsal yapay zeka asistanısın.
Tekstil sektöründe faaliyet gösteren bir holding grubunun tüm departmanlarına hizmet veriyorsun.

## MUTLAK KURAL: VARSAYILAN KISA YANIT
Her yanıtın VARSAYILAN olarak KISA olmalı (2-4 cümle, düz metin).
Liste, başlık, numaralı madde, uzun açıklama YAPMA — kullanıcı açıkça istemediği sürece.
Sadece şu durumlarda detaylı/uzun yanıt ver:
- Kullanıcı "detaylı anlat", "kapsamlı", "ayrıntılı", "madde madde", "listele" gibi açıkça isterse
- Mod Analiz veya Rapor ise

## Diğer Kurallar
- Türkçe, profesyonel, samimi.
- Bilmediğini UYDURMA. "Bu konuda kesin bilgim yok" de.
- Sayısal verilerde birim kullan (₺, kg, m, adet, %, gün).
- Gereksiz tekrar yapma, sorunun cevabını doğrudan söyle.
"""


# ══════════════════════════════════════════════════════════════
# 3. DEPARTMAN PROMPT'LARI — DERİN & UZMANLIK
# ══════════════════════════════════════════════════════════════

DEPARTMENT_PROMPTS = {
    "Üretim": """## Üretim Uzmanlığı
Tekstil üretim süreçlerinde uzmansın: İplik, Dokuma, Boyahane, Konfeksiyon, Terbiye/Apre.
Kritik Metrikler: Fire Oranı (hedef <%2), OEE (hedef >%85), Duruş Analizi, Çevrim Süresi.
Fire yorum: <%2 iyi, %2-5 normal, >%5 kritik. OEE: >%85 dünya sınıfı, %70-85 iyi, <%70 iyileştirme gerek.
6 Büyük Kayıp: Arıza, setup, boş çalışma, hız kaybı, fire, başlangıç kaybı.""",

    "Finans": """## Finans Uzmanlığı
Mali analiz ve finansal planlama uzmansın: Bilanço, gelir tablosu, nakit akış, maliyet muhasebesi.
Kritik Metrikler: Brüt Kâr Marjı, FAVÖK, Nakit Çevrim Süresi (Stok+Alacak-Borç gün), Birim Maliyet, ROI.
Maliyet kırılımını tablo formatında sun: Hammadde, İşçilik, Enerji, Amortisman, Diğer GÜG.""",

    "Yönetim": """## Üst Yönetim Uzmanlığı
C-level yöneticilere hitap ediyorsun. Kısa, etkili, bullet-point odaklı.
Her bulguyu rakamla destekle. "So what?" sorusuna cevap ver — iş etkisini belirt.
Format: Durum [Kritik/Dikkat/Normal/İyi] → Ana Bulgu → Etki (₺/%) → Tavsiye.""",

    "İnsan Kaynakları": """## İK Uzmanlığı
İşe alım, performans, bordro, eğitim, iş hukuku (4857) uzmansın.
Metrikler: Devir Oranı (hedef <%15), İşe Alım Süresi, Eğitim Saat/Kişi, Devamsızlık.
KVKK uyarısı: Kişisel veri paylaşma.""",

    "Satış": """## Satış Uzmanlığı
Satış hunisi, müşteri segmentasyonu, fiyatlandırma, pazar analizi uzmansın.
Metrikler: Satış Büyüme %, Müşteri Başına Gelir, Dönüşüm Oranı, Müşteri Tutma Oranı.
Tablo formatında sun: Müşteri/Bölge, Bu Ay, Geçen Ay, Değişim, Hedef, Gerçekleşme.""",

    "IT": """## IT Uzmanlığı
Sunucu, network, veritabanı, siber güvenlik, DevOps uzmansın.
Metrikler: Uptime (hedef >%99.9), MTTR (<4 saat), MTBF, Yedekleme Başarı Oranı.
Güvenlik: Şifre, API key, connection string ASLA paylaşma.""",
}


# ══════════════════════════════════════════════════════════════
# 4. MOD PROMPT'LARI — DERİN
# ══════════════════════════════════════════════════════════════

MODE_PROMPTS = {
    "Sohbet": "Kısa ve samimi cevap ver. 1-2 cümle yeterli. Doğal konuş, madde/başlık/liste KULLANMA.",

    "Bilgi": """KISA ve NET cevap ver. Maksimum 2-4 cümle. Liste/başlık/madde KULLANMA. Soruyu doğrudan yanıtla, gereksiz açıklama ekleme.""",

    "Analiz": """Detaylı, veri odaklı analiz yap:
1. Veri doğrulama ve KPI sınıflandırma (hedef, sektör ortalaması, geçmiş karşılaştırma)
2. Risk skorlama (olasılık × etki) ve kök neden hipotezi
3. Senaryo: 🟢 Best / 🟡 Expected / 🔴 Worst Case
4. Stratejik öneri: Kısa vade (1-4 hafta) / Orta vade (1-3 ay) / Uzun vade (3-12 ay)
Somut sayılarla konuş. Bilmediğini uydurma, varsayım yaptığını belirt. Tablo formatı kullan.""",

    "Özet": "Maksimum 5-7 cümle ile özetle: Ana konu → Temel bulgular → Sonuç/tavsiye.",

    "Öneri": """Somut, uygulanabilir öneriler sun. Her öneri için: Ne, Neden (₺/%/gün), Nasıl, Kim, Ne zaman.
ROI hesapla: (Getiri - Maliyet) / Maliyet × 100. Önerileri etki/kolaylık matrisine göre önceliklendir.""",

    "Rapor": """Profesyonel rapor formatı:
1. Yönetici Özeti: Durum + Ana bulgu + Etki
2. Bulgular ve Veriler (tablo)
3. Risk Değerlendirmesi
4. Öneriler ve Aksiyon Planı (kısa/orta/uzun vade)""",

    "Acil": """⚠️ ACİL DURUM — Tehlike seviyesini belirt (🔴/🟡/🟢). Hemen yapılacak aksiyonları numaralı listele.
İletişim zincirini belirt. Güvenlik önlemlerini hatırlat. Kısa, net, aksiyon odaklı.""",

    "Beyin Fırtınası": "Yaratıcı düşün. En az 8-10 fikir üret. Grupla: Kısa/Uzun vadeli/Radikal. Uygulanabilirlik puanı ver (1-5).",
}


# ══════════════════════════════════════════════════════════════
# 5. KPI YORUMLAMA KALIPLARI
# ══════════════════════════════════════════════════════════════

KPI_INTERPRETATION_TEMPLATES = {
    "fire_orani": {
        "metric": "Fire Oranı (%)",
        "formula": "(Fire Miktar / Toplam Üretim) × 100",
        "benchmarks": {"iyi": 2.0, "normal": 5.0, "kritik": 8.0},
        "template": "Fire oranı %{value} → {seviye} seviyede (sektör ort: %3-4). {yorum}",
        "actions": {
            "iyi": "Mevcut kalite süreçleri etkin. Sürdür ve benchmark olarak paylaş.",
            "normal": "İyileştirme fırsatı var. Pareto analizi ile en büyük fire kaynağını belirle.",
            "kritik": "ACİL: Kalite kontrol süreçlerini gözden geçir. Kök neden analizi (5 Neden) uygula.",
        }
    },
    "oee": {
        "metric": "OEE (%)",
        "formula": "Kullanılabilirlik × Performans × Kalite",
        "benchmarks": {"dünya_sinifi": 85.0, "iyi": 70.0, "orta": 55.0},
        "template": "OEE %{value} → {seviye}. Darboğaz: {darbogaz}. {yorum}",
    },
    "brut_kar_marji": {
        "metric": "Brüt Kâr Marjı (%)",
        "formula": "(Satışlar - SMM) / Satışlar × 100",
        "benchmarks": {"iyi": 25.0, "normal": 15.0, "kritik": 8.0},
        "template": "Brüt kâr marjı %{value} → {seviye}. {yorum}",
    },
    "personel_devir": {
        "metric": "Personel Devir Oranı (%)",
        "formula": "(Ayrılan / Ort. Çalışan) × 100",
        "benchmarks": {"iyi": 10.0, "normal": 20.0, "kritik": 30.0},
        "template": "Devir oranı %{value} → {seviye}. {yorum}",
    },
    "nakit_cevrim": {
        "metric": "Nakit Çevrim Süresi (gün)",
        "formula": "Stok Gün + Alacak Gün - Borç Gün",
        "benchmarks": {"iyi": 30, "normal": 60, "kritik": 90},
        "template": "Nakit çevrim {value} gün → {seviye}. {yorum}",
    },
}


def interpret_kpi(kpi_name: str, value: float) -> str:
    """KPI değerini yorumla ve template'e göre metin üret."""
    template_data = KPI_INTERPRETATION_TEMPLATES.get(kpi_name)
    if not template_data:
        return f"{kpi_name}: {value}"
    
    benchmarks = template_data["benchmarks"]
    thresholds = sorted(benchmarks.items(), key=lambda x: x[1])
    
    seviye = "kritik"
    for level, threshold in thresholds:
        if value <= threshold:
            seviye = level
            break
    
    actions = template_data.get("actions", {})
    yorum = actions.get(seviye, "Detaylı analiz gerekiyor.")
    
    return template_data["template"].format(
        value=round(value, 1), seviye=seviye, yorum=yorum,
        darbogaz="(analiz gerekli)", 
    )


# ══════════════════════════════════════════════════════════════
# 6. RİSK ANALİZİ DİLİ
# ══════════════════════════════════════════════════════════════

RISK_ANALYSIS_PROMPT = """
## Risk Değerlendirme Çerçevesi

Her risk için şu tabloyu doldur:

| Risk | Olasılık (1-5) | Etki (1-5) | Risk Skoru | Öncelik | Aksiyon |
|------|---------------|-----------|-----------|---------|---------|
| [Risk adı] | [1=Çok düşük, 5=Çok yüksek] | [1=Önemsiz, 5=Felaket] | OxE | [Kritik/Yüksek/Orta/Düşük] | [Somut önlem] |

Risk Skor Yorumu:
- 20-25: 🔴 Kritik — Hemen aksiyon al
- 12-19: 🟠 Yüksek — 1 hafta içinde önlem
- 6-11: 🟡 Orta — Planlı iyileştirme
- 1-5: 🟢 Düşük — İzle ve takip et

Risk Kategorileri:
- **Operasyonel**: Makine arızası, hammadde tedarik, kalite sapması
- **Finansal**: Kur riski, alacak riski, nakit sıkışıklığı
- **İnsan**: Personel devri, iş kazası, yetenek kaybı
- **Stratejik**: Pazar değişimi, rekabet, teknoloji değişimi
- **Uyum**: Yasal düzenleme, çevre, iş güvenliği
"""


# ══════════════════════════════════════════════════════════════
# 7. SEZONLUK TREND DİLİ
# ══════════════════════════════════════════════════════════════

SEASONAL_PROMPT = """
## Sezonluk Trend Analizi Çerçevesi

Tekstil sektöründe mevsimsel döngüler:
- **Q1 (Ocak-Mart)**: Yaz koleksiyonu üretimi, ihracat yoğun dönem
- **Q2 (Nisan-Haziran)**: Geçiş dönemi, kış öncesi sipariş toplama
- **Q3 (Temmuz-Eylül)**: Kış koleksiyonu üretimi, yurtiçi pik
- **Q4 (Ekim-Aralık)**: Sezon sonu, stok eritme, yılbaşı hazırlık

Trend yorumlarken:
1. Mevsimsel etkiyi ayır (yıllık tekrar eden pattern)
2. Gerçek trendi belirle (mevsimsel düzeltilmiş)
3. Geçen yılın aynı dönemiyle karşılaştır (YoY)
4. Kümülatif performansı değerlendir (YTD)
"""


# ══════════════════════════════════════════════════════════════
# 8. STRUCTURED OUTPUT YÖNERGE
# ══════════════════════════════════════════════════════════════

STRUCTURED_OUTPUT_PROMPT = """
## Yapılandırılmış Çıktı Kuralları
Aşağıdaki durumlarda JSON formatında yanıt ver:
- Tablo verisi istendiğinde
- Karşılaştırma yapıldığında
- KPI raporu istendiğinde
- Liste/sıralama istendiğinde

JSON çıktı formatı:
```json
{
  "summary": "Tek cümle özet",
  "data": [...],
  "insights": ["Bulgu 1", "Bulgu 2"],
  "recommendations": ["Öneri 1", "Öneri 2"],
  "risk_level": "low|medium|high|critical",
  "confidence": 0.85
}
```
Eğer kullanıcı açıkça JSON istemiyorsa, normal metin formatında yaz.
"""


# ══════════════════════════════════════════════════════════════
# 9. PROMPT OLUŞTURMA FONKSİYONLARI
# ══════════════════════════════════════════════════════════════

def build_prompt(question: str, context: dict) -> tuple[str, str]:
    """System ve user prompt oluşturur — v5.9.0 optimize edilmiş.
    
    Kurallar:
    - Temel: SYSTEM_PROMPT + MODE_PROMPT + DEPARTMENT_PROMPT (her zaman)
    - Ek olarak EN FAZLA 1 adet uzmanlık şablonu seçilir (token tasarrufu)
    - Sohbet modu minimum prompt alır
    """
    department = context.get("dept", "Genel")
    mode = context.get("mode", "Sohbet")
    intent = context.get("intent", "sohbet")
    risk = context.get("risk", "Düşük")
    
    safe_question = sanitize_input(question)
    
    # Temel system prompt
    system = SYSTEM_PROMPT
    
    # Mod talimatı
    mode_prompt = MODE_PROMPTS.get(mode, "")
    if mode_prompt:
        system += f"\n\n{mode_prompt}" if mode != "Sohbet" else f"\n{mode_prompt}"
    
    # Departman uzmanlığı (iş/analiz sorularında)
    if department != "Genel" and intent != "sohbet":
        dept_prompt = DEPARTMENT_PROMPTS.get(department, "")
        if dept_prompt:
            system += f"\n\n{dept_prompt}"
    
    # Risk durumu yüksekse acil mod ekle
    if risk in ("Yüksek", "Kritik"):
        system += f"\n\n⚠️ Risk Seviyesi: {risk}. Acil ve net yanıt ver."
    
    # ── EN FAZLA 1 uzmanlık şablonu seç (v5.9.0) ──
    # Öncelik: Risk > Sezonluk > CoT (birbirleriyle karışmasın)
    # v5.10.4: Bilgi modunda CoT şablonu EKLENMEZ — kısa yanıt öncelikli
    if mode not in ("Sohbet", "Bilgi") and intent not in ("sohbet", "bilgi"):
        if _needs_risk_analysis(question):
            system += f"\n\n{RISK_ANALYSIS_PROMPT}"
        elif _needs_seasonal_analysis(question):
            system += f"\n\n{SEASONAL_PROMPT}"
        else:
            cot = get_cot_template(question, mode)
            if cot:
                system += f"\n\n{cot}"
    
    return system, safe_question


def build_rag_prompt(question: str, context: dict, documents: list = None) -> tuple[str, str]:
    """RAG dokümanları ile gelişmiş prompt oluşturur."""
    system, user = build_prompt(question, context)
    
    if documents:
        # Gerçek dokümanları web_learned'den ayır ve önceliklendir
        real_docs = []
        web_docs = []
        chat_docs = []
        for doc in documents[:8]:
            source = doc.get('source', '')
            doc_type = doc.get('type', '')
            if 'web_search' in source or doc_type == 'web_learned':
                web_docs.append(doc)
            elif doc_type == 'chat_learned':
                chat_docs.append(doc)
            else:
                real_docs.append(doc)
        
        # Önce gerçek dokümanlar, sonra chat öğrenimleri, son olarak web kaynakları
        sorted_docs = real_docs + chat_docs + web_docs
        
        doc_text = "\n\n## 📚 İlgili Dokümanlar (Bilgi Tabanı)\n"
        doc_text += "AŞAĞIDAKİ DOKÜMANLAR BİLGİ TABANINDAN GETİRİLDİ. BU BİLGİLERİ KULLANARAK YANIT VER.\n"
        for i, doc in enumerate(sorted_docs[:5], 1):
            source = doc.get('source', 'Bilinmeyen')
            content = sanitize_document_content(doc.get('content', '')[:1500])
            relevance = doc.get('relevance', 0)
            doc_type = doc.get('type', 'doküman')
            label = "📄 Doküman" if doc_type not in ('chat_learned', 'web_learned') else ("💬 Chat Bilgisi" if doc_type == 'chat_learned' else "🌐 Web")
            doc_text += f"\n### {label} {i}: {source} (alaka: {relevance:.2f})\n{content}\n"
        doc_text += """
### ⚠️ Doküman Kuralları:
1. Dokümanlardan DOĞRUDAN ALINTI yaparak yanıt ver, kaynağı belirt
2. Doküman bilgisi genel bilginle çelişiyorsa KESİNLİKLE DOKÜMANI tercih et
3. Dokümanlarda yoksa açıkça belirt: "Bilgi tabanımda bu konuda veri bulunamadı."
"""
        system += doc_text
    
    return system, user


def build_tool_prompt(question: str, context: dict, available_tools: list = None) -> tuple[str, str]:
    """Tool calling destekli prompt oluşturur."""
    system, user = build_prompt(question, context)
    
    if available_tools:
        tools_desc = "\n\n## 🔧 Kullanılabilir Araçlar\n"
        tools_desc += "Aşağıdaki araçları kullanarak yanıt verebilirsin:\n\n"
        for tool in available_tools:
            tools_desc += f"- **{tool['name']}**: {tool['description']}\n"
            if tool.get('parameters'):
                tools_desc += f"  Parametreler: {tool['parameters']}\n"
        tools_desc += """
### Araç Kullanım Formatı:
Bir araç kullanmak istediğinde şu JSON formatını kullan:
```json
{"tool": "araç_adı", "params": {"param1": "değer1"}}
```
Araç sonucunu aldıktan sonra kullanıcıya yorumla."""
        system += tools_desc
    
    return system, user


# ── Yardımcı fonksiyonlar ──

# ══════════════════════════════════════════════════════════════
# 10. CHAIN-OF-THOUGHT REASONING TEMPLATES (v4.3.0)
# ══════════════════════════════════════════════════════════════

REASONING_TEMPLATES = {
    "deductive": """## Tümdengelimli Akıl Yürütme (Deductive)
Şu adımları takip et:
1. **Genel İlke**: Konuyla ilgili bilinen kural/ilke/standart nedir?
2. **Spesifik Durum**: Eldeki veri bu ilkeye nasıl uyuyor?
3. **Sonuç**: İlke + veri → kesin çıkarım nedir?
4. **Güven**: Bu sonuçtan ne kadar eminsin? Varsayımların neler?""",

    "comparative": """## Karşılaştırmalı Akıl Yürütme (Comparative)
Şu adımları takip et:
1. **Kıyaslama Eksenleri**: Hangi boyutlarda karşılaştırıyorsun? (maliyet, süre, kalite, risk)
2. **Veri Tablosu**: Her alternatif için her eksendeki değeri belirt
3. **Ağırlıklı Puanlama**: İş önceliğine göre ağırlıklandır
4. **Tercih ve Gerekçe**: En iyi seçenek hangisi, neden?""",

    "causal": """## Neden-Sonuç Akıl Yürütme (Causal)
Şu adımları takip et:
1. **Gözlem**: Ne gözlemleniyor? (veri, trend, anomali)
2. **Olası Nedenler**: 5 Neden Tekniği — neden bu oldu? (min 3 hipotez)
3. **Neden Doğrulama**: Her hipotezi destekleyen/çürüten veri var mı?
4. **Kök Neden**: En güçlü hipotez hangisi?
5. **Etki Zinciri**: Bu kök neden başka neleri etkiliyor?
6. **Çözüm**: Kök nedene yönelik somut aksiyon öner""",

    "risk_based": """## Risk Bazlı Akıl Yürütme
Şu adımları takip et:
1. **Riskleri Tanımla**: Operasyonel, finansal, stratejik riskler neler?
2. **Olasılık × Etki**: Her risk için skor hesapla (1-5 × 1-5)
3. **Senaryo Analizi**: 🟢 Best / 🟡 Expected / 🔴 Worst Case
4. **Önlem Planı**: Her yüksek riske karşı somut aksiyon belirt
5. **Artık Risk**: Önlemler sonrası kalan risk seviyesi nedir?""",

    "financial": """## Finansal Akıl Yürütme
Şu adımları takip et:
1. **Maliyet Kırılımı**: Doğrudan + dolaylı maliyetleri ₺ cinsinden listele
2. **Getiri Tahmini**: Beklenen fayda/tasarruf/gelir artışı ₺
3. **ROI Hesaplama**: (Getiri - Maliyet) / Maliyet × 100
4. **Geri Ödeme Süresi**: Yatırım ne zaman kendini amorti eder?
5. **Hassasiyet Analizi**: ±%20 değişimde ROI ne olur?
6. **Karar**: Yatırıma değer mi, alternatifleri var mı?""",
}

# Mod-bazlı otomatik CoT şablon seçimi
COT_MODE_MAPPING = {
    "Analiz": ["deductive", "causal"],
    "Rapor": ["deductive", "comparative"],
    "Öneri": ["financial", "risk_based"],
    "Acil": ["causal", "risk_based"],
    "Beyin Fırtınası": ["comparative"],
}


def get_cot_template(question: str, mode: str) -> str:
    """Soru ve moda göre en uygun CoT şablonunu seç."""
    q = question.lower()
    
    # Soru bazlı override
    if re.search(r'karşılaştır|kıyasla|fark|versus|vs', q):
        return REASONING_TEMPLATES["comparative"]
    if re.search(r'neden|sebep|kök\s*neden|arıza|sorun|problem', q):
        return REASONING_TEMPLATES["causal"]
    if re.search(r'maliyet|bütçe|yatırım|roi|getiri|tasarruf', q):
        return REASONING_TEMPLATES["financial"]
    if re.search(r'risk|tehlike|tehdit|olası|senaryo', q):
        return REASONING_TEMPLATES["risk_based"]
    
    # Mod bazlı default
    template_keys = COT_MODE_MAPPING.get(mode, [])
    if template_keys:
        return REASONING_TEMPLATES[template_keys[0]]
    
    return ""


# ══════════════════════════════════════════════════════════════
# 11. ACTION PLAN TEMPLATE — 5W1H (v4.3.0)
# ══════════════════════════════════════════════════════════════

ACTION_PLAN_TEMPLATE = """## Aksiyon Planı Formatı (5W1H)
Her öneri için şu yapıyı kullan:

| Soru | Detay |
|------|-------|
| **Ne (What)** | Yapılacak iş/proje |
| **Neden (Why)** | Beklenen fayda (₺, %, gün cinsinden) |
| **Kim (Who)** | Sorumlu departman/pozisyon |
| **Ne zaman (When)** | Başlangıç tarihi ve süre |
| **Nerede (Where)** | Etkilenen alan/tesis/hat |
| **Nasıl (How)** | Uygulama adımları (numaralı) |

### ROI Hesaplama Şablonu:
- **Yatırım Maliyeti**: ₺X (donanım + yazılım + işçilik)
- **Yıllık Tasarruf/Getiri**: ₺Y
- **ROI**: (Y - X) / X × 100 = %Z
- **Geri Ödeme Süresi**: X / (Y/12) = N ay
"""

# ══════════════════════════════════════════════════════════════
# 12. MULTI-PERSPECTIVE TEMPLATE (v4.3.0)
# ══════════════════════════════════════════════════════════════

MULTI_PERSPECTIVE_TEMPLATE = """## Çoklu Perspektif Değerlendirmesi
Bu kararı farklı bakış açılarından değerlendir:

### 💰 CFO Perspektifi (Finansal)
- Maliyet etkisi, ROI, nakit akış etkisi, bütçe uyumu

### ⚙️ COO Perspektifi (Operasyonel)
- Üretim etkisi, kapasite, tedarik zinciri, kalite etkisi

### 🛡️ CRO Perspektifi (Risk)
- Operasyonel risk, finansal risk, uyum riski, itibar riski

### 📊 Sentez
- Tüm perspektifleri tartarak nihai değerlendirme ve tavsiye sun
"""


def _needs_risk_analysis(question: str) -> bool:
    q = question.lower()
    return bool(re.search(r'risk|tehlike|tehdit|zafiyet|etki\s*analiz|olasılık', q))


def _needs_seasonal_analysis(question: str) -> bool:
    q = question.lower()
    return bool(re.search(r'sezon|mevsim|aylık\s*trend|çeyreklik|yıllık\s*karşılaştır|q[1-4]|quarter', q))
