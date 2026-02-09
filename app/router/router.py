"""Akıllı Soru Yönlendirici - Departman ve Mod Belirleme"""

from typing import Dict, Any
import re


# Anahtar kelime -> Departman eşleştirmeleri
DEPARTMENT_KEYWORDS = {
    "Üretim": [
        "üretim", "fire", "yangın", "makine", "arıza", "fabrika", "hat", 
        "kalite", "hammadde", "stok", "bakım", "onarım", "vardiya",
    ],
    "Finans": [
        "nakit", "kâr", "kar", "zarar", "bütçe", "maliyet", "fatura", 
        "ödeme", "tahsilat", "kredi", "borç", "alacak", "muhasebe",
    ],
    "İnsan Kaynakları": [
        "personel", "çalışan", "işe alım", "maaş", "izin", "eğitim",
        "performans", "özlük", "bordro", "işten çıkış",
    ],
    "Satış": [
        "müşteri", "satış", "sipariş", "teklif", "fiyat", "kampanya",
        "pazar", "ihracat", "bayi", "distribütör",
    ],
    "IT": [
        "yazılım", "sistem", "sunucu", "network", "güvenlik", "yedekleme",
        "erişim", "şifre", "uygulama", "database",
    ],
}

# Risk seviyesi belirleme
RISK_KEYWORDS = {
    "Yüksek": ["acil", "kritik", "yangın", "kaza", "tehlike", "ivedi", "fire"],
    "Orta": ["sorun", "problem", "arıza", "gecikme", "risk", "eksik"],
    "Düşük": ["bilgi", "soru", "nasıl", "nedir", "açıklama", "rapor"],
}

# Mod belirleme
MODE_KEYWORDS = {
    "Acil Müdahale": ["acil", "hemen", "ivedi", "yangın", "kaza"],
    "Analiz": ["analiz", "rapor", "değerlendirme", "karşılaştırma", "trend"],
    "Yönetim": ["onay", "karar", "strateji", "planlama", "bütçe"],
    "Operasyon": ["işlem", "süreç", "günlük", "rutin", "takip"],
}


def decide(question: str) -> Dict[str, Any]:
    """
    Soruyu analiz ederek departman, mod ve risk seviyesi belirler.
    
    Args:
        question: Kullanıcı sorusu
    
    Returns:
        dict: {"dept": str, "mode": str, "risk": str}
    """
    q = question.lower()
    
    # Departman belirleme
    department = "Yönetim"  # Varsayılan
    max_matches = 0
    
    for dept, keywords in DEPARTMENT_KEYWORDS.items():
        matches = sum(1 for kw in keywords if kw in q)
        if matches > max_matches:
            max_matches = matches
            department = dept
    
    # Risk belirleme
    risk = "Düşük"  # Varsayılan
    for risk_level, keywords in RISK_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            risk = risk_level
            break
    
    # Mod belirleme
    mode = "Analiz"  # Varsayılan
    for mode_type, keywords in MODE_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            mode = mode_type
            break
    
    return {
        "dept": department,
        "mode": mode,
        "risk": risk,
    }


def get_department_info(department: str) -> Dict[str, Any]:
    """Departman hakkında bilgi döner"""
    info = {
        "Üretim": {
            "description": "Üretim ve fabrika operasyonları",
            "priority_contact": "Üretim Müdürü",
            "escalation_time_minutes": 15,
        },
        "Finans": {
            "description": "Mali işler ve muhasebe",
            "priority_contact": "Finans Müdürü",
            "escalation_time_minutes": 30,
        },
        "İnsan Kaynakları": {
            "description": "Personel ve özlük işleri",
            "priority_contact": "İK Müdürü",
            "escalation_time_minutes": 60,
        },
        "Satış": {
            "description": "Satış ve müşteri ilişkileri",
            "priority_contact": "Satış Müdürü",
            "escalation_time_minutes": 30,
        },
        "IT": {
            "description": "Bilgi teknolojileri",
            "priority_contact": "IT Müdürü",
            "escalation_time_minutes": 20,
        },
        "Yönetim": {
            "description": "Genel yönetim ve strateji",
            "priority_contact": "Genel Müdür",
            "escalation_time_minutes": 60,
        },
    }
    return info.get(department, info["Yönetim"])