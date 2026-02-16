"""Rapor Şablon Sistemi (v4.4.0)

Departmana özel rapor şablonları ile tutarlı, yapılandırılmış çıktı üretir.
Şablonlar LLM'e gönderilip doldurulabilir veya doğrudan veri ile render edilir.

Desteklenen şablonlar:
- Üretim performans raporu
- Maliyet analiz raporu
- Kalite kontrol raporu
- Genel yönetim özeti
- KPI scorecard
"""

import re
from typing import Optional, Dict, Any, List
from datetime import datetime
import structlog

logger = structlog.get_logger()

# ═══════════════════════════════════════════════════════════════
# RAPOR ŞABLONLARI
# ═══════════════════════════════════════════════════════════════

REPORT_TEMPLATES = {
    "uretim_performans": {
        "title": "Üretim Performans Raporu",
        "department": "Üretim",
        "sections": [
            {"name": "ozet", "label": "Yönetici Özeti", "required": True},
            {"name": "kpi_tablosu", "label": "Temel KPI'lar",
             "format": "table",
             "columns": ["KPI", "Hedef", "Gerçekleşen", "Fark (%)", "Durum"]},
            {"name": "uretim_verileri", "label": "Üretim Verileri",
             "format": "table",
             "columns": ["Hat/Tezgah", "Üretim (mt/adet)", "Verimlilik (%)", "Duruş (saat)"]},
            {"name": "fire_analizi", "label": "Fire/Hurda Analizi",
             "format": "text"},
            {"name": "sorunlar", "label": "Sorunlar ve Aksiyon Önerileri",
             "format": "list"},
            {"name": "sonuc", "label": "Sonuç ve Öneriler", "required": True},
        ],
        "prompt_hint": (
            "Bu bir üretim performans raporudur. Sayısal veriler (üretim miktarı, "
            "verimlilik oranı, fire oranı, duruş süreleri) tablo formatında olmalıdır. "
            "Her KPI için hedef ve gerçekleşen değer karşılaştırılmalıdır."
        ),
    },
    
    "maliyet_analiz": {
        "title": "Maliyet Analiz Raporu",
        "department": "Finans",
        "sections": [
            {"name": "ozet", "label": "Yönetici Özeti", "required": True},
            {"name": "maliyet_dagilimi", "label": "Maliyet Dağılımı",
             "format": "table",
             "columns": ["Kalem", "Tutar (TL)", "Oran (%)", "Önceki Dönem", "Değişim (%)"]},
            {"name": "birim_maliyet", "label": "Birim Maliyet Analizi",
             "format": "table",
             "columns": ["Ürün/Hizmet", "Birim Maliyet", "Hedef", "Sapma"]},
            {"name": "trend", "label": "Trend Analizi",
             "format": "text"},
            {"name": "tasarruf", "label": "Tasarruf Fırsatları",
             "format": "list"},
            {"name": "sonuc", "label": "Sonuç ve Öneriler", "required": True},
        ],
        "prompt_hint": (
            "Bu bir maliyet analiz raporudur. Tüm maliyetler TL cinsinden, "
            "dönemsel karşılaştırma ile verilmelidir. Tasarruf fırsatları "
            "beklenen tasarruf tutarı ile belirtilmelidir."
        ),
    },
    
    "kalite_kontrol": {
        "title": "Kalite Kontrol Raporu",
        "department": "Üretim",
        "sections": [
            {"name": "ozet", "label": "Genel Değerlendirme", "required": True},
            {"name": "test_sonuclari", "label": "Test Sonuçları",
             "format": "table",
             "columns": ["Test", "Standart", "Sonuç", "Durum (✓/✗)"]},
            {"name": "hata_dagitimi", "label": "Hata Dağılımı",
             "format": "table",
             "columns": ["Hata Tipi", "Adet", "Oran (%)", "Seviye"]},
            {"name": "kök_neden", "label": "Kök Neden Analizi",
             "format": "text"},
            {"name": "aksiyonlar", "label": "Düzeltici Aksiyonlar",
             "format": "list"},
            {"name": "sonuc", "label": "Sonuç", "required": True},
        ],
        "prompt_hint": (
            "Bu bir kalite kontrol raporudur. Her test sonucu standart değer ile "
            "karşılaştırılmalı, uygun/uygunsuz belirtilmelidir. Hatalar kök neden "
            "analizi ile değerlendirilmelidir."
        ),
    },
    
    "yonetim_ozeti": {
        "title": "Yönetim Özet Raporu",
        "department": "Yönetim",
        "sections": [
            {"name": "ozet", "label": "Dönem Özeti", "required": True},
            {"name": "kpi_dashboard", "label": "KPI Dashboard",
             "format": "table",
             "columns": ["Departman", "KPI", "Değer", "Hedef", "Durum"]},
            {"name": "onemli_gelismeler", "label": "Önemli Gelişmeler",
             "format": "list"},
            {"name": "riskler", "label": "Riskler ve Sorunlar",
             "format": "list"},
            {"name": "stratejik_oneriler", "label": "Stratejik Öneriler",
             "format": "text"},
            {"name": "sonuc", "label": "Sonuç", "required": True},
        ],
        "prompt_hint": (
            "Bu bir yönetim özet raporudur. Tüm departmanların temel KPI'ları "
            "tek tabloda özetlenmelidir. Stratejik öneriler somut ve uygulanabilir olmalıdır."
        ),
    },
    
    "kpi_scorecard": {
        "title": "KPI Scorecard",
        "department": "Genel",
        "sections": [
            {"name": "scorecard", "label": "KPI Tablosu",
             "format": "table",
             "columns": ["KPI", "Birim", "Hedef", "Gerçekleşen", "Skor", "Trend"]},
            {"name": "basarili", "label": "Başarılı KPI'lar",
             "format": "list"},
            {"name": "kritik", "label": "Kritik KPI'lar (Hedefin Altında)",
             "format": "list"},
            {"name": "aksiyon", "label": "Aksiyon Planı",
             "format": "text"},
        ],
        "prompt_hint": (
            "Bu bir KPI scorecard'dır. Her KPI %100 üzerinden skorlanmalı, "
            "trend ok işaretleri (↑↓→) ile belirtilmelidir."
        ),
    },
}


def get_template(template_name: str) -> Optional[Dict]:
    """Şablon bilgisini döndür."""
    return REPORT_TEMPLATES.get(template_name)


def list_templates(department: str = None) -> List[Dict]:
    """Kullanılabilir şablonları listele."""
    templates = []
    for key, tmpl in REPORT_TEMPLATES.items():
        if department and tmpl["department"] not in (department, "Genel"):
            continue
        templates.append({
            "id": key,
            "title": tmpl["title"],
            "department": tmpl["department"],
            "sections": len(tmpl["sections"]),
        })
    return templates


def render_template_markdown(template_name: str, data: Dict[str, Any] = None) -> str:
    """Şablonu Markdown formatında render et.
    
    Args:
        template_name: Şablon ID'si
        data: Bölüm verileri {"section_name": "içerik" veya tablo verisi}
    
    Returns:
        Markdown formatında rapor stringi
    """
    tmpl = REPORT_TEMPLATES.get(template_name)
    if not tmpl:
        return f"⚠️ Şablon bulunamadı: {template_name}"
    
    lines = []
    lines.append(f"# {tmpl['title']}")
    lines.append(f"*Tarih: {datetime.now().strftime('%d.%m.%Y')} | Departman: {tmpl['department']}*")
    lines.append("")
    
    data = data or {}
    
    for section in tmpl["sections"]:
        section_name = section["name"]
        section_label = section["label"]
        section_format = section.get("format", "text")
        content = data.get(section_name, "")
        
        lines.append(f"## {section_label}")
        lines.append("")
        
        if not content:
            if section.get("required"):
                lines.append("*[Bu bölüm doldurulmalıdır]*")
            else:
                lines.append("*[Veri bekleniyor]*")
            lines.append("")
            continue
        
        if section_format == "table" and isinstance(content, list):
            columns = section.get("columns", [])
            if columns:
                lines.append("| " + " | ".join(columns) + " |")
                lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
            for row in content:
                if isinstance(row, dict):
                    cells = [str(row.get(col, "")) for col in columns]
                elif isinstance(row, (list, tuple)):
                    cells = [str(c) for c in row]
                else:
                    cells = [str(row)]
                lines.append("| " + " | ".join(cells) + " |")
            lines.append("")
            
        elif section_format == "list" and isinstance(content, list):
            for item in content:
                lines.append(f"- {item}")
            lines.append("")
            
        else:
            lines.append(str(content))
            lines.append("")
    
    lines.append("---")
    lines.append(f"*CompanyAI Otomatik Rapor | v4.4.0*")
    
    return "\n".join(lines)


def build_report_prompt(
    template_name: str,
    question: str,
    context: str = "",
) -> str:
    """Şablona göre LLM'e gönderilecek rapor prompt'u oluştur.
    
    LLM'den şablondaki bölümleri doldurmasını ister.
    """
    tmpl = REPORT_TEMPLATES.get(template_name)
    if not tmpl:
        return question
    
    sections_desc = []
    for section in tmpl["sections"]:
        fmt = section.get("format", "text")
        if fmt == "table":
            cols = section.get("columns", [])
            sections_desc.append(
                f"### {section['label']}\n"
                f"Tablo formatında: {' | '.join(cols)}"
            )
        elif fmt == "list":
            sections_desc.append(
                f"### {section['label']}\n"
                f"Madde listesi formatında"
            )
        else:
            sections_desc.append(
                f"### {section['label']}\n"
                f"Paragraf formatında"
            )
    
    sections_text = "\n\n".join(sections_desc)
    
    prompt = f"""Aşağıdaki rapor şablonuna göre detaylı bir rapor hazırla.

**Rapor Şablonu:** {tmpl['title']}
**Önemli:** {tmpl['prompt_hint']}

**Bölümler (her bölümü ayrı başlıkla yaz):**

{sections_text}

**Kullanıcı Sorusu:** {question}
"""
    
    if context:
        prompt += f"\n**Mevcut Veri/Bağlam:**\n{context[:2000]}"
    
    return prompt


def detect_report_template(question: str, department: str = "Genel") -> Optional[str]:
    """Sorudan uygun rapor şablonunu otomatik algıla.
    
    Returns:
        Şablon ID'si veya None
    """
    q = question.lower()
    
    if re.search(r'(üretim|verimlilik|tezgah|hat)\s*(performans|rapor|analiz)', q):
        return "uretim_performans"
    if re.search(r'(maliyet|gider|masraf)\s*(analiz|rapor|dağılım)', q):
        return "maliyet_analiz"
    if re.search(r'(kalite|hata|fire|kusur|test)\s*(kontrol|rapor|analiz)', q):
        return "kalite_kontrol"
    if re.search(r'(yönetim|genel|dönem)\s*(özet|rapor|dashboard)', q):
        return "yonetim_ozeti"
    if re.search(r'(kpi|scorecard|puan\s*kartı|performans\s*kart)', q):
        return "kpi_scorecard"
    
    # Departmana göre varsayılan
    dept_defaults = {
        "Üretim": "uretim_performans",
        "Finans": "maliyet_analiz",
        "Yönetim": "yonetim_ozeti",
    }
    
    if re.search(r'(rapor|analiz|özet)\s*(hazırla|oluştur|yap|çıkar)', q):
        return dept_defaults.get(department)
    
    return None
