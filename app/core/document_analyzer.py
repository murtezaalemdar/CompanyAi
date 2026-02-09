"""
Gelişmiş Doküman Analiz Motoru (Document Intelligence)

Yüklenen dokümanlardan:
- Pivot tablo oluşturma
- İstatistiksel analiz
- Trend/karşılaştırma raporu
- Yorum ve tavsiyeler
- Otomatik veri keşfi
- Doğal dil ile veri sorgulama

Desteklenen girdiler:
- Excel (.xlsx, .xls) → Tam tablolu analiz
- CSV (.csv) → Tablolu analiz
- JSON (.json) → Yapısal analiz
- PDF/DOCX/TXT → Metin tabanlı analiz
- RAG'daki mevcut dokümanlar → Semantik analiz
"""

import io
import json
import re
from typing import Optional, Any
from datetime import datetime

import structlog
import pandas as pd
import numpy as np

logger = structlog.get_logger()


# ══════════════════════════════════════════════════════════════
# 1. VERİ PARSE & KEŞİF
# ══════════════════════════════════════════════════════════════

def parse_file_to_dataframe(filename: str, file_content: bytes) -> Optional[pd.DataFrame]:
    """
    Dosyayı pandas DataFrame'e çevir.
    Excel, CSV, JSON ve TSV destekler.
    """
    filename_lower = filename.lower()
    
    try:
        if filename_lower.endswith(('.xlsx', '.xls')):
            # Excel — tüm sayfaları oku, en büyük olanı kullan
            xls = pd.ExcelFile(io.BytesIO(file_content))
            sheets = {}
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                sheets[sheet_name] = df
            
            if not sheets:
                return None
            
            # En çok satırı olan sayfayı döndür
            main_sheet = max(sheets.values(), key=lambda x: len(x))
            
            # Tüm sayfaları metadata olarak sakla
            main_sheet.attrs['_all_sheets'] = {
                name: {"rows": len(df), "cols": len(df.columns)} 
                for name, df in sheets.items()
            }
            main_sheet.attrs['_sheets_data'] = sheets
            
            return main_sheet
        
        elif filename_lower.endswith('.csv'):
            # CSV — farklı delimiter'ları dene
            for sep in [',', ';', '\t', '|']:
                try:
                    df = pd.read_csv(io.BytesIO(file_content), sep=sep, encoding='utf-8')
                    if len(df.columns) > 1:
                        return df
                except Exception:
                    continue
            # Son deneme: otomatik
            return pd.read_csv(io.BytesIO(file_content), encoding='utf-8')
        
        elif filename_lower.endswith('.json'):
            text = file_content.decode('utf-8')
            data = json.loads(text)
            
            if isinstance(data, list):
                return pd.DataFrame(data)
            elif isinstance(data, dict):
                # İç içe dict'i düzleştirmeye çalış
                if any(isinstance(v, list) for v in data.values()):
                    for key, val in data.items():
                        if isinstance(val, list) and val:
                            return pd.DataFrame(val)
                return pd.DataFrame([data])
            
        elif filename_lower.endswith('.tsv'):
            return pd.read_csv(io.BytesIO(file_content), sep='\t', encoding='utf-8')
            
    except Exception as e:
        logger.warning("parse_to_df_failed", file=filename, error=str(e))
    
    return None


def discover_data(df: pd.DataFrame) -> dict:
    """
    DataFrame'i otomatik keşfet — sütun tipleri, istatistikler, ilişkiler.
    """
    info = {
        "row_count": len(df),
        "col_count": len(df.columns),
        "columns": [],
        "numeric_columns": [],
        "categorical_columns": [],
        "date_columns": [],
        "text_columns": [],
        "has_missing": False,
        "missing_summary": {},
        "memory_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
    }
    
    for col in df.columns:
        col_info = {
            "name": col,
            "dtype": str(df[col].dtype),
            "non_null": int(df[col].notna().sum()),
            "null_count": int(df[col].isna().sum()),
            "null_pct": round(df[col].isna().mean() * 100, 1),
            "unique_count": int(df[col].nunique()),
        }
        
        if df[col].isna().any():
            info["has_missing"] = True
            info["missing_summary"][col] = col_info["null_count"]
        
        # Tarih tespiti
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            info["date_columns"].append(col)
            col_info["type"] = "date"
            col_info["min"] = str(df[col].min())
            col_info["max"] = str(df[col].max())
        
        # Sayısal tespiti
        elif pd.api.types.is_numeric_dtype(df[col]):
            info["numeric_columns"].append(col)
            col_info["type"] = "numeric"
            col_info["min"] = float(df[col].min()) if df[col].notna().any() else None
            col_info["max"] = float(df[col].max()) if df[col].notna().any() else None
            col_info["mean"] = round(float(df[col].mean()), 2) if df[col].notna().any() else None
            col_info["median"] = round(float(df[col].median()), 2) if df[col].notna().any() else None
            col_info["std"] = round(float(df[col].std()), 2) if df[col].notna().any() else None
            col_info["sum"] = float(df[col].sum()) if df[col].notna().any() else None
        
        # Kategorik tespiti
        elif df[col].nunique() <= max(20, len(df) * 0.05):
            info["categorical_columns"].append(col)
            col_info["type"] = "categorical"
            col_info["top_values"] = df[col].value_counts().head(10).to_dict()
        
        # Metin
        else:
            info["text_columns"].append(col)
            col_info["type"] = "text"
            col_info["avg_length"] = round(df[col].astype(str).str.len().mean(), 0)
        
        # Tarih string tespiti (sütun string ama tarih gibi görünüyor)
        if col_info.get("type") not in ("date", "numeric") and df[col].dtype == "object":
            sample = df[col].dropna().head(20).astype(str)
            date_patterns = [
                r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',
                r'\d{1,2}[-/.]\d{1,2}[-/.]\d{4}',
            ]
            date_matches = sum(
                1 for s in sample 
                if any(re.search(p, s) for p in date_patterns)
            )
            if date_matches > len(sample) * 0.5:
                col_info["possible_date"] = True
                info["date_columns"].append(col)
        
        info["columns"].append(col_info)
    
    return info


# ══════════════════════════════════════════════════════════════
# 2. PİVOT TABLO
# ══════════════════════════════════════════════════════════════

def create_pivot(
    df: pd.DataFrame,
    rows: list[str] = None,
    columns: list[str] = None,
    values: list[str] = None,
    aggfunc: str = "sum",
    fill_value: Any = 0,
) -> dict:
    """
    Pivot tablo oluştur.
    
    Parametreler:
        rows: Satır bazında gruplama sütunları
        columns: Sütun bazında gruplama
        values: Hesaplanacak değer sütunları
        aggfunc: sum, mean, count, min, max, std
        fill_value: Boş hücre değeri
    """
    agg_map = {
        "sum": "sum", "toplam": "sum",
        "mean": "mean", "ortalama": "mean",
        "count": "count", "sayı": "count", "adet": "count",
        "min": "min", "minimum": "min", "en düşük": "min",
        "max": "max", "maximum": "max", "en yüksek": "max",
        "std": "std", "standart sapma": "std",
        "median": "median", "medyan": "median",
    }
    
    func = agg_map.get(aggfunc.lower(), "sum")
    
    try:
        if rows and values:
            pivot = pd.pivot_table(
                df,
                index=rows,
                columns=columns,
                values=values,
                aggfunc=func,
                fill_value=fill_value,
                margins=True,
                margins_name="TOPLAM"
            )
        elif rows:
            # Sadece gruplama
            pivot = df.groupby(rows).agg(func, numeric_only=True)
            pivot.loc["TOPLAM"] = pivot.sum(numeric_only=True)
        else:
            # Tüm sayısal sütunların özeti
            pivot = df.describe()
        
        return {
            "success": True,
            "table": pivot.to_dict(),
            "table_str": pivot.to_string(),
            "table_markdown": pivot.to_markdown() if hasattr(pivot, 'to_markdown') else pivot.to_string(),
            "shape": list(pivot.shape),
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def smart_pivot(df: pd.DataFrame, question: str = None) -> dict:
    """
    Soruya göre otomatik pivot oluştur.
    Soru verilmezse en mantıklı pivot'u otomatik belirle.
    """
    discovery = discover_data(df)
    
    cat_cols = discovery["categorical_columns"]
    num_cols = discovery["numeric_columns"]
    
    if not num_cols:
        return {"success": False, "error": "Sayısal sütun bulunamadı, pivot oluşturulamaz"}
    
    # Otomatik seçim
    if cat_cols and num_cols:
        best_row = cat_cols[0]
        best_value = num_cols[:3]  # İlk 3 sayısal sütun
        
        # Eğer 2+ kategorik varsa, ikincisini sütun olarak kullan
        best_col = cat_cols[1] if len(cat_cols) > 1 else None
        
        return create_pivot(
            df,
            rows=[best_row],
            columns=[best_col] if best_col else None,
            values=best_value,
            aggfunc="sum"
        )
    
    # Sadece sayısal varsa, describe (istatistiksel özet)
    return create_pivot(df)


# ══════════════════════════════════════════════════════════════
# 3. İSTATİSTİKSEL ANALİZ
# ══════════════════════════════════════════════════════════════

def statistical_analysis(df: pd.DataFrame) -> dict:
    """Kapsamlı istatistiksel analiz"""
    result = {
        "basic_stats": {},
        "correlations": None,
        "distributions": {},
        "outliers": {},
        "trends": {},
    }
    
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    # Temel istatistikler
    if num_cols:
        desc = df[num_cols].describe()
        result["basic_stats"] = desc.to_dict()
        
        # Korelasyon matrisi
        if len(num_cols) > 1:
            corr = df[num_cols].corr()
            result["correlations"] = corr.to_dict()
            
            # Güçlü korelasyonlar
            strong_corrs = []
            for i in range(len(corr.columns)):
                for j in range(i+1, len(corr.columns)):
                    val = corr.iloc[i, j]
                    if abs(val) > 0.5:
                        strong_corrs.append({
                            "col1": corr.columns[i],
                            "col2": corr.columns[j],
                            "correlation": round(val, 3),
                            "strength": "Güçlü" if abs(val) > 0.7 else "Orta",
                            "direction": "Pozitif" if val > 0 else "Negatif",
                        })
            result["strong_correlations"] = strong_corrs
        
        # Aykırı değer tespiti (IQR yöntemi)
        for col in num_cols:
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR
            outliers = df[(df[col] < lower) | (df[col] > upper)][col]
            if len(outliers) > 0:
                result["outliers"][col] = {
                    "count": len(outliers),
                    "percentage": round(len(outliers) / len(df) * 100, 1),
                    "lower_bound": round(lower, 2),
                    "upper_bound": round(upper, 2),
                    "min_outlier": round(float(outliers.min()), 2),
                    "max_outlier": round(float(outliers.max()), 2),
                }
        
        # Dağılım bilgisi
        for col in num_cols:
            try:
                skew = float(df[col].skew())
                kurt = float(df[col].kurtosis())
                result["distributions"][col] = {
                    "skewness": round(skew, 3),
                    "kurtosis": round(kurt, 3),
                    "distribution_type": (
                        "Normal dağılım" if abs(skew) < 0.5 and abs(kurt) < 1
                        else "Sağa çarpık" if skew > 0.5
                        else "Sola çarpık" if skew < -0.5
                        else "Sivri" if kurt > 1
                        else "Basık"
                    ),
                }
            except Exception:
                pass
    
    return result


# ══════════════════════════════════════════════════════════════
# 4. TREND ANALİZİ
# ══════════════════════════════════════════════════════════════

def trend_analysis(df: pd.DataFrame, date_col: str = None, value_col: str = None) -> dict:
    """Zaman serisi trend analizi"""
    
    # Tarih sütununu otomatik bul
    if not date_col:
        for col in df.columns:
            try:
                pd.to_datetime(df[col])
                date_col = col
                break
            except Exception:
                continue
    
    if not date_col:
        return {"success": False, "error": "Tarih sütunu bulunamadı"}
    
    # Değer sütununu otomatik bul
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if not value_col:
        value_col = num_cols[0] if num_cols else None
    
    if not value_col:
        return {"success": False, "error": "Sayısal değer sütunu bulunamadı"}
    
    try:
        df_sorted = df.copy()
        df_sorted[date_col] = pd.to_datetime(df_sorted[date_col])
        df_sorted = df_sorted.sort_values(date_col)
        
        trends = {}
        for col in ([value_col] if isinstance(value_col, str) else num_cols[:5]):
            if col not in df_sorted.columns or not pd.api.types.is_numeric_dtype(df_sorted[col]):
                continue
            
            vals = df_sorted[col].dropna()
            if len(vals) < 3:
                continue
            
            first_half = vals[:len(vals)//2].mean()
            second_half = vals[len(vals)//2:].mean()
            
            change_pct = ((second_half - first_half) / first_half * 100) if first_half != 0 else 0
            
            # Basit regresyon eğimi
            x = np.arange(len(vals))
            slope = np.polyfit(x, vals.values, 1)[0] if len(vals) > 1 else 0
            
            trends[col] = {
                "direction": "Artış" if change_pct > 5 else "Azalma" if change_pct < -5 else "Stabil",
                "change_pct": round(change_pct, 1),
                "first_half_avg": round(float(first_half), 2),
                "second_half_avg": round(float(second_half), 2),
                "slope": round(float(slope), 4),
                "min_value": round(float(vals.min()), 2),
                "max_value": round(float(vals.max()), 2),
                "latest_value": round(float(vals.iloc[-1]), 2),
            }
        
        return {
            "success": True,
            "date_column": date_col,
            "date_range": f"{df_sorted[date_col].min()} - {df_sorted[date_col].max()}",
            "data_points": len(df_sorted),
            "trends": trends,
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════
# 5. TOP-N / SIRALAMA ANALİZİ
# ══════════════════════════════════════════════════════════════

def top_n_analysis(df: pd.DataFrame, n: int = 10) -> dict:
    """Her sayısal sütun için top-N ve bottom-N"""
    results = {}
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = [c for c in df.columns if c not in num_cols]
    
    label_col = cat_cols[0] if cat_cols else None
    
    for col in num_cols[:5]:  # En fazla 5 sütun
        sorted_df = df.nlargest(n, col)
        if label_col:
            top = sorted_df[[label_col, col]].to_dict('records')
        else:
            top = sorted_df[[col]].to_dict('records')
        
        sorted_df_bottom = df.nsmallest(n, col)
        if label_col:
            bottom = sorted_df_bottom[[label_col, col]].to_dict('records')
        else:
            bottom = sorted_df_bottom[[col]].to_dict('records')
        
        results[col] = {"top": top, "bottom": bottom}
    
    return results


# ══════════════════════════════════════════════════════════════
# 6. KARŞILAŞTIRMA ANALİZİ
# ══════════════════════════════════════════════════════════════

def comparison_analysis(df: pd.DataFrame, group_col: str = None) -> dict:
    """Kategorik gruplara göre karşılaştırma"""
    
    if not group_col:
        # Otomatik kategorik sütun seç
        cat_cols = [
            c for c in df.columns 
            if df[c].dtype == 'object' and df[c].nunique() <= 20
        ]
        if not cat_cols:
            return {"success": False, "error": "Gruplama için uygun kategorik sütun bulunamadı"}
        group_col = cat_cols[0]
    
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if not num_cols:
        return {"success": False, "error": "Sayısal sütun bulunamadı"}
    
    grouped = df.groupby(group_col)[num_cols].agg(['mean', 'sum', 'count', 'min', 'max'])
    
    result = {
        "success": True,
        "group_column": group_col,
        "groups": list(df[group_col].unique()),
        "group_count": df[group_col].nunique(),
        "summary": {},
    }
    
    for col in num_cols[:5]:
        group_means = df.groupby(group_col)[col].mean().sort_values(ascending=False)
        group_sums = df.groupby(group_col)[col].sum().sort_values(ascending=False)
        group_counts = df.groupby(group_col)[col].count()
        
        result["summary"][col] = {
            "best_group": str(group_means.index[0]) if len(group_means) > 0 else None,
            "worst_group": str(group_means.index[-1]) if len(group_means) > 0 else None,
            "means": {str(k): round(v, 2) for k, v in group_means.items()},
            "sums": {str(k): round(v, 2) for k, v in group_sums.items()},
            "counts": {str(k): int(v) for k, v in group_counts.items()},
        }
    
    return result


# ══════════════════════════════════════════════════════════════
# 7. RAPOR + YORUM + TAVSİYE OLUŞTURMA (LLM İÇİN PROMPT)
# ══════════════════════════════════════════════════════════════

def generate_analysis_prompt(
    df: pd.DataFrame,
    analysis_type: str = "full",
    question: str = None,
    filename: str = None,
) -> str:
    """
    LLM'e gönderilecek detaylı analiz prompt'u oluştur.
    
    analysis_type:
        - "full": Tam analiz (keşif + istatistik + pivot + trend + tavsiye)
        - "pivot": Sadece pivot tablo
        - "trend": Trend analizi
        - "compare": Karşılaştırma
        - "summary": Hızlı özet
        - "recommend": Tavsiye odaklı
        - "report": Resmi rapor formatında
    """
    
    discovery = discover_data(df)
    
    # Temel veri bilgisi
    prompt = f"""## 📊 Doküman Analizi: {filename or 'Yüklenen Veri'}

### Veri Özeti:
- **Satır sayısı**: {discovery['row_count']}
- **Sütun sayısı**: {discovery['col_count']}
- **Sayısal sütunlar**: {', '.join(discovery['numeric_columns']) or 'Yok'}
- **Kategorik sütunlar**: {', '.join(discovery['categorical_columns']) or 'Yok'}
- **Tarih sütunları**: {', '.join(discovery['date_columns']) or 'Yok'}
"""
    
    # Sütun detayları
    prompt += "\n### Sütun Bilgileri:\n"
    for col_info in discovery["columns"]:
        line = f"- **{col_info['name']}** ({col_info['type']}): "
        if col_info["type"] == "numeric":
            line += f"Min={col_info.get('min')}, Max={col_info.get('max')}, Ort={col_info.get('mean')}, Toplam={col_info.get('sum')}"
        elif col_info["type"] == "categorical":
            top_vals = col_info.get("top_values", {})
            top_3 = list(top_vals.items())[:3]
            line += f"{col_info['unique_count']} benzersiz değer. En sık: {', '.join(f'{k}({v})' for k, v in top_3)}"
        elif col_info["type"] == "date":
            line += f"Aralık: {col_info.get('min')} → {col_info.get('max')}"
        else:
            line += f"Ort uzunluk: {col_info.get('avg_length', 'N/A')} karakter"
        
        if col_info["null_count"] > 0:
            line += f" [⚠️ %{col_info['null_pct']} eksik]"
        prompt += line + "\n"
    
    # İstatistiksel Analiz
    stats = statistical_analysis(df)
    
    if stats.get("strong_correlations"):
        prompt += "\n### Korelasyonlar (Güçlü İlişkiler):\n"
        for corr in stats["strong_correlations"]:
            prompt += f"- **{corr['col1']}** ↔ **{corr['col2']}**: {corr['correlation']} ({corr['strength']} {corr['direction']})\n"
    
    if stats.get("outliers"):
        prompt += "\n### Aykırı Değerler:\n"
        for col, info in stats["outliers"].items():
            prompt += f"- **{col}**: {info['count']} aykırı değer (%{info['percentage']}), normal aralık: {info['lower_bound']} - {info['upper_bound']}\n"
    
    # Pivot Tablo
    if analysis_type in ("full", "pivot") and discovery["categorical_columns"] and discovery["numeric_columns"]:
        pivot_result = smart_pivot(df)
        if pivot_result.get("success"):
            prompt += f"\n### Pivot Tablo:\n```\n{pivot_result['table_str'][:2000]}\n```\n"
    
    # Trend Analizi
    if analysis_type in ("full", "trend") and discovery["date_columns"]:
        trend = trend_analysis(df)
        if trend.get("success"):
            prompt += f"\n### Trend Analizi ({trend['date_range']}):\n"
            for col, t_info in trend.get("trends", {}).items():
                prompt += f"- **{col}**: {t_info['direction']} (%{t_info['change_pct']}), Son değer: {t_info['latest_value']}\n"
    
    # Karşılaştırma
    if analysis_type in ("full", "compare") and discovery["categorical_columns"]:
        comp = comparison_analysis(df)
        if comp.get("success"):
            prompt += f"\n### Grup Karşılaştırması ({comp['group_column']}):\n"
            for col, cinfo in comp.get("summary", {}).items():
                prompt += f"- **{col}**: En iyi={cinfo['best_group']}, En düşük={cinfo['worst_group']}\n"
    
    # Top-N
    if analysis_type in ("full", "report") and discovery["numeric_columns"]:
        top_n = top_n_analysis(df, n=5)
        if top_n:
            prompt += "\n### En Yüksek / En Düşük Değerler:\n"
            for col, data in list(top_n.items())[:3]:
                prompt += f"**{col} — Top 5:**\n"
                for item in data["top"][:5]:
                    vals = [f"{k}: {v}" for k, v in item.items()]
                    prompt += f"  - {', '.join(vals)}\n"
    
    # Veri örneği
    sample_rows = min(5, len(df))
    prompt += f"\n### Veri Örneği (İlk {sample_rows} Satır):\n"
    prompt += f"```\n{df.head(sample_rows).to_string()}\n```\n"
    
    # Analiz talimatı
    if analysis_type == "pivot":
        prompt += "\n**GÖREV**: Yukarıdaki verilere göre detaylı pivot tablo analizi yap. Hangi kategorilerin öne çıktığını, karşılaştırmaları ve önemli bulguları raporla."
    elif analysis_type == "trend":
        prompt += "\n**GÖREV**: Trend analizini yorumla. Artış/azalma nedenlerini, mevsimsel etkileri ve gelecek projeksiyonlarını belirt."
    elif analysis_type == "compare":
        prompt += "\n**GÖREV**: Grupları detaylı karşılaştır. En iyi/en kötü performans gösterenleri belirle ve nedenleri hakkında yorum yap."
    elif analysis_type == "recommend":
        prompt += "\n**GÖREV**: Bu verilere dayanarak somut, uygulanabilir TAVSİYELER sun. Her tavsiyeyi verilerle destekle. Risk analizi de yap."
    elif analysis_type == "report":
        prompt += "\n**GÖREV**: Bu verilerle profesyonel bir RAPOR oluştur. Yönetici Özeti, Bulgular, Detaylı Analiz, Riskler, Öneriler bölümlerini içersin."
    elif analysis_type == "summary":
        prompt += "\n**GÖREV**: Bu veriyi 5-6 cümlede özetle. En çarpıcı bulguları vurgula."
    else:  # full
        prompt += """
**GÖREV**: Bu veri setini kapsamlı analiz et ve aşağıdaki başlıklarda yanıt ver:

1. **📋 Veri Özeti**: Veri setinin genel yapısını ve kalitesini değerlendir
2. **📊 Temel Bulgular**: En önemli sayısal bulgular (en yüksek, en düşük, ortalamalar)
3. **📈 Trend & Değişim**: Zaman bazlı veya kategorik değişimler
4. **🔍 Dikkat Çekici Noktalar**: Aykırı değerler, beklenmeyen paternler, eksik veriler
5. **💡 Yorumlar**: Verilerin ne anlama geldiği hakkında profesyonel yorumlar
6. **✅ Tavsiyeler**: Somut, uygulanabilir öneriler (en az 3-5 madde)
7. **⚠️ Riskler**: Dikkat edilmesi gereken riskler ve uyarılar
"""
    
    # Kullanıcı sorusu varsa ekle
    if question:
        prompt += f"\n**Kullanıcının sorusu/talebi**: {question}\nBu soruyu da mutlaka cevapla.\n"
    
    return prompt


# ══════════════════════════════════════════════════════════════
# 8. METİN TABANLI DÖKÜMAN ANALİZİ (PDF/DOCX/TXT)
# ══════════════════════════════════════════════════════════════

def generate_text_analysis_prompt(
    text: str,
    analysis_type: str = "full",
    question: str = None,
    filename: str = None,
) -> str:
    """
    Metin tabanlı dokümanlar için analiz prompt'u.
    PDF, DOCX, TXT gibi yapılandırılmamış veriler için.
    """
    # Metin istatistikleri
    word_count = len(text.split())
    line_count = len(text.split('\n'))
    char_count = len(text)
    
    # Anahtar kelimeler (en sık geçen kelimeler)
    words = re.findall(r'\b[a-zA-ZçğıöşüÇĞIİÖŞÜ]{4,}\b', text.lower())
    word_freq = {}
    stop_words = {'için', 'olan', 'olarak', 'veya', 'gibi', 'kadar', 'daha', 'ancak', 'fakat', 'bile'}
    for w in words:
        if w not in stop_words:
            word_freq[w] = word_freq.get(w, 0) + 1
    
    top_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:15]
    
    # Sayısal değerler
    numbers = re.findall(r'\b\d+[.,]?\d*\b', text)
    
    # Metnin kısaltılmış hali (çok uzunsa)
    max_text = 8000
    display_text = text[:max_text] + f"\n\n[... {char_count - max_text} karakter daha ...]" if len(text) > max_text else text
    
    prompt = f"""## 📄 Doküman Analizi: {filename or 'Yüklenen Doküman'}

### Doküman Bilgileri:
- **Kelime sayısı**: {word_count:,}
- **Satır sayısı**: {line_count:,}
- **Karakter sayısı**: {char_count:,}
- **İçerdiği sayısal değerler**: {len(numbers)} adet
- **Anahtar kelimeler**: {', '.join(f'{w}({c})' for w, c in top_keywords[:10])}

### Doküman İçeriği:
```
{display_text}
```

"""
    
    if analysis_type == "summary":
        prompt += "**GÖREV**: Bu dokümanı 5-10 cümlede özetle. Ana konuları ve en önemli bilgileri vurgula."
    elif analysis_type == "recommend":
        prompt += "**GÖREV**: Bu dokümandaki bilgilere dayanarak somut tavsiyeler sun. Her tavsiyeyi dokümandaki verilerle destekle."
    elif analysis_type == "report":
        prompt += """**GÖREV**: Bu doküman hakkında kapsamlı bir rapor oluştur:
1. Yönetici Özeti
2. Ana Bulgular
3. Detaylı Değerlendirme
4. Öneriler ve Aksiyon Maddeleri
5. Riskler ve Uyarılar"""
    else:
        prompt += """**GÖREV**: Bu dokümanı detaylı analiz et:
1. **📋 Özet**: Dokümanın ana konusu ve amacı
2. **🔍 Temel Bulgular**: İçindeki en önemli bilgiler
3. **💡 Yorumlar**: Profesyonel değerlendirme
4. **✅ Tavsiyeler**: Somut öneriler
5. **⚠️ Dikkat Edilecekler**: Riskler ve uyarılar
"""
    
    if question:
        prompt += f"\n**Kullanıcının sorusu/talebi**: {question}\nBu soruyu da mutlaka cevapla.\n"
    
    return prompt


# ══════════════════════════════════════════════════════════════
# 9. DOĞAL DİL İLE VERİ SORGULAMA
# ══════════════════════════════════════════════════════════════

def natural_language_query(df: pd.DataFrame, question: str) -> dict:
    """
    Doğal dil sorusunu pandas işlemine çevir.
    Basit sorguları otomatik çalıştır.
    """
    q = question.lower()
    result = {"success": False, "answer": None, "query_type": None}
    
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    try:
        # Toplam/Sum
        if re.search(r'toplam|sum|genel\s*toplam', q):
            for col in num_cols:
                if col.lower() in q:
                    result = {
                        "success": True,
                        "answer": f"{col} toplamı: {df[col].sum():,.2f}",
                        "value": float(df[col].sum()),
                        "query_type": "sum"
                    }
                    return result
            # Tüm toplamlar
            sums = {col: round(float(df[col].sum()), 2) for col in num_cols}
            result = {"success": True, "answer": str(sums), "value": sums, "query_type": "sum_all"}
            return result
        
        # Ortalama
        if re.search(r'ortalama|mean|average', q):
            for col in num_cols:
                if col.lower() in q:
                    result = {
                        "success": True,
                        "answer": f"{col} ortalaması: {df[col].mean():,.2f}",
                        "value": float(df[col].mean()),
                        "query_type": "mean"
                    }
                    return result
            means = {col: round(float(df[col].mean()), 2) for col in num_cols}
            result = {"success": True, "answer": str(means), "value": means, "query_type": "mean_all"}
            return result
        
        # En yüksek/max
        if re.search(r'en (yüksek|fazla|büyük|çok)|max|maksimum', q):
            for col in num_cols:
                if col.lower() in q:
                    idx = df[col].idxmax()
                    row = df.loc[idx]
                    result = {
                        "success": True,
                        "answer": f"{col} en yüksek: {row[col]:,.2f}\nSatır: {row.to_dict()}",
                        "value": float(row[col]),
                        "row": row.to_dict(),
                        "query_type": "max"
                    }
                    return result
        
        # En düşük/min
        if re.search(r'en (düşük|az|küçük)|min|minimum', q):
            for col in num_cols:
                if col.lower() in q:
                    idx = df[col].idxmin()
                    row = df.loc[idx]
                    result = {
                        "success": True,
                        "answer": f"{col} en düşük: {row[col]:,.2f}\nSatır: {row.to_dict()}",
                        "value": float(row[col]),
                        "row": row.to_dict(),
                        "query_type": "min"
                    }
                    return result
        
        # Satır sayısı
        if re.search(r'kaç\s*(tane|adet|satır)|satır\s*sayısı|count', q):
            result = {
                "success": True,
                "answer": f"Toplam {len(df)} satır var.",
                "value": len(df),
                "query_type": "count"
            }
            return result
        
        # Filtre (belirli bir değer arama)
        for col in df.columns:
            col_lower = col.lower()
            if col_lower in q:
                # "X olan satırlar" gibi
                for val in df[col].unique():
                    val_str = str(val).lower()
                    if val_str in q and len(val_str) > 2:
                        filtered = df[df[col] == val]
                        result = {
                            "success": True,
                            "answer": f"{col}={val} olan {len(filtered)} satır bulundu.\n{filtered.to_string()[:1000]}",
                            "value": len(filtered),
                            "query_type": "filter"
                        }
                        return result
        
    except Exception as e:
        result["error"] = str(e)
    
    return result


# ══════════════════════════════════════════════════════════════
# 10. ANALİZ SONUÇLARINI FORMATLA (JSON → LLM-Ready)
# ══════════════════════════════════════════════════════════════

def format_analysis_for_llm(
    df: pd.DataFrame = None,
    text: str = None,
    analysis_type: str = "full",
    question: str = None,
    filename: str = None,
) -> str:
    """
    Dosya tipine göre uygun analiz prompt'u döndür.
    DataFrame varsa tablolu analiz, yoksa metin analizi.
    """
    if df is not None and not df.empty:
        return generate_analysis_prompt(df, analysis_type, question, filename)
    elif text:
        return generate_text_analysis_prompt(text, analysis_type, question, filename)
    else:
        return "Analiz edilecek veri bulunamadı."
