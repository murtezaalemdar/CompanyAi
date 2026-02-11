"""Doğal Dil → SQL Dönüştürücü & Otomatik Feature Engineering

- Doğal dil sorgusu → SQL (PostgreSQL)
- Tablo şema algılama
- Feature oluşturma (lag, rolling, one-hot, binning, interaction)
- Otomatik kolon analizi ve önerisi
"""

import re
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional
import structlog

logger = structlog.get_logger(__name__)


# ══════════════════════════════════════════════════════════════
# 1. SQL GENERATOR
# ══════════════════════════════════════════════════════════════

# Yaygın tablo şemaları (CompanyAi PostgreSQL)
KNOWN_SCHEMAS = {
    "uretim": {
        "columns": ["id", "tarih", "vardiya", "tezgah_no", "urun", "miktar", "fire_miktar",
                     "durus_dakika", "hata_tipi", "operator_id"],
        "description": "Günlük üretim kayıtları",
    },
    "kalite": {
        "columns": ["id", "tarih", "parti_no", "urun", "hata_tipi", "hata_sayisi", "denetci_id",
                     "karar", "not_"],
        "description": "Kalite kontrol kayıtları",
    },
    "satis": {
        "columns": ["id", "tarih", "musteri", "urun", "miktar", "birim_fiyat", "tutar",
                     "para_birimi", "durum"],
        "description": "Satış siparişleri",
    },
    "stok": {
        "columns": ["id", "urun_kodu", "urun_adi", "miktar", "birim", "depo", "son_hareket_tarih"],
        "description": "Stok durumu",
    },
    "personel": {
        "columns": ["id", "sicil_no", "ad_soyad", "departman", "pozisyon", "ise_baslama",
                     "maas", "durum"],
        "description": "Personel bilgileri",
    },
    "makine": {
        "columns": ["id", "makine_no", "makine_tipi", "durum", "son_bakim_tarih",
                     "sonraki_bakim_tarih", "toplam_calisma_saat"],
        "description": "Makine/ekipman envanteri",
    },
    "maliyet": {
        "columns": ["id", "tarih", "departman", "kategori", "tutar", "aciklama"],
        "description": "Maliyet kayıtları",
    },
}

# Doğal dil → SQL anahtar kelimeleri
NL_TO_SQL_PATTERNS = [
    # Aggregation
    (r"toplam\s+(.+)", "SUM({col})"),
    (r"ortalama\s+(.+)", "AVG({col})"),
    (r"en\s+yüksek\s+(.+)", "MAX({col})"),
    (r"en\s+düşük\s+(.+)", "MIN({col})"),
    (r"kaç\s+tane|sayısı|adet", "COUNT(*)"),
    
    # Time
    (r"bugün|günlük", "WHERE tarih = CURRENT_DATE"),
    (r"bu\s+hafta", "WHERE tarih >= date_trunc('week', CURRENT_DATE)"),
    (r"bu\s+ay", "WHERE tarih >= date_trunc('month', CURRENT_DATE)"),
    (r"son\s+(\d+)\s+gün", "WHERE tarih >= CURRENT_DATE - INTERVAL '{n} days'"),
    (r"son\s+(\d+)\s+ay", "WHERE tarih >= CURRENT_DATE - INTERVAL '{n} months'"),
    (r"geçen\s+ay", "WHERE tarih >= date_trunc('month', CURRENT_DATE - INTERVAL '1 month') AND tarih < date_trunc('month', CURRENT_DATE)"),
    
    # Sorting
    (r"en\s+çok|en\s+fazla", "ORDER BY {col} DESC LIMIT 10"),
    (r"en\s+az|en\s+düşük", "ORDER BY {col} ASC LIMIT 10"),
    
    # Grouping
    (r"(departman|bölüm)\s+bazında", "GROUP BY departman"),
    (r"(ürün|urun)\s+bazında", "GROUP BY urun"),
    (r"(vardiya)\s+bazında", "GROUP BY vardiya"),
    (r"(aylık|aylik)", "GROUP BY date_trunc('month', tarih)"),
    (r"(haftalık|haftalik)", "GROUP BY date_trunc('week', tarih)"),
    (r"(günlük|gunluk)", "GROUP BY tarih"),
]


def detect_table(question: str) -> Optional[str]:
    """Sorudan ilgili tabloyu algıla."""
    question_lower = question.lower()
    
    table_keywords = {
        "uretim": ["üretim", "fire", "duruş", "tezgah", "vardiya", "miktar"],
        "kalite": ["kalite", "hata", "denetim", "kontrol", "parti", "red", "ret"],
        "satis": ["satış", "sipariş", "müşteri", "fiyat", "ciro", "gelir"],
        "stok": ["stok", "envanter", "depo", "malzeme", "hammadde"],
        "personel": ["personel", "çalışan", "maaş", "devamsızlık", "işe alım"],
        "makine": ["makine", "ekipman", "bakım", "arıza"],
        "maliyet": ["maliyet", "gider", "harcama", "bütçe"],
    }
    
    scores = {}
    for table, keywords in table_keywords.items():
        score = sum(1 for kw in keywords if kw in question_lower)
        if score > 0:
            scores[table] = score
    
    if scores:
        return max(scores, key=scores.get)
    return None


def generate_sql(question: str, table_hint: str = None) -> dict:
    """Doğal dil sorusundan SQL sorgusu oluştur.
    
    Returns: {"sql": "SELECT ...", "table": "...", "explanation": "...", "confidence": 0-1}
    """
    question_lower = question.lower()
    
    # Tablo tespiti
    table = table_hint or detect_table(question)
    if not table:
        return {
            "sql": None,
            "error": "Hangi veri tablosu kullanılacak belirlenemedi",
            "suggestion": f"Mevcut tablolar: {', '.join(KNOWN_SCHEMAS.keys())}",
            "confidence": 0,
        }
    
    schema = KNOWN_SCHEMAS.get(table, {})
    columns = schema.get("columns", [])
    
    # SELECT bölümü
    select_parts = []
    group_by = []
    where_parts = []
    order_by = ""
    limit = ""
    
    # Aggregation algılama
    if any(w in question_lower for w in ["toplam", "toplamı", "toplami"]):
        col = _find_numeric_column(question_lower, columns)
        select_parts.append(f"SUM({col}) AS toplam")
    elif any(w in question_lower for w in ["ortalama", "ortalaması"]):
        col = _find_numeric_column(question_lower, columns)
        select_parts.append(f"AVG({col}) AS ortalama")
    elif any(w in question_lower for w in ["en yüksek", "en fazla", "max", "maksimum"]):
        col = _find_numeric_column(question_lower, columns)
        select_parts.append(f"MAX({col}) AS maksimum")
    elif any(w in question_lower for w in ["en düşük", "en az", "min", "minimum"]):
        col = _find_numeric_column(question_lower, columns)
        select_parts.append(f"MIN({col}) AS minimum")
    elif any(w in question_lower for w in ["kaç tane", "sayısı", "adet", "kaç"]):
        select_parts.append("COUNT(*) AS adet")
    
    # GROUP BY algılama
    for col in columns:
        if col in question_lower or col.replace("_", " ") in question_lower:
            if col not in ["id", "not_"]:
                group_by.append(col)
                if col not in [s.split(" AS ")[0].replace("SUM(", "").replace(")", "") for s in select_parts]:
                    select_parts.insert(0, col)
    
    # Bazında / göre kalıpları
    if "bazında" in question_lower or "göre" in question_lower:
        for col in ["departman", "urun", "vardiya", "musteri", "kategori", "hata_tipi"]:
            if col in columns:
                pattern = col.replace("_", " ")
                if pattern in question_lower or col in question_lower:
                    if col not in group_by:
                        group_by.append(col)
                        select_parts.insert(0, col)
    
    # Zaman filtreleri
    if "bugün" in question_lower:
        where_parts.append("tarih = CURRENT_DATE")
    elif "bu hafta" in question_lower:
        where_parts.append("tarih >= date_trunc('week', CURRENT_DATE)")
    elif "bu ay" in question_lower:
        where_parts.append("tarih >= date_trunc('month', CURRENT_DATE)")
    elif "geçen ay" in question_lower:
        where_parts.append("tarih >= date_trunc('month', CURRENT_DATE - INTERVAL '1 month')")
        where_parts.append("tarih < date_trunc('month', CURRENT_DATE)")
    
    # son N gün/ay
    m = re.search(r"son\s+(\d+)\s+gün", question_lower)
    if m:
        where_parts.append(f"tarih >= CURRENT_DATE - INTERVAL '{m.group(1)} days'")
    m = re.search(r"son\s+(\d+)\s+ay", question_lower)
    if m:
        where_parts.append(f"tarih >= CURRENT_DATE - INTERVAL '{m.group(1)} months'")
    
    # Aylık/haftalık gruplama
    if any(w in question_lower for w in ["aylık", "aylik", "ay bazında"]):
        group_by.append("date_trunc('month', tarih)")
        select_parts.insert(0, "date_trunc('month', tarih) AS ay")
    elif any(w in question_lower for w in ["haftalık", "haftalik"]):
        group_by.append("date_trunc('week', tarih)")
        select_parts.insert(0, "date_trunc('week', tarih) AS hafta")
    
    # ORDER & LIMIT
    if any(w in question_lower for w in ["en çok", "en fazla", "ilk 10", "top 10"]):
        agg = select_parts[-1] if select_parts else "*"
        alias = agg.split(" AS ")[-1] if " AS " in agg else agg
        order_by = f"ORDER BY {alias} DESC"
        limit = "LIMIT 10"
    elif any(w in question_lower for w in ["en az", "en düşük"]):
        agg = select_parts[-1] if select_parts else "*"
        alias = agg.split(" AS ")[-1] if " AS " in agg else agg
        order_by = f"ORDER BY {alias} ASC"
        limit = "LIMIT 10"
    
    # Default SELECT
    if not select_parts:
        select_parts = ["*"]
    
    # SQL oluştur
    sql = f"SELECT {', '.join(select_parts)}\nFROM {table}"
    if where_parts:
        sql += f"\nWHERE {' AND '.join(where_parts)}"
    if group_by:
        sql += f"\nGROUP BY {', '.join(group_by)}"
    if order_by:
        sql += f"\n{order_by}"
    if limit:
        sql += f"\n{limit}"
    sql += ";"
    
    # Güven skoru
    confidence = min(1.0, 0.3 + 0.2 * len(select_parts) + 0.2 * len(where_parts) + 0.1 * len(group_by))
    
    return {
        "sql": sql,
        "table": table,
        "explanation": f"{schema.get('description', '')} tablosundan sorgu",
        "confidence": round(confidence, 2),
    }


def _find_numeric_column(question: str, columns: list) -> str:
    """Sorudan sayısal kolonu bul."""
    numeric_hints = {
        "miktar": "miktar",
        "fire": "fire_miktar",
        "tutar": "tutar",
        "fiyat": "birim_fiyat",
        "maaş": "maas",
        "maas": "maas",
        "duruş": "durus_dakika",
        "maliyet": "tutar",
        "hata": "hata_sayisi",
        "saat": "toplam_calisma_saat",
    }
    
    for hint, col in numeric_hints.items():
        if hint in question and col in columns:
            return col
    
    # Fallback: ilk sayısal görünen kolon
    for col in columns:
        if any(w in col for w in ["miktar", "tutar", "fiyat", "saat", "sayi"]):
            return col
    
    return columns[2] if len(columns) > 2 else columns[0]


def build_sql_prompt(question: str, result: dict) -> str:
    """SQL sonucunu LLM prompt'une ekle."""
    if result.get("sql"):
        return (
            f"Kullanıcı sorusu: {question}\n"
            f"Oluşturulan SQL:\n```sql\n{result['sql']}\n```\n"
            f"Tablo: {result['table']} — {result['explanation']}\n"
            f"Güven: {result['confidence']}\n"
            f"Bu SQL'in sonuçlarını doğal dilde açıkla."
        )
    return ""


# ══════════════════════════════════════════════════════════════
# 2. FEATURE ENGINEERING
# ══════════════════════════════════════════════════════════════

def auto_feature_engineering(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """DataFrame'e otomatik feature'lar ekle.
    
    Returns: (enhanced_df, list_of_new_features)
    """
    new_features = []
    df_out = df.copy()
    
    # 1. Tarih feature'ları
    date_cols = df_out.select_dtypes(include=["datetime64"]).columns.tolist()
    if not date_cols:
        # String tarih sütunlarını algıla
        for col in df_out.columns:
            if any(w in col.lower() for w in ["tarih", "date", "zaman", "time"]):
                try:
                    df_out[col] = pd.to_datetime(df_out[col], errors="coerce")
                    date_cols.append(col)
                except Exception:
                    pass
    
    for col in date_cols:
        if df_out[col].notna().sum() > 0:
            df_out[f"{col}_yil"] = df_out[col].dt.year
            df_out[f"{col}_ay"] = df_out[col].dt.month
            df_out[f"{col}_gun"] = df_out[col].dt.day
            df_out[f"{col}_haftanin_gunu"] = df_out[col].dt.dayofweek
            df_out[f"{col}_ceyrek"] = df_out[col].dt.quarter
            df_out[f"{col}_haftasonu"] = (df_out[col].dt.dayofweek >= 5).astype(int)
            new_features.extend([
                f"{col}_yil", f"{col}_ay", f"{col}_gun",
                f"{col}_haftanin_gunu", f"{col}_ceyrek", f"{col}_haftasonu",
            ])
    
    # 2. Sayısal feature'lar
    numeric_cols = df_out.select_dtypes(include=[np.number]).columns.tolist()
    # Orijinal + yeni sayısal olanları ayır
    original_numeric = [c for c in numeric_cols if c in df.columns]
    
    # Lag features (zaman serisi ise)
    if date_cols and len(original_numeric) > 0:
        for col in original_numeric[:3]:  # İlk 3 sayısal kolon
            for lag in [1, 7]:
                feat_name = f"{col}_lag_{lag}"
                df_out[feat_name] = df_out[col].shift(lag)
                new_features.append(feat_name)
    
    # Rolling features
    if len(df_out) >= 7:
        for col in original_numeric[:3]:
            for window in [7]:
                df_out[f"{col}_ma_{window}"] = df_out[col].rolling(window, min_periods=1).mean()
                df_out[f"{col}_std_{window}"] = df_out[col].rolling(window, min_periods=1).std()
                new_features.extend([f"{col}_ma_{window}", f"{col}_std_{window}"])
    
    # 3. Oran feature'ları (2 sayısal kolon varsa)
    if len(original_numeric) >= 2:
        for i in range(min(3, len(original_numeric))):
            for j in range(i + 1, min(4, len(original_numeric))):
                col_a = original_numeric[i]
                col_b = original_numeric[j]
                ratio_name = f"{col_a}_div_{col_b}"
                with np.errstate(divide="ignore", invalid="ignore"):
                    ratio = df_out[col_a] / df_out[col_b].replace(0, np.nan)
                df_out[ratio_name] = ratio
                new_features.append(ratio_name)
    
    # 4. Kategorik encoding
    cat_cols = df_out.select_dtypes(include=["object", "category"]).columns.tolist()
    for col in cat_cols:
        nunique = df_out[col].nunique()
        if 2 <= nunique <= 10:
            dummies = pd.get_dummies(df_out[col], prefix=col, drop_first=True)
            df_out = pd.concat([df_out, dummies], axis=1)
            new_features.extend(dummies.columns.tolist())
    
    # 5. Binning (sayısal kolonları kategorize et)
    for col in original_numeric[:3]:
        try:
            col_data = df_out[col].dropna()
            if len(col_data.unique()) > 5:
                bin_name = f"{col}_segment"
                df_out[bin_name] = pd.qcut(df_out[col], q=4, labels=["Düşük", "Orta-Düşük", "Orta-Yüksek", "Yüksek"], duplicates="drop")
                new_features.append(bin_name)
        except Exception:
            pass
    
    logger.info("feature_engineering_complete", new_features_count=len(new_features))
    return df_out, new_features


def suggest_features(df: pd.DataFrame) -> list[dict]:
    """DataFrame analiz edip feature önerileri ver."""
    suggestions = []
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = df.select_dtypes(include=["object"]).columns.tolist()
    
    # Tarih varsa → zaman özellikleri
    for col in df.columns:
        if any(w in col.lower() for w in ["tarih", "date"]):
            suggestions.append({
                "type": "Tarih Ayrıştırma",
                "column": col,
                "description": f"{col} → yıl, ay, gün, haftanın günü, çeyrek, haftasonu",
                "impact": "Yüksek — sezonluk trendleri yakalar",
            })
    
    # Sayısal varsa → lag + rolling
    if len(numeric_cols) > 0:
        suggestions.append({
            "type": "Lag/Gecikme",
            "column": numeric_cols[0],
            "description": f"{numeric_cols[0]} → 1-günlük ve 7-günlük lag",
            "impact": "Yüksek — geçmiş-gelecek ilişkisi",
        })
        suggestions.append({
            "type": "Hareketli Ortalama",
            "column": numeric_cols[0],
            "description": f"{numeric_cols[0]} → 7 günlük MA ve STD",
            "impact": "Orta — trend ve volatilite",
        })
    
    # 2+ sayısal → oran
    if len(numeric_cols) >= 2:
        suggestions.append({
            "type": "Oran/Ratio",
            "column": f"{numeric_cols[0]} / {numeric_cols[1]}",
            "description": f"Oran hesaplama: verimlilik oranı, fire oranı vb.",
            "impact": "Yüksek — normalize edilmiş karşılaştırma",
        })
    
    # Kategorik → one-hot
    for col in cat_cols[:3]:
        nunique = df[col].nunique()
        if 2 <= nunique <= 10:
            suggestions.append({
                "type": "One-Hot Encoding",
                "column": col,
                "description": f"{col} ({nunique} kategori) → binary sütunlar",
                "impact": "Orta — kategorik veriyi modele hazırlar",
            })
    
    return suggestions
