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
            
            # Tüm sayfaları metadata olarak sakla (sadece istatistik, DataFrame referansı KOYMUYORUZ)
            main_sheet.attrs['_all_sheets'] = {
                name: {"rows": len(df), "cols": len(df.columns)} 
                for name, df in sheets.items()
            }
            # NOT: _sheets_data attrs'a konmaz — pandas deepcopy recursion bug'ına yol açar
            
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
    # ÖNEMLİ BUG FIX (commit 6a1d0b6): pandas 2.3.x deepcopy recursion bug
    # pandas 2.3.x'te DataFrame.__finalize__() deepcopy(other.attrs) çağırıyor.
    # Eğer attrs içinde başka DataFrame nesneleri varsa (ör: _sheets_data)
    # sonsuz döngüye girer → RecursionError. Bu satır attrs'u TEMİZLER.
    # parse_file_to_dataframe() sheets bilgisini artık attrs'a koymaz.
    df.attrs = {}
    
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
    """Gelişmiş zaman serisi trend analizi — hareketli ortalama, volatilite, büyüme oranları"""
    
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
            
            # Hareketli ortalamalar
            moving_avgs = {}
            for window in [3, 7, 14, 30]:
                if len(vals) >= window * 2:
                    ma = vals.rolling(window=window).mean().dropna()
                    moving_avgs[f"MA{window}"] = {
                        "current": round(float(ma.iloc[-1]), 2),
                        "previous": round(float(ma.iloc[-2]), 2) if len(ma) > 1 else None,
                        "trend": "Yükseliş" if len(ma) > 1 and ma.iloc[-1] > ma.iloc[-2] else "Düşüş",
                    }
            
            # Volatilite (standart sapma / ortalama)
            volatility = float(vals.std() / vals.mean() * 100) if vals.mean() != 0 else 0
            
            # Dönemsel büyüme oranları
            growth_rates = {}
            n = len(vals)
            quartiles = [("Q1→Q2", 0, n//4, n//4, n//2), ("Q2→Q3", n//4, n//2, n//2, 3*n//4), ("Q3→Q4", n//2, 3*n//4, 3*n//4, n)]
            for label, s1, e1, s2, e2 in quartiles:
                if e1 > s1 and e2 > s2:
                    avg1 = vals.iloc[s1:e1].mean()
                    avg2 = vals.iloc[s2:e2].mean()
                    if avg1 != 0:
                        growth_rates[label] = round(((avg2 - avg1) / avg1) * 100, 1)
            
            # Son değer vs uzun vadeli ortalama karşılaştırması
            long_avg = float(vals.mean())
            latest = float(vals.iloc[-1])
            position_vs_avg = round(((latest - long_avg) / long_avg) * 100, 1) if long_avg != 0 else 0
            
            trends[col] = {
                "direction": "Artış" if change_pct > 5 else "Azalma" if change_pct < -5 else "Stabil",
                "change_pct": round(change_pct, 1),
                "first_half_avg": round(float(first_half), 2),
                "second_half_avg": round(float(second_half), 2),
                "slope": round(float(slope), 4),
                "min_value": round(float(vals.min()), 2),
                "max_value": round(float(vals.max()), 2),
                "latest_value": round(float(vals.iloc[-1]), 2),
                "moving_averages": moving_avgs,
                "volatility_pct": round(volatility, 1),
                "growth_rates": growth_rates,
                "position_vs_avg": position_vs_avg,
                "momentum": "Güçlü Yükseliş" if change_pct > 20 else "Yükseliş" if change_pct > 5 else "Güçlü Düşüş" if change_pct < -20 else "Düşüş" if change_pct < -5 else "Yatay",
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
    """Gelişmiş kategorik gruplara göre karşılaştırma — medyan, std, fark yüzdesi"""
    
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
        group_medians = df.groupby(group_col)[col].median().sort_values(ascending=False)
        group_sums = df.groupby(group_col)[col].sum().sort_values(ascending=False)
        group_counts = df.groupby(group_col)[col].count()
        group_stds = df.groupby(group_col)[col].std()
        
        # Gruplar arası fark yüzdesi (en iyi vs en kötü)
        best_val = group_means.iloc[0] if len(group_means) > 0 else 0
        worst_val = group_means.iloc[-1] if len(group_means) > 0 else 0
        gap_pct = round(((best_val - worst_val) / worst_val) * 100, 1) if worst_val != 0 else 0
        
        # Genel ortalamadan sapma
        overall_mean = df[col].mean()
        deviations = {}
        for grp in group_means.index:
            dev = round(((group_means[grp] - overall_mean) / overall_mean) * 100, 1) if overall_mean != 0 else 0
            deviations[str(grp)] = dev
        
        result["summary"][col] = {
            "best_group": str(group_means.index[0]) if len(group_means) > 0 else None,
            "worst_group": str(group_means.index[-1]) if len(group_means) > 0 else None,
            "gap_pct": gap_pct,
            "means": {str(k): round(v, 2) for k, v in group_means.items()},
            "medians": {str(k): round(v, 2) for k, v in group_medians.items()},
            "sums": {str(k): round(v, 2) for k, v in group_sums.items()},
            "counts": {str(k): int(v) for k, v in group_counts.items()},
            "std_devs": {str(k): round(v, 2) for k, v in group_stds.items() if not pd.isna(v)},
            "deviation_from_avg": deviations,
            "overall_mean": round(overall_mean, 2),
        }
    
    return result


# ══════════════════════════════════════════════════════════════
# 6b. ANOMALİ TESPİTİ (IQR + Z-Score)
# ══════════════════════════════════════════════════════════════

def anomaly_detection(df: pd.DataFrame) -> dict:
    """IQR ve Z-Score ile aykırı değer tespiti"""
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if not num_cols:
        return {"success": False, "error": "Sayısal sütun bulunamadı"}
    
    anomalies = {}
    total_anomaly_count = 0
    
    for col in num_cols[:8]:
        vals = df[col].dropna()
        if len(vals) < 10:
            continue
        
        # IQR yöntemi
        Q1 = vals.quantile(0.25)
        Q3 = vals.quantile(0.75)
        IQR = Q3 - Q1
        lower_iqr = Q1 - 1.5 * IQR
        upper_iqr = Q3 + 1.5 * IQR
        iqr_outliers = vals[(vals < lower_iqr) | (vals > upper_iqr)]
        
        # Z-Score yöntemi
        mean_val = vals.mean()
        std_val = vals.std()
        if std_val > 0:
            z_scores = np.abs((vals - mean_val) / std_val)
            z_outliers = vals[z_scores > 2.5]
        else:
            z_outliers = pd.Series(dtype=float)
        
        # Ciddi anomaliler (her iki yöntemde de tespit edilen)
        severe = set(iqr_outliers.index) & set(z_outliers.index)
        
        col_anomaly_count = len(iqr_outliers)
        total_anomaly_count += col_anomaly_count
        
        if col_anomaly_count > 0:
            anomalies[col] = {
                "iqr_count": len(iqr_outliers),
                "zscore_count": len(z_outliers),
                "severe_count": len(severe),
                "anomaly_pct": round(len(iqr_outliers) / len(vals) * 100, 1),
                "normal_range": f"{round(float(lower_iqr), 2)} — {round(float(upper_iqr), 2)}",
                "mean": round(float(mean_val), 2),
                "std": round(float(std_val), 2),
                "top_anomalies": sorted([round(float(v), 2) for v in iqr_outliers.values], reverse=True)[:5],
                "severity": "Kritik" if len(severe) > 0 else "Uyarı" if len(iqr_outliers) > len(vals) * 0.05 else "Bilgi",
            }
    
    return {
        "success": True,
        "total_anomalies": total_anomaly_count,
        "columns_with_anomalies": len(anomalies),
        "total_columns_checked": len(num_cols[:8]),
        "anomaly_details": anomalies,
        "overall_health": "İyi" if total_anomaly_count < 5 else "Dikkat" if total_anomaly_count < 20 else "Sorunlu",
    }


# ══════════════════════════════════════════════════════════════
# 6c. KORELASYON ANALİZİ (Detaylı)
# ══════════════════════════════════════════════════════════════

def correlation_analysis(df: pd.DataFrame) -> dict:
    """Detaylı korelasyon matrisi ve ilişki önerileri"""
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if len(num_cols) < 2:
        return {"success": False, "error": "En az 2 sayısal sütun gerekli"}
    
    corr_matrix = df[num_cols[:10]].corr()
    
    # Tüm ilişkileri sınıfla
    relationships = []
    for i in range(len(corr_matrix.columns)):
        for j in range(i + 1, len(corr_matrix.columns)):
            val = corr_matrix.iloc[i, j]
            if pd.isna(val):
                continue
            abs_val = abs(val)
            strength = (
                "Çok Güçlü" if abs_val > 0.9 else
                "Güçlü" if abs_val > 0.7 else
                "Orta" if abs_val > 0.5 else
                "Zayıf" if abs_val > 0.3 else
                "Çok Zayıf"
            )
            relationships.append({
                "col1": corr_matrix.columns[i],
                "col2": corr_matrix.columns[j],
                "correlation": round(val, 3),
                "strength": strength,
                "direction": "Pozitif" if val > 0 else "Negatif",
                "actionable": abs_val > 0.5,
            })
    
    # Önemlilere göre sırala
    relationships.sort(key=lambda x: abs(x["correlation"]), reverse=True)
    
    # Her sütunun en güçlü ilişkisi
    best_pairs = {}
    for col in num_cols[:10]:
        col_rels = [r for r in relationships if r["col1"] == col or r["col2"] == col]
        if col_rels:
            best = col_rels[0]
            partner = best["col2"] if best["col1"] == col else best["col1"]
            best_pairs[col] = {"partner": partner, "correlation": best["correlation"], "strength": best["strength"]}
    
    return {
        "success": True,
        "matrix": {str(k): {str(k2): round(v2, 3) for k2, v2 in v.items()} for k, v in corr_matrix.to_dict().items()},
        "relationships": relationships[:20],
        "strong_count": sum(1 for r in relationships if abs(r["correlation"]) > 0.7),
        "moderate_count": sum(1 for r in relationships if 0.5 < abs(r["correlation"]) <= 0.7),
        "best_pairs": best_pairs,
        "total_pairs": len(relationships),
    }


# ══════════════════════════════════════════════════════════════
# 6d. DAĞILIM ANALİZİ
# ══════════════════════════════════════════════════════════════

def distribution_analysis(df: pd.DataFrame) -> dict:
    """Veri dağılım profili — çarpıklık, basıklık, yüzdelikler"""
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if not num_cols:
        return {"success": False, "error": "Sayısal sütun bulunamadı"}
    
    distributions = {}
    for col in num_cols[:8]:
        vals = df[col].dropna()
        if len(vals) < 5:
            continue
        
        try:
            skew = float(vals.skew())
            kurt = float(vals.kurtosis())
            
            # Dağılım tipi belirleme
            if abs(skew) < 0.5 and abs(kurt) < 1:
                dist_type = "Normal (Simetrik)"
            elif skew > 1:
                dist_type = "Güçlü Sağa Çarpık"
            elif skew > 0.5:
                dist_type = "Hafif Sağa Çarpık"
            elif skew < -1:
                dist_type = "Güçlü Sola Çarpık"
            elif skew < -0.5:
                dist_type = "Hafif Sola Çarpık"
            elif kurt > 3:
                dist_type = "Sivri (Leptokurtik)"
            elif kurt < -1:
                dist_type = "Basık (Platykurtik)"
            else:
                dist_type = "Normal Civarı"
            
            # Yüzdelik değerler
            percentiles = {
                "P5": round(float(vals.quantile(0.05)), 2),
                "P10": round(float(vals.quantile(0.10)), 2),
                "P25": round(float(vals.quantile(0.25)), 2),
                "P50": round(float(vals.quantile(0.50)), 2),
                "P75": round(float(vals.quantile(0.75)), 2),
                "P90": round(float(vals.quantile(0.90)), 2),
                "P95": round(float(vals.quantile(0.95)), 2),
            }
            
            # Histogram benzeri bant analizi
            bands = {}
            min_val, max_val = float(vals.min()), float(vals.max())
            if max_val > min_val:
                band_width = (max_val - min_val) / 5
                for i in range(5):
                    low = min_val + i * band_width
                    high = low + band_width
                    count = int(((vals >= low) & (vals < high if i < 4 else vals <= high)).sum())
                    bands[f"{round(low, 1)}-{round(high, 1)}"] = count
            
            distributions[col] = {
                "distribution_type": dist_type,
                "skewness": round(skew, 3),
                "kurtosis": round(kurt, 3),
                "mean": round(float(vals.mean()), 2),
                "median": round(float(vals.median()), 2),
                "mode": round(float(vals.mode().iloc[0]), 2) if len(vals.mode()) > 0 else None,
                "std": round(float(vals.std()), 2),
                "cv_pct": round(float(vals.std() / vals.mean() * 100), 1) if vals.mean() != 0 else 0,
                "percentiles": percentiles,
                "range": round(max_val - min_val, 2),
                "iqr": round(float(vals.quantile(0.75) - vals.quantile(0.25)), 2),
                "bands": bands,
            }
        except Exception:
            continue
    
    return {"success": True, "distributions": distributions, "columns_analyzed": len(distributions)}


# ══════════════════════════════════════════════════════════════
# 6e. TAHMİNLEME (Basit Projeksiyon)
# ══════════════════════════════════════════════════════════════

def forecast_analysis(df: pd.DataFrame, date_col: str = None, value_col: str = None, periods: int = 5) -> dict:
    """Hareketli ortalama ve lineer regresyon tabanlı basit tahminleme"""
    
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
    
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if not value_col:
        value_col = num_cols[0] if num_cols else None
    
    if not value_col:
        return {"success": False, "error": "Sayısal değer sütunu bulunamadı"}
    
    try:
        df_sorted = df.copy()
        df_sorted[date_col] = pd.to_datetime(df_sorted[date_col])
        df_sorted = df_sorted.sort_values(date_col)
        
        vals = df_sorted[value_col].dropna()
        if len(vals) < 5:
            return {"success": False, "error": "Tahmin için en az 5 veri noktası gerekli"}
        
        x = np.arange(len(vals))
        
        # Lineer regresyon
        coeffs = np.polyfit(x, vals.values, 1)
        slope, intercept = coeffs
        
        # R² hesapla
        y_pred = slope * x + intercept
        ss_res = np.sum((vals.values - y_pred) ** 2)
        ss_tot = np.sum((vals.values - vals.mean()) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        # Gelecek tahminleri
        future_x = np.arange(len(vals), len(vals) + periods)
        linear_forecast = [round(float(slope * xi + intercept), 2) for xi in future_x]
        
        # Hareketli ortalama tabanlı tahmin
        window = min(5, len(vals) // 2)
        ma_last = float(vals.rolling(window=window).mean().iloc[-1]) if window > 0 else float(vals.mean())
        ma_trend = float(slope)  # Trendi ekle
        ma_forecast = [round(ma_last + ma_trend * (i + 1), 2) for i in range(periods)]
        
        # Güven seviyesi
        confidence = "Yüksek" if r_squared > 0.7 else "Orta" if r_squared > 0.4 else "Düşük"
        
        return {
            "success": True,
            "value_column": value_col,
            "data_points": len(vals),
            "forecast_periods": periods,
            "linear_forecast": linear_forecast,
            "ma_forecast": ma_forecast,
            "trend_slope": round(float(slope), 4),
            "r_squared": round(r_squared, 3),
            "confidence": confidence,
            "current_value": round(float(vals.iloc[-1]), 2),
            "predicted_change_pct": round(((linear_forecast[-1] - float(vals.iloc[-1])) / float(vals.iloc[-1])) * 100, 1) if vals.iloc[-1] != 0 else 0,
            "method": "Lineer Regresyon + Hareketli Ortalama",
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════
# 6f. PARETO / ABC ANALİZİ
# ══════════════════════════════════════════════════════════════

def pareto_analysis(df: pd.DataFrame, value_col: str = None, label_col: str = None) -> dict:
    """80/20 kuralı ve ABC sınıflandırması"""
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = [c for c in df.columns if df[c].dtype == 'object']
    
    if not value_col:
        value_col = num_cols[0] if num_cols else None
    if not label_col:
        label_col = cat_cols[0] if cat_cols else None
    
    if not value_col:
        return {"success": False, "error": "Sayısal sütun bulunamadı"}
    
    try:
        # Label yoksa index kullan
        if label_col:
            grouped = df.groupby(label_col)[value_col].sum().sort_values(ascending=False)
        else:
            grouped = df[value_col].sort_values(ascending=False)
        
        total = grouped.sum()
        if total == 0:
            return {"success": False, "error": "Toplam değer 0"}
        
        cumulative = grouped.cumsum()
        cumulative_pct = (cumulative / total * 100).round(1)
        
        # ABC Sınıflandırması
        a_items = []  # %80'e kadar
        b_items = []  # %80-95
        c_items = []  # %95-100
        
        for idx, pct in cumulative_pct.items():
            item = {
                "label": str(idx),
                "value": round(float(grouped[idx]), 2),
                "pct": round(float(grouped[idx] / total * 100), 1),
                "cumulative_pct": float(pct),
            }
            if pct <= 80:
                a_items.append(item)
            elif pct <= 95:
                b_items.append(item)
            else:
                c_items.append(item)
        
        # Tam A sınırını kontrol et (son A öğesi %80'i geçebilir)
        if not a_items and b_items:
            a_items.append(b_items.pop(0))
        
        # 80/20 kuralı kontrolü
        top_20_pct_count = max(1, int(len(grouped) * 0.2))
        top_20_value = grouped.head(top_20_pct_count).sum()
        top_20_contribution = round(float(top_20_value / total * 100), 1)
        
        return {
            "success": True,
            "value_column": value_col,
            "label_column": label_col,
            "total_items": len(grouped),
            "total_value": round(float(total), 2),
            "pareto_rule": {
                "top_20_pct_items": top_20_pct_count,
                "top_20_contribution_pct": top_20_contribution,
                "is_pareto": top_20_contribution >= 65,  # Kabaca 80/20'ye yakın
            },
            "abc": {
                "A": {"count": len(a_items), "items": a_items[:10], "description": "Yüksek değer (%80 katkı)"},
                "B": {"count": len(b_items), "items": b_items[:10], "description": "Orta değer (%80-95 katkı)"},
                "C": {"count": len(c_items), "items": c_items[:10], "description": "Düşük değer (%95-100 katkı)"},
            },
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════
# 6g. VERİ KALİTESİ DENETİMİ
# ══════════════════════════════════════════════════════════════

def data_quality_analysis(df: pd.DataFrame) -> dict:
    """Kapsamlı veri kalitesi değerlendirmesi"""
    total_cells = df.shape[0] * df.shape[1]
    
    # 1. Eksik veri analizi
    missing = {}
    total_missing = 0
    for col in df.columns:
        null_count = int(df[col].isnull().sum())
        if null_count > 0:
            missing[col] = {
                "count": null_count,
                "pct": round(null_count / len(df) * 100, 1),
                "severity": "Kritik" if null_count / len(df) > 0.3 else "Uyarı" if null_count / len(df) > 0.1 else "Düşük",
            }
            total_missing += null_count
    
    # 2. Tekrarlayan satırlar
    duplicates = int(df.duplicated().sum())
    dup_pct = round(duplicates / len(df) * 100, 1) if len(df) > 0 else 0
    
    # 3. Sütun tip tutarlılığı
    type_issues = {}
    for col in df.columns:
        if df[col].dtype == 'object':
            # Sayı gibi görünen metin var mı?
            numeric_like = df[col].dropna().apply(lambda x: str(x).replace(',', '.').replace(' ', '').replace('-', '')).str.match(r'^\d+\.?\d*$')
            numeric_count = int(numeric_like.sum()) if len(numeric_like) > 0 else 0
            total_non_null = int(df[col].notna().sum())
            if total_non_null > 0 and numeric_count / total_non_null > 0.7:
                type_issues[col] = {
                    "issue": "Sayısal veri metin olarak saklanmış",
                    "numeric_ratio": round(numeric_count / total_non_null * 100, 1),
                }
    
    # 4. Boş/whitespace satırlar
    whitespace_issues = {}
    for col in df.columns:
        if df[col].dtype == 'object':
            ws_count = int(df[col].dropna().apply(lambda x: str(x).strip() == '').sum())
            if ws_count > 0:
                whitespace_issues[col] = ws_count
    
    # 5. Genel kalite skoru
    completeness = round((1 - total_missing / total_cells) * 100, 1) if total_cells > 0 else 100
    uniqueness = round((1 - duplicates / len(df)) * 100, 1) if len(df) > 0 else 100
    consistency = round((1 - len(type_issues) / len(df.columns)) * 100, 1) if len(df.columns) > 0 else 100
    quality_score = round((completeness * 0.4 + uniqueness * 0.3 + consistency * 0.3), 1)
    
    return {
        "success": True,
        "rows": len(df),
        "columns": len(df.columns),
        "total_cells": total_cells,
        "quality_score": quality_score,
        "quality_grade": "A" if quality_score >= 90 else "B" if quality_score >= 75 else "C" if quality_score >= 60 else "D" if quality_score >= 40 else "F",
        "completeness": {
            "score": completeness,
            "total_missing": total_missing,
            "columns_with_missing": len(missing),
            "details": missing,
        },
        "uniqueness": {
            "score": uniqueness,
            "duplicate_rows": duplicates,
            "duplicate_pct": dup_pct,
        },
        "consistency": {
            "score": consistency,
            "type_issues": type_issues,
            "whitespace_issues": whitespace_issues,
        },
        "recommendations": _quality_recommendations(completeness, uniqueness, consistency, missing, type_issues),
    }


def _quality_recommendations(completeness, uniqueness, consistency, missing, type_issues) -> list:
    """Veri kalitesi tavsiyelerini oluştur"""
    recs = []
    if completeness < 90:
        worst_cols = sorted(missing.items(), key=lambda x: x[1]["count"], reverse=True)[:3]
        cols_str = ", ".join(f"{c} (%{v['pct']})" for c, v in worst_cols)
        recs.append(f"Eksik veri temizliği: {cols_str} sütunlarındaki boşlukları doldurun veya çıkarın")
    if uniqueness < 95:
        recs.append(f"Tekrarlayan satırları kaldırın (toplam tekrar oranı: %{round(100-uniqueness, 1)})")
    if consistency < 90:
        for col, info in type_issues.items():
            recs.append(f"'{col}' sütununu sayısal tipe dönüştürün (%{info['numeric_ratio']} sayısal)")
    if completeness >= 90 and uniqueness >= 95 and consistency >= 90:
        recs.append("Veri kalitesi genel olarak iyi durumda ✓")
    return recs


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
        - "anomaly": Anomali / aykırı değer tespiti
        - "correlation": Korelasyon analizi
        - "distribution": Dağılım analizi
        - "forecast": Tahminleme / projeksiyon
        - "pareto": Pareto ABC analizi
        - "quality": Veri kalitesi denetimi
    """
    
    discovery = discover_data(df)
    
    # Temel veri bilgisi — tüm tipler için ortak
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
    
    # ── TİP-SPESİFİK VERİ EKLEMELERİ ──
    
    # İstatistiksel Analiz (tüm tipler için temel)
    stats = statistical_analysis(df)
    
    if stats.get("strong_correlations") and analysis_type in ("full", "correlation", "report", "recommend"):
        prompt += "\n### Korelasyonlar (Güçlü İlişkiler):\n"
        for corr in stats["strong_correlations"]:
            prompt += f"- **{corr['col1']}** ↔ **{corr['col2']}**: {corr['correlation']} ({corr['strength']} {corr['direction']})\n"
    
    if stats.get("outliers") and analysis_type in ("full", "anomaly", "quality", "report"):
        prompt += "\n### Aykırı Değerler:\n"
        for col, info in stats["outliers"].items():
            prompt += f"- **{col}**: {info['count']} aykırı değer (%{info['percentage']}), normal aralık: {info['lower_bound']} - {info['upper_bound']}\n"
    
    # Pivot Tablo
    if analysis_type in ("full", "pivot") and discovery["categorical_columns"] and discovery["numeric_columns"]:
        pivot_result = smart_pivot(df)
        if pivot_result.get("success"):
            prompt += f"\n### Pivot Tablo:\n```\n{pivot_result['table_str'][:2000]}\n```\n"
    
    # Trend Analizi
    if analysis_type in ("full", "trend", "forecast") and discovery["date_columns"]:
        trend = trend_analysis(df)
        if trend.get("success"):
            prompt += f"\n### Trend Analizi ({trend['date_range']}):\n"
            for col, t_info in trend.get("trends", {}).items():
                prompt += f"- **{col}**: {t_info['direction']} (%{t_info['change_pct']}), Momentum: {t_info.get('momentum', '-')}, Volatilite: %{t_info.get('volatility_pct', 0)}, Son: {t_info['latest_value']}\n"
                if t_info.get("moving_averages"):
                    for ma_name, ma_info in t_info["moving_averages"].items():
                        prompt += f"  - {ma_name}: {ma_info['current']} ({ma_info['trend']})\n"
                if t_info.get("growth_rates"):
                    for period, rate in t_info["growth_rates"].items():
                        prompt += f"  - {period}: %{rate} büyüme\n"
    
    # Karşılaştırma
    if analysis_type in ("full", "compare") and discovery["categorical_columns"]:
        comp = comparison_analysis(df)
        if comp.get("success"):
            prompt += f"\n### Grup Karşılaştırması ({comp['group_column']}, {comp['group_count']} grup):\n"
            for col, cinfo in comp.get("summary", {}).items():
                prompt += f"- **{col}**: En iyi={cinfo['best_group']}, En düşük={cinfo['worst_group']}, Fark=%{cinfo.get('gap_pct', 0)}\n"
                if cinfo.get("medians"):
                    prompt += f"  Medyanlar: {', '.join(f'{k}={v}' for k, v in list(cinfo['medians'].items())[:5])}\n"
    
    # Top-N
    if analysis_type in ("full", "report", "pareto") and discovery["numeric_columns"]:
        top_n = top_n_analysis(df, n=5)
        if top_n:
            prompt += "\n### En Yüksek / En Düşük Değerler:\n"
            for col, data in list(top_n.items())[:3]:
                prompt += f"**{col} — Top 5:**\n"
                for item in data["top"][:5]:
                    vals_str = [f"{k}: {v}" for k, v in item.items()]
                    prompt += f"  - {', '.join(vals_str)}\n"
    
    # ── YENİ TİPLER İÇİN EK VERİ ──
    
    # Anomali Tespiti
    if analysis_type == "anomaly":
        anom = anomaly_detection(df)
        if anom.get("success"):
            prompt += f"\n### Anomali Tespiti (Genel Sağlık: {anom['overall_health']}):\n"
            prompt += f"- Toplam anomali: {anom['total_anomalies']}, Etkilenen sütun: {anom['columns_with_anomalies']}/{anom['total_columns_checked']}\n"
            for col, det in anom.get("anomaly_details", {}).items():
                prompt += f"- **{col}** [{det['severity']}]: {det['iqr_count']} IQR, {det['zscore_count']} Z-Score aykırı. Normal aralık: {det['normal_range']}\n"
                if det.get("top_anomalies"):
                    prompt += f"  En büyük anomaliler: {', '.join(str(v) for v in det['top_anomalies'][:5])}\n"
    
    # Korelasyon Analizi
    if analysis_type == "correlation":
        corr = correlation_analysis(df)
        if corr.get("success"):
            prompt += f"\n### Detaylı Korelasyon Analizi ({corr['total_pairs']} çift incelendi):\n"
            prompt += f"- Güçlü ilişki: {corr['strong_count']}, Orta ilişki: {corr['moderate_count']}\n"
            for rel in corr.get("relationships", [])[:10]:
                emoji = "🔴" if abs(rel["correlation"]) > 0.7 else "🟡" if abs(rel["correlation"]) > 0.5 else "⚪"
                prompt += f"  {emoji} **{rel['col1']}** ↔ **{rel['col2']}**: {rel['correlation']} ({rel['strength']}, {rel['direction']})\n"
    
    # Dağılım Analizi
    if analysis_type == "distribution":
        dist = distribution_analysis(df)
        if dist.get("success"):
            prompt += f"\n### Dağılım Analizi ({dist['columns_analyzed']} sütun):\n"
            for col, d in dist.get("distributions", {}).items():
                prompt += f"- **{col}**: {d['distribution_type']}, Ort={d['mean']}, Medyan={d['median']}, Std={d['std']}, CV=%{d['cv_pct']}\n"
                prompt += f"  Çarpıklık={d['skewness']}, Basıklık={d['kurtosis']}, IQR={d['iqr']}\n"
                prompt += f"  Yüzdelikler: P25={d['percentiles']['P25']}, P50={d['percentiles']['P50']}, P75={d['percentiles']['P75']}, P95={d['percentiles']['P95']}\n"
    
    # Tahminleme
    if analysis_type == "forecast":
        fc = forecast_analysis(df)
        if fc.get("success"):
            prompt += f"\n### Tahminleme ({fc['method']}, R²={fc['r_squared']}, Güven: {fc['confidence']}):\n"
            prompt += f"- Mevcut değer: {fc['current_value']}, Eğim: {fc['trend_slope']}\n"
            prompt += f"- Lineer tahmin (sonraki {fc['forecast_periods']} dönem): {', '.join(str(v) for v in fc['linear_forecast'])}\n"
            prompt += f"- Hareketli Ort. tahmin: {', '.join(str(v) for v in fc['ma_forecast'])}\n"
            prompt += f"- Beklenen değişim: %{fc['predicted_change_pct']}\n"
    
    # Pareto / ABC
    if analysis_type == "pareto":
        par = pareto_analysis(df)
        if par.get("success"):
            pr = par["pareto_rule"]
            prompt += f"\n### Pareto / ABC Analizi ({par['total_items']} öğe, Toplam: {par['total_value']}):\n"
            prompt += f"- **80/20 Kuralı**: Üst %20 ({pr['top_20_pct_items']} öğe) toplam değerin %{pr['top_20_contribution_pct']}'ini oluşturuyor {'✓ Pareto geçerli' if pr['is_pareto'] else '✗ Pareto geçerli değil'}\n"
            for grade in ["A", "B", "C"]:
                abc = par["abc"][grade]
                items_str = ", ".join(f"{it['label']}({it['pct']}%)" for it in abc["items"][:5])
                prompt += f"- **Sınıf {grade}** ({abc['count']} öğe): {abc['description']}. {items_str}\n"
    
    # Veri Kalitesi
    if analysis_type == "quality":
        qual = data_quality_analysis(df)
        if qual.get("success"):
            prompt += f"\n### Veri Kalitesi Raporu (Skor: {qual['quality_score']}/100, Not: {qual['quality_grade']}):\n"
            prompt += f"- Bütünlük: %{qual['completeness']['score']} ({qual['completeness']['total_missing']} eksik hücre)\n"
            prompt += f"- Teksillik: %{qual['uniqueness']['score']} ({qual['uniqueness']['duplicate_rows']} tekrar satır)\n"
            prompt += f"- Tutarlılık: %{qual['consistency']['score']} ({len(qual['consistency']['type_issues'])} tip sorunu)\n"
            if qual.get("recommendations"):
                prompt += "- **Tavsiyeler**:\n"
                for rec in qual["recommendations"]:
                    prompt += f"  • {rec}\n"
    
    # Veri örneği
    sample_rows = min(5, len(df))
    prompt += f"\n### Veri Örneği (İlk {sample_rows} Satır):\n"
    prompt += f"```\n{df.head(sample_rows).to_string()}\n```\n"
    
    # ── TİP-SPESİFİK GÖREV TALİMATLARI ──
    
    if analysis_type == "pivot":
        prompt += """
**GÖREV**: Yukarıdaki pivot tablo verilerini detaylı analiz et:
1. Hangi kategoriler öne çıkıyor ve neden?
2. Kategoriler arası performans farkları ve oranları
3. En dikkat çekici çapraz kesişimler
4. Yöneticiler için karar önerileri
Tabloları ve sayısal karşılaştırmaları mutlaka kullan."""

    elif analysis_type == "trend":
        prompt += """
**GÖREV**: Trend analizini profesyonelce yorumla:
1. Ana trend yönü ve gücü (momentum değerlendirmesi)
2. Hareketli ortalamaların gösterdiği kısa/uzun vadeli sinyaller
3. Volatilite ve risk değerlendirmesi
4. Dönemsel büyüme oranlarının analizi
5. Mevsimsel veya döngüsel paternler varsa belirt
6. Gelecek dönem için beklentiler ve öneriler
Her bulguyu verilerle destekle."""

    elif analysis_type == "compare":
        prompt += """
**GÖREV**: Grupları kapsamlı karşılaştır:
1. En iyi ve en kötü performans gösteren gruplar (neden?)
2. Medyan vs ortalama farklarının gösterdiği dağılım özellikleri
3. Gruplar arası fark yüzdeleri ve anlamlılığı
4. Genel ortalamadan sapma analizi
5. Standart sapma ile tutarlılık değerlendirmesi
6. Her grup için spesifik aksiyon önerileri"""

    elif analysis_type == "recommend":
        prompt += """
**GÖREV**: Bu verilere dayanarak somut, uygulanabilir ve önceliklendirilmiş TAVSİYELER sun:
1. **Acil Aksiyonlar** (0-1 ay): Hemen yapılması gerekenler
2. **Kısa Vadeli** (1-3 ay): Planlı iyileştirmeler
3. **Uzun Vadeli** (3-12 ay): Stratejik dönüşümler
Her tavsiyeyi:
- Verilerle destekle (hangi sayı/oran bunu gerektiriyor?)
- Beklenen etkiyi belirt
- Risk/maliyet analizi yap
- Öncelik seviyesi ata (Kritik/Yüksek/Orta/Düşük)
En az 5-7 madde sun."""

    elif analysis_type == "report":
        prompt += """
**GÖREV**: Profesyonel bir YÖNETİCİ RAPORU oluştur:
1. **📋 Yönetici Özeti** (3-5 cümle, en kritik bulgular)
2. **📊 Temel Metrikler** (KPI tablosu formatında)
3. **📈 Detaylı Bulgular** (her kategori/metrik için derinlemesine analiz)
4. **🔍 Karşılaştırmalı Analiz** (dönemler arası, gruplar arası)
5. **⚠️ Risk ve Uyarılar** (dikkat edilmesi gerekenler)
6. **✅ Aksiyon Planı** (somut adımlar, sorumlular, zaman çizelgesi)
7. **📌 Sonuç** (genel değerlendirme)
Tüm bölümlerde sayısal veriler kullan. Tablolarla destekle."""

    elif analysis_type == "summary":
        prompt += """
**GÖREV**: Bu veri setini 8-10 cümlelik etkili bir özete dönüştür:
1. Verinin ne hakkında olduğu ve kapsamı
2. En çarpıcı 3 sayısal bulgu
3. Dikkat çekici pattern veya anomali varsa
4. Genel durum değerlendirmesi (iyi/kötü/kritik)
5. Tek cümlelik sonuç ve öneri
Kısa, öz ama bilgi dolu olsun."""

    elif analysis_type == "anomaly":
        prompt += """
**GÖREV**: Anomali ve aykırı değer tespitini detaylı raporla:
1. Tespit edilen anomalilerin listesi ve ciddiyet seviyeleri
2. Her anomalinin olası nedenleri (veri hatası mı, gerçek sapma mı?)
3. Hangi sütunlar en fazla anomali içeriyor ve bunun anlamı
4. Anomalilerin iş süreçlerine potansiyel etkisi
5. Temizleme/düzeltme tavsiyeler (hangileri silinmeli, hangileri araştırılmalı)
6. Anomalilerin kök neden analizi
Her bulguyu IQR ve Z-Score değerleriyle destekle."""

    elif analysis_type == "correlation":
        prompt += """
**GÖREV**: Korelasyon ilişkilerini iş perspektifinden yorumla:
1. En güçlü pozitif ve negatif ilişkiler ve ne anlama geldikleri
2. Beklenmeyen veya ilginç ilişkiler (neden-sonuç tartışması)
3. İş kararlarında kullanılabilecek ilişki önerileri
4. Korelasyon ≠ nedensellik uyarısı ile yorumlar
5. Birbirine bağımlı değişken grupları (cluster)
6. Stratejik öneriler: "X'i artırırsanız Y de artma/azalma eğiliminde"
Her ilişkiyi korelasyon katsayısıyla birlikte sun."""

    elif analysis_type == "distribution":
        prompt += """
**GÖREV**: Veri dağılımlarını detaylı analiz et:
1. Her sütunun dağılım tipi ve bunun anlamı
2. Normal dağılımdan sapmaların yorumu (çarpıklık, basıklık)
3. Yüzdelik dilim analizi — değerlerin nerede yoğunlaştığı
4. Ortalama vs Medyan farkının gösterdiği dengesizlik
5. Değişkenlik katsayısı (CV) ile tutarlılık değerlendirmesi
6. Verinin hangi aralıklarda yoğunlaştığı ve uç değerler
İstatistiksel terimleri anlaşılır iş diline çevir."""

    elif analysis_type == "forecast":
        prompt += """
**GÖREV**: Tahminleme sonuçlarını yorumla ve iş önerileri sun:
1. Mevcut trendin gücü ve güvenilirliği (R² ve güven seviyesi)
2. Lineer ve hareketli ortalama tahminlerinin karşılaştırması
3. Tahmin edilen değişim yönü ve büyüklüğü
4. En iyi/en kötü senaryo tahminleri
5. Tahminlerin kısıtlamaları ve varsayımları
6. Bu tahminlere göre alınması gereken stratejik aksiyonlar
⚠️ Basit modeller olduğunu belirt, kesin olmadığını vurgula."""

    elif analysis_type == "pareto":
        prompt += """
**GÖREV**: Pareto/ABC analizini iş değeri perspektifinden yorumla:
1. 80/20 kuralının bu veride geçerli olup olmadığı
2. A sınıfı öğeler — neden en değerli, nasıl büyütülür?
3. B sınıfı öğeler — A'ya çıkma potansiyeli olanlar
4. C sınıfı öğeler — optimize edilmeli mi, kesilmeli mi?
5. Kaynak dağılımı önerileri (bütçe, zaman, personel)
6. Somut aksiyon planı: "ÖğeX'e %Y daha fazla yatırım yapın"
Her öneriyi katkı yüzdeleriyle destekle."""

    elif analysis_type == "quality":
        prompt += """
**GÖREV**: Veri kalitesi denetim raporunu profesyonelce sun:
1. Genel kalite skoru ve notunun değerlendirmesi
2. Bütünlük — eksik verilerin etkisi ve çözüm önerileri
3. Teksillik — tekrar satırların neden oluştuğu ve temizleme stratejisi
4. Tutarlılık — tip uyumsuzlukları ve düzeltme adımları
5. Öncelikli iyileştirme planı (en kritikten en az kritiğe)
6. Veri kalitesi iyileştikten sonra beklenen analiz doğruluğu artışı
Bu raporu veri mühendisliği ekibine sunulacakmış gibi yaz."""

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
