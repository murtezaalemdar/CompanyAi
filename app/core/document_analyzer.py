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

# Opsiyonel: statsmodels istatistik testleri
try:
    from scipy import stats as scipy_stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

# Opsiyonel: forecasting motoru (ARIMA, Holt-Winters)
try:
    from app.core.forecasting import (
        arima_forecast,
        holt_linear_trend,
        holt_winters_seasonal,
        exponential_smoothing,
        STATSMODELS_AVAILABLE,
    )
    FORECASTING_AVAILABLE = True
except ImportError:
    FORECASTING_AVAILABLE = False
    STATSMODELS_AVAILABLE = False


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
    """Pro karşılaştırma — medyan, std, fark yüzdesi, t-test/ANOVA istatistiksel testler"""
    
    if not group_col:
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
    
    result = {
        "success": True,
        "group_column": group_col,
        "groups": [str(g) for g in df[group_col].unique()],
        "group_count": df[group_col].nunique(),
        "summary": {},
        "statistical_tests": {},
    }
    
    groups = df[group_col].unique()
    
    for col in num_cols[:5]:
        group_means = df.groupby(group_col)[col].mean().sort_values(ascending=False)
        group_medians = df.groupby(group_col)[col].median().sort_values(ascending=False)
        group_sums = df.groupby(group_col)[col].sum().sort_values(ascending=False)
        group_counts = df.groupby(group_col)[col].count()
        group_stds = df.groupby(group_col)[col].std()
        
        # Gruplar arası fark yüzdesi
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
        
        # İstatistiksel testler (scipy varsa)
        if SCIPY_AVAILABLE and len(groups) >= 2:
            group_data = [df[df[group_col] == g][col].dropna().values for g in groups if len(df[df[group_col] == g][col].dropna()) >= 2]
            
            if len(group_data) >= 2:
                test_result = {}
                if len(group_data) == 2:
                    # 2 grup → t-test
                    try:
                        t_stat, p_val = scipy_stats.ttest_ind(group_data[0], group_data[1], equal_var=False)
                        # Effect size (Cohen's d)
                        pooled_std = np.sqrt((np.std(group_data[0])**2 + np.std(group_data[1])**2) / 2)
                        cohens_d = abs(np.mean(group_data[0]) - np.mean(group_data[1])) / pooled_std if pooled_std > 0 else 0
                        
                        test_result = {
                            "test": "Welch t-test",
                            "statistic": round(float(t_stat), 4),
                            "p_value": round(float(p_val), 4),
                            "significant": float(p_val) < 0.05,
                            "cohens_d": round(float(cohens_d), 3),
                            "effect_size": "Büyük" if cohens_d > 0.8 else "Orta" if cohens_d > 0.5 else "Küçük" if cohens_d > 0.2 else "İhmal Edilebilir",
                            "interpretation": f"Gruplar arası fark {'istatistiksel olarak anlamlı ✓' if float(p_val) < 0.05 else 'anlamlı değil ✗'} (p={round(float(p_val), 4)})",
                        }
                    except Exception:
                        pass
                else:
                    # 3+ grup → ANOVA
                    try:
                        f_stat, p_val = scipy_stats.f_oneway(*group_data)
                        # Eta-squared (etki büyüklüğü)
                        all_data = np.concatenate(group_data)
                        grand_mean = np.mean(all_data)
                        ss_between = sum(len(g) * (np.mean(g) - grand_mean)**2 for g in group_data)
                        ss_total = np.sum((all_data - grand_mean)**2)
                        eta_sq = ss_between / ss_total if ss_total > 0 else 0
                        
                        test_result = {
                            "test": "One-way ANOVA",
                            "statistic": round(float(f_stat), 4),
                            "p_value": round(float(p_val), 4),
                            "significant": float(p_val) < 0.05,
                            "eta_squared": round(float(eta_sq), 3),
                            "effect_size": "Büyük" if eta_sq > 0.14 else "Orta" if eta_sq > 0.06 else "Küçük",
                            "interpretation": f"Gruplar arası fark {'istatistiksel olarak anlamlı ✓' if float(p_val) < 0.05 else 'anlamlı değil ✗'} (p={round(float(p_val), 4)})",
                        }
                    except Exception:
                        pass
                
                if test_result:
                    result["statistical_tests"][col] = test_result
    
    return result


# ══════════════════════════════════════════════════════════════
# 6b. ANOMALİ TESPİTİ (IQR + Z-Score)
# ══════════════════════════════════════════════════════════════

def anomaly_detection(df: pd.DataFrame) -> dict:
    """Pro anomali tespiti — IQR, Z-Score, Rolling Window, Modified Z-Score, Grubbs testi"""
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if not num_cols:
        return {"success": False, "error": "Sayısal sütun bulunamadı"}
    
    anomalies = {}
    total_anomaly_count = 0
    
    for col in num_cols[:8]:
        vals = df[col].dropna()
        if len(vals) < 10:
            continue
        
        # 1) IQR yöntemi
        Q1 = vals.quantile(0.25)
        Q3 = vals.quantile(0.75)
        IQR = Q3 - Q1
        lower_iqr = Q1 - 1.5 * IQR
        upper_iqr = Q3 + 1.5 * IQR
        iqr_outliers = vals[(vals < lower_iqr) | (vals > upper_iqr)]
        
        # 2) Z-Score yöntemi
        mean_val = vals.mean()
        std_val = vals.std()
        if std_val > 0:
            z_scores = np.abs((vals - mean_val) / std_val)
            z_outliers = vals[z_scores > 2.5]
        else:
            z_outliers = pd.Series(dtype=float)
        
        # 3) Modified Z-Score (MAD tabanlı — medyan bazlı, daha robust)
        median_val = vals.median()
        mad = np.median(np.abs(vals - median_val))
        modified_z_outliers = pd.Series(dtype=float)
        if mad > 0:
            modified_z = 0.6745 * (vals - median_val) / mad
            modified_z_outliers = vals[np.abs(modified_z) > 3.5]
        
        # 4) Rolling Window anomali (veri sıralıysa — trend-adjusted)
        rolling_anomalies = pd.Series(dtype=float)
        if len(vals) >= 20:
            window = min(max(int(len(vals) * 0.1), 5), 50)
            rolling_mean = vals.rolling(window=window, center=True, min_periods=3).mean()
            rolling_std = vals.rolling(window=window, center=True, min_periods=3).std()
            valid_std = rolling_std.fillna(std_val)
            valid_mean = rolling_mean.fillna(mean_val)
            deviations = np.abs(vals - valid_mean)
            threshold = valid_std * 2.5
            threshold = threshold.replace(0, std_val * 2.5)
            rolling_anomalies = vals[deviations > threshold]
        
        # Ciddi anomaliler (en az 3 yöntemde tespit edilen)
        all_outlier_sets = [set(iqr_outliers.index), set(z_outliers.index), set(modified_z_outliers.index)]
        if len(rolling_anomalies) > 0:
            all_outlier_sets.append(set(rolling_anomalies.index))
        
        # Her indeks kaç yöntemde yakalandı
        all_outlier_indices = set()
        for s in all_outlier_sets:
            all_outlier_indices |= s
        
        detection_counts = {}
        for idx in all_outlier_indices:
            cnt = sum(1 for s in all_outlier_sets if idx in s)
            detection_counts[idx] = cnt
        
        severe = {idx for idx, cnt in detection_counts.items() if cnt >= 3}
        moderate = {idx for idx, cnt in detection_counts.items() if cnt == 2}
        mild = {idx for idx, cnt in detection_counts.items() if cnt == 1}
        
        col_anomaly_count = len(all_outlier_indices)
        total_anomaly_count += col_anomaly_count
        
        # Grubbs testi (scipy varsa — en uç değer istatistiksel test)
        grubbs_result = None
        if SCIPY_AVAILABLE and len(vals) >= 8:
            try:
                n = len(vals)
                max_idx = np.argmax(np.abs(vals - mean_val))
                G = abs(vals.iloc[max_idx] - mean_val) / std_val if std_val > 0 else 0
                t_crit = scipy_stats.t.ppf(1 - 0.05 / (2 * n), n - 2)
                G_crit = ((n - 1) / np.sqrt(n)) * np.sqrt(t_crit**2 / (n - 2 + t_crit**2))
                grubbs_result = {
                    "test_statistic": round(float(G), 4),
                    "critical_value": round(float(G_crit), 4),
                    "extreme_value": round(float(vals.iloc[max_idx]), 2),
                    "is_outlier": float(G) > float(G_crit),
                    "interpretation": f"En uç değer {round(float(vals.iloc[max_idx]), 2)} {'istatistiksel olarak aykırı ✓' if G > G_crit else 'aykırı sayılmaz ✗'}"
                }
            except Exception:
                pass
        
        if col_anomaly_count > 0:
            col_result = {
                "methods": {
                    "iqr": {"count": len(iqr_outliers), "range": f"{round(float(lower_iqr), 2)} — {round(float(upper_iqr), 2)}"},
                    "zscore": {"count": len(z_outliers), "threshold": 2.5},
                    "modified_zscore": {"count": len(modified_z_outliers), "threshold": 3.5, "method": "MAD-based"},
                },
                "severity_breakdown": {
                    "kritik": len(severe),
                    "orta": len(moderate),
                    "hafif": len(mild),
                },
                "total_anomalies": col_anomaly_count,
                "anomaly_pct": round(col_anomaly_count / len(vals) * 100, 1),
                "stats": {"mean": round(float(mean_val), 2), "median": round(float(median_val), 2), "std": round(float(std_val), 2)},
                "top_anomalies": sorted([round(float(vals.loc[idx]), 2) for idx in list(severe | moderate)[:10]], reverse=True)[:5],
                "severity": "Kritik" if len(severe) > 0 else "Uyarı" if col_anomaly_count > len(vals) * 0.05 else "Bilgi",
            }
            if len(rolling_anomalies) > 0:
                col_result["methods"]["rolling_window"] = {"count": len(rolling_anomalies), "window_size": window, "note": "Trend-adjusted"}
            if grubbs_result:
                col_result["grubbs_test"] = grubbs_result
            anomalies[col] = col_result
    
    return {
        "success": True,
        "total_anomalies": total_anomaly_count,
        "columns_with_anomalies": len(anomalies),
        "total_columns_checked": len(num_cols[:8]),
        "anomaly_details": anomalies,
        "detection_methods": ["IQR", "Z-Score", "Modified Z-Score (MAD)", "Rolling Window", "Grubbs Test"],
        "overall_health": "İyi" if total_anomaly_count < 5 else "Dikkat" if total_anomaly_count < 20 else "Sorunlu",
    }


# ══════════════════════════════════════════════════════════════
# 6c. KORELASYON ANALİZİ (Detaylı)
# ══════════════════════════════════════════════════════════════

def correlation_analysis(df: pd.DataFrame) -> dict:
    """Pro korelasyon analizi — Pearson + Spearman + istatistiksel anlamlılık"""
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if len(num_cols) < 2:
        return {"success": False, "error": "En az 2 sayısal sütun gerekli"}
    
    cols = num_cols[:10]
    pearson_matrix = df[cols].corr(method='pearson')
    spearman_matrix = df[cols].corr(method='spearman')
    
    # Tüm ilişkileri sınıfla
    relationships = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            p_val = pearson_matrix.iloc[i, j]
            s_val = spearman_matrix.iloc[i, j]
            if pd.isna(p_val):
                continue
            
            abs_p = abs(p_val)
            abs_s = abs(s_val) if not pd.isna(s_val) else 0
            strength = (
                "Çok Güçlü" if abs_p > 0.9 else
                "Güçlü" if abs_p > 0.7 else
                "Orta" if abs_p > 0.5 else
                "Zayıf" if abs_p > 0.3 else
                "Çok Zayıf"
            )
            
            # Non-linear ilişki tespiti (Spearman > Pearson farkı)
            linearity = "Doğrusal"
            if abs_s - abs_p > 0.15:
                linearity = "Non-Doğrusal (monoton)"
            elif abs_p - abs_s > 0.15:
                linearity = "Muhtemelen non-monoton"
            
            # P-value hesapla (scipy varsa)
            p_value = None
            if SCIPY_AVAILABLE and len(df) >= 3:
                try:
                    _, p_value = scipy_stats.pearsonr(df[cols[i]].dropna(), df[cols[j]].dropna())
                    p_value = round(p_value, 4)
                except Exception:
                    pass
            
            relationships.append({
                "col1": cols[i],
                "col2": cols[j],
                "pearson": round(p_val, 3),
                "spearman": round(s_val, 3) if not pd.isna(s_val) else None,
                "strength": strength,
                "direction": "Pozitif" if p_val > 0 else "Negatif",
                "linearity": linearity,
                "p_value": p_value,
                "significant": p_value < 0.05 if p_value is not None else None,
                "actionable": abs_p > 0.5,
            })
    
    # Önemlilere göre sırala
    relationships.sort(key=lambda x: abs(x["pearson"]), reverse=True)
    
    # Her sütunun en güçlü ilişkisi
    best_pairs = {}
    for col in cols:
        col_rels = [r for r in relationships if r["col1"] == col or r["col2"] == col]
        if col_rels:
            best = col_rels[0]
            partner = best["col2"] if best["col1"] == col else best["col1"]
            best_pairs[col] = {"partner": partner, "pearson": best["pearson"], "spearman": best["spearman"], "strength": best["strength"]}
    
    return {
        "success": True,
        "pearson_matrix": {str(k): {str(k2): round(v2, 3) for k2, v2 in v.items()} for k, v in pearson_matrix.to_dict().items()},
        "spearman_matrix": {str(k): {str(k2): round(v2, 3) for k2, v2 in v.items()} for k, v in spearman_matrix.to_dict().items()},
        "relationships": relationships[:20],
        "strong_count": sum(1 for r in relationships if abs(r["pearson"]) > 0.7),
        "moderate_count": sum(1 for r in relationships if 0.5 < abs(r["pearson"]) <= 0.7),
        "nonlinear_count": sum(1 for r in relationships if r["linearity"] != "Doğrusal"),
        "best_pairs": best_pairs,
        "total_pairs": len(relationships),
        "method": "Pearson + Spearman" if True else "Pearson",
    }


# ══════════════════════════════════════════════════════════════
# 6d. DAĞILIM ANALİZİ
# ══════════════════════════════════════════════════════════════

def distribution_analysis(df: pd.DataFrame) -> dict:
    """Pro dağılım profili — çarpıklık, basıklık, normallik testi, yüzdelikler"""
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
            
            # Normallik testleri (scipy varsa)
            normality_test = None
            if SCIPY_AVAILABLE and 8 <= len(vals) <= 5000:
                try:
                    stat, p_val = scipy_stats.shapiro(vals.values)
                    normality_test = {
                        "test": "Shapiro-Wilk",
                        "statistic": round(stat, 4),
                        "p_value": round(p_val, 4),
                        "is_normal": p_val > 0.05,
                        "interpretation": "Normal dağılım ✓" if p_val > 0.05 else "Normal dağılım değil ✗",
                    }
                except Exception:
                    pass
            elif SCIPY_AVAILABLE and len(vals) > 5000:
                try:
                    stat, p_val = scipy_stats.kstest(vals.values, 'norm', args=(vals.mean(), vals.std()))
                    normality_test = {
                        "test": "Kolmogorov-Smirnov",
                        "statistic": round(stat, 4),
                        "p_value": round(p_val, 4),
                        "is_normal": p_val > 0.05,
                        "interpretation": "Normal dağılım ✓" if p_val > 0.05 else "Normal dağılım değil ✗",
                    }
                except Exception:
                    pass
            
            # Yüzdelik değerler
            percentiles = {
                "P5": round(float(vals.quantile(0.05)), 2),
                "P10": round(float(vals.quantile(0.10)), 2),
                "P25": round(float(vals.quantile(0.25)), 2),
                "P50": round(float(vals.quantile(0.50)), 2),
                "P75": round(float(vals.quantile(0.75)), 2),
                "P90": round(float(vals.quantile(0.90)), 2),
                "P95": round(float(vals.quantile(0.95)), 2),
                "P99": round(float(vals.quantile(0.99)), 2),
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
                    pct = round(count / len(vals) * 100, 1)
                    bands[f"{round(low, 1)}-{round(high, 1)}"] = {"count": count, "pct": pct}
            
            # Yoğunlaşma bölgesi (P25-P75 arası yüzde)
            iqr_count = int(((vals >= vals.quantile(0.25)) & (vals <= vals.quantile(0.75))).sum())
            concentration = round(iqr_count / len(vals) * 100, 1)
            
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
                "concentration_iqr_pct": concentration,
                "normality_test": normality_test,
            }
        except Exception:
            continue
    
    return {"success": True, "distributions": distributions, "columns_analyzed": len(distributions)}


# ══════════════════════════════════════════════════════════════
# 6e. TAHMİNLEME (Basit Projeksiyon)
# ══════════════════════════════════════════════════════════════

def forecast_analysis(df: pd.DataFrame, date_col: str = None, value_col: str = None, periods: int = 6) -> dict:
    """Pro tahminleme — ARIMA/Holt-Winters + güven aralıkları + model karşılaştırması"""
    
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
        
        values_list = [float(v) for v in vals.values]
        models = {}
        best_model = None
        best_mape = float("inf")
        
        # ── Model 1: Lineer Regresyon (her zaman) ──
        x = np.arange(len(vals))
        coeffs = np.polyfit(x, vals.values, 1)
        slope, intercept = coeffs
        y_pred = slope * x + intercept
        ss_res = np.sum((vals.values - y_pred) ** 2)
        ss_tot = np.sum((vals.values - vals.mean()) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        future_x = np.arange(len(vals), len(vals) + periods)
        linear_fc = [round(float(slope * xi + intercept), 2) for xi in future_x]
        
        linear_errors = np.abs(vals.values - y_pred)
        linear_mape = float(np.mean(linear_errors / np.abs(vals.values + 1e-10)) * 100)
        
        models["linear"] = {
            "method": "Lineer Regresyon",
            "forecasts": linear_fc,
            "r_squared": round(r_squared, 3),
            "mape": round(linear_mape, 2),
            "slope": round(float(slope), 4),
        }
        if linear_mape < best_mape:
            best_mape = linear_mape
            best_model = "linear"
        
        # ── Model 2: Holt Linear Trend ──
        if FORECASTING_AVAILABLE and len(values_list) >= 4:
            try:
                holt_result = holt_linear_trend(values_list, forecast_periods=periods)
                if holt_result.get("success"):
                    models["holt"] = {
                        "method": holt_result["method"],
                        "forecasts": holt_result["forecasts"],
                        "confidence_intervals": holt_result.get("confidence_intervals", []),
                        "mape": holt_result.get("mape", 999),
                        "trend_per_period": holt_result.get("trend_per_period"),
                    }
                    if holt_result.get("mape", 999) < best_mape:
                        best_mape = holt_result["mape"]
                        best_model = "holt"
            except Exception:
                pass
        
        # ── Model 3: Exponential Smoothing ──
        if FORECASTING_AVAILABLE and len(values_list) >= 3:
            try:
                ses_result = exponential_smoothing(values_list, forecast_periods=periods)
                if ses_result.get("success"):
                    models["ses"] = {
                        "method": ses_result["method"],
                        "forecasts": ses_result["forecasts"],
                        "confidence_intervals": ses_result.get("confidence_intervals", []),
                        "mape": ses_result.get("mape", 999),
                    }
                    if ses_result.get("mape", 999) < best_mape:
                        best_mape = ses_result["mape"]
                        best_model = "ses"
            except Exception:
                pass
        
        # ── Model 4: ARIMA (en güçlü) ──
        if FORECASTING_AVAILABLE and STATSMODELS_AVAILABLE and len(values_list) >= 10:
            try:
                arima_result = arima_forecast(values_list, forecast_periods=periods)
                if arima_result.get("success"):
                    models["arima"] = {
                        "method": arima_result["method"],
                        "forecasts": arima_result["forecasts"],
                        "confidence_intervals": arima_result.get("confidence_intervals", []),
                        "mape": arima_result.get("mape", 999),
                        "aic": arima_result.get("aic"),
                        "order": arima_result.get("order"),
                        "stationarity": arima_result.get("stationarity"),
                    }
                    if arima_result.get("mape", 999) < best_mape:
                        best_mape = arima_result["mape"]
                        best_model = "arima"
            except Exception:
                pass
        
        # ── Model 5: Holt-Winters Seasonal ──
        if FORECASTING_AVAILABLE and len(values_list) >= 24:
            try:
                hw_result = holt_winters_seasonal(values_list, forecast_periods=periods)
                if hw_result.get("success"):
                    models["holt_winters"] = {
                        "method": hw_result["method"],
                        "forecasts": hw_result["forecasts"],
                        "seasonal_indices": hw_result.get("seasonal_indices", []),
                        "mape": hw_result.get("mape", 999),
                    }
                    if hw_result.get("mape", 999) < best_mape:
                        best_mape = hw_result["mape"]
                        best_model = "holt_winters"
            except Exception:
                pass
        
        # En iyi modelin güven seviyesi
        confidence = "Yüksek" if best_mape < 10 else "Orta" if best_mape < 25 else "Düşük"
        
        current_value = round(float(vals.iloc[-1]), 2)
        best_fc = models[best_model]["forecasts"] if best_model else linear_fc
        predicted_change = round(((best_fc[-1] - current_value) / current_value) * 100, 1) if current_value != 0 else 0
        
        return {
            "success": True,
            "value_column": value_col,
            "data_points": len(vals),
            "forecast_periods": periods,
            "best_model": best_model,
            "best_mape": round(best_mape, 2),
            "confidence": confidence,
            "current_value": current_value,
            "predicted_change_pct": predicted_change,
            "models": models,
            "models_compared": len(models),
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
    """Pro veri kalitesi — eksik veri, tip tutarlılığı, tarih doğrulama, aykırı değer taraması, çapraz kontrol"""
    total_cells = df.shape[0] * df.shape[1]
    
    # 1. Eksik veri analizi
    missing = {}
    total_missing = 0
    missing_patterns = {}
    for col in df.columns:
        null_count = int(df[col].isnull().sum())
        if null_count > 0:
            missing[col] = {
                "count": null_count,
                "pct": round(null_count / len(df) * 100, 1),
                "severity": "Kritik" if null_count / len(df) > 0.3 else "Uyarı" if null_count / len(df) > 0.1 else "Düşük",
            }
            total_missing += null_count
    # Eksik veri deseni — hangi sütunlar birlikte boş
    if len(missing) >= 2:
        missing_cols = list(missing.keys())[:5]
        for i, c1 in enumerate(missing_cols):
            for c2 in missing_cols[i+1:]:
                both_null = int((df[c1].isnull() & df[c2].isnull()).sum())
                if both_null > 0:
                    missing_patterns[f"{c1} & {c2}"] = both_null
    
    # 2. Tekrarlayan satırlar
    duplicates = int(df.duplicated().sum())
    dup_pct = round(duplicates / len(df) * 100, 1) if len(df) > 0 else 0
    # Near-duplicates (string sütunlarında benzerlik)
    near_dup_cols = []
    for col in df.columns:
        if df[col].dtype == 'object':
            vals = df[col].dropna()
            stripped = vals.str.strip().str.lower()
            diff_count = int((vals != stripped.values).sum()) if len(vals) > 0 else 0
            if diff_count > 0:
                near_dup_cols.append({"column": col, "whitespace_case_diffs": diff_count})
    
    # 3. Sütun tip tutarlılığı
    type_issues = {}
    for col in df.columns:
        if df[col].dtype == 'object':
            numeric_like = df[col].dropna().apply(lambda x: str(x).replace(',', '.').replace(' ', '').replace('-', '')).str.match(r'^\d+\.?\d*$')
            numeric_count = int(numeric_like.sum()) if len(numeric_like) > 0 else 0
            total_non_null = int(df[col].notna().sum())
            if total_non_null > 0 and numeric_count / total_non_null > 0.7:
                type_issues[col] = {
                    "issue": "Sayısal veri metin olarak saklanmış",
                    "numeric_ratio": round(numeric_count / total_non_null * 100, 1),
                }
    
    # 4. Tarih formatı doğrulama
    import re
    date_issues = {}
    date_patterns = [
        r'\d{4}-\d{2}-\d{2}',           # YYYY-MM-DD
        r'\d{2}/\d{2}/\d{4}',           # DD/MM/YYYY
        r'\d{2}\.\d{2}\.\d{4}',         # DD.MM.YYYY
        r'\d{4}/\d{2}/\d{2}',           # YYYY/MM/DD
    ]
    for col in df.columns:
        if df[col].dtype == 'object':
            sample = df[col].dropna().head(100)
            if len(sample) == 0:
                continue
            format_counts = {}
            unparseable = 0
            for val in sample:
                val_str = str(val).strip()
                matched = False
                for pat in date_patterns:
                    if re.fullmatch(pat, val_str[:10]):
                        fmt = pat.replace(r'\d{4}', 'YYYY').replace(r'\d{2}', 'XX')
                        format_counts[fmt] = format_counts.get(fmt, 0) + 1
                        matched = True
                        break
                if not matched:
                    # pd.to_datetime ile dene
                    try:
                        pd.to_datetime(val_str)
                        format_counts["mixed_parseable"] = format_counts.get("mixed_parseable", 0) + 1
                    except Exception:
                        pass
            
            if len(format_counts) > 1:
                date_issues[col] = {
                    "issue": "Karışık tarih formatları",
                    "formats_found": format_counts,
                    "recommendation": "Tek bir tarih formatına (YYYY-MM-DD) dönüştürün",
                }
            elif len(format_counts) == 1 and list(format_counts.values())[0] > len(sample) * 0.5:
                # Geçerli tarihler kontrol — gelecek/geçmiş sınırları
                try:
                    parsed = pd.to_datetime(df[col], errors='coerce')
                    valid = parsed.dropna()
                    if len(valid) > 0:
                        future_count = int((valid > pd.Timestamp.now() + pd.Timedelta(days=365*5)).sum())
                        past_count = int((valid < pd.Timestamp('1900-01-01')).sum())
                        if future_count > 0 or past_count > 0:
                            date_issues[col] = {
                                "issue": "Şüpheli tarih aralıkları",
                                "future_dates": future_count,
                                "very_old_dates": past_count,
                                "min_date": str(valid.min())[:10],
                                "max_date": str(valid.max())[:10],
                            }
                except Exception:
                    pass
    
    # 5. Boş/whitespace satırlar
    whitespace_issues = {}
    for col in df.columns:
        if df[col].dtype == 'object':
            ws_count = int(df[col].dropna().apply(lambda x: str(x).strip() == '').sum())
            if ws_count > 0:
                whitespace_issues[col] = ws_count
    
    # 6. Sayısal sütun aralık kontrolü (mantıksız değerler)
    range_issues = {}
    for col in df.select_dtypes(include=[np.number]).columns:
        vals = df[col].dropna()
        if len(vals) < 5:
            continue
        issues = []
        if (vals < 0).any():
            neg_count = int((vals < 0).sum())
            # Yüzde, miktar gibi negatif olmaması gereken alanlar
            lower_col = col.lower()
            if any(kw in lower_col for kw in ['fiyat', 'price', 'miktar', 'quantity', 'adet', 'count', 'yaş', 'age', 'weight', 'ağırlık']):
                issues.append({"type": "Negatif değerler", "count": neg_count, "note": f"'{col}' sütununda negatif değer beklenmez"})
        # Aşırı yüksek değerler (ortalamadan 10x)
        mean_v = vals.mean()
        max_v = vals.max()
        if mean_v > 0 and max_v > mean_v * 100:
            issues.append({"type": "Aşırı yüksek", "max_value": round(float(max_v), 2), "mean": round(float(mean_v), 2), "ratio": round(float(max_v / mean_v), 1)})
        if issues:
            range_issues[col] = issues
    
    # 7. Çapraz sütun tutarlılığı
    cross_checks = []
    col_lower_map = {col: col.lower() for col in df.columns}
    for col in df.columns:
        lc = col_lower_map[col]
        # başlangıç < bitiş kontrolleri
        if any(kw in lc for kw in ['başlangıç', 'start', 'baslangic', 'min_']):
            for col2 in df.columns:
                lc2 = col_lower_map[col2]
                if any(kw in lc2 for kw in ['bitiş', 'end', 'bitis', 'max_']):
                    if df[col].dtype == df[col2].dtype:
                        try:
                            violations = int((df[col] > df[col2]).sum())
                            if violations > 0:
                                cross_checks.append({
                                    "rule": f"{col} ≤ {col2}",
                                    "violations": violations,
                                    "severity": "Uyarı",
                                })
                        except Exception:
                            pass
    
    # 8. Kardinalite analizi (sütun benzersiz değer oranı)
    cardinality = {}
    for col in df.columns:
        nunique = df[col].nunique()
        ratio = round(nunique / len(df) * 100, 1) if len(df) > 0 else 0
        if ratio == 100 and df[col].dtype == 'object':
            cardinality[col] = {"type": "Olası ID/anahtar sütun", "unique_ratio": ratio}
        elif nunique <= 2 and len(df) > 10:
            cardinality[col] = {"type": "Düşük kardinalite (binary)", "unique_values": nunique}
        elif nunique <= 5 and len(df) > 50:
            cardinality[col] = {"type": "Düşük kardinalite (kategori)", "unique_values": nunique}
    
    # 9. Genel kalite skoru (genişletilmiş)
    completeness = round((1 - total_missing / total_cells) * 100, 1) if total_cells > 0 else 100
    uniqueness = round((1 - duplicates / len(df)) * 100, 1) if len(df) > 0 else 100
    consistency = round((1 - len(type_issues) / len(df.columns)) * 100, 1) if len(df.columns) > 0 else 100
    validity = 100.0
    total_validity_checks = len(date_issues) + len(range_issues) + len(cross_checks)
    if total_validity_checks > 0:
        validity = round(max(0, 100 - total_validity_checks * 10), 1)
    quality_score = round((completeness * 0.3 + uniqueness * 0.2 + consistency * 0.2 + validity * 0.3), 1)
    
    return {
        "success": True,
        "rows": len(df),
        "columns": len(df.columns),
        "total_cells": total_cells,
        "quality_score": quality_score,
        "quality_grade": "A" if quality_score >= 90 else "B" if quality_score >= 75 else "C" if quality_score >= 60 else "D" if quality_score >= 40 else "F",
        "dimensions": {
            "completeness": completeness,
            "uniqueness": uniqueness,
            "consistency": consistency,
            "validity": round(validity, 1),
        },
        "completeness": {
            "score": completeness,
            "total_missing": total_missing,
            "columns_with_missing": len(missing),
            "details": missing,
            "missing_patterns": missing_patterns if missing_patterns else None,
        },
        "uniqueness": {
            "score": uniqueness,
            "duplicate_rows": duplicates,
            "duplicate_pct": dup_pct,
            "near_duplicates": near_dup_cols if near_dup_cols else None,
        },
        "consistency": {
            "score": consistency,
            "type_issues": type_issues,
            "whitespace_issues": whitespace_issues,
        },
        "validity": {
            "score": round(validity, 1),
            "date_issues": date_issues if date_issues else None,
            "range_issues": range_issues if range_issues else None,
            "cross_column_checks": cross_checks if cross_checks else None,
        },
        "cardinality": cardinality if cardinality else None,
        "recommendations": _quality_recommendations(completeness, uniqueness, consistency, missing, type_issues, date_issues, range_issues, cross_checks),
    }


def _quality_recommendations(completeness, uniqueness, consistency, missing, type_issues, date_issues=None, range_issues=None, cross_checks=None) -> list:
    """Pro veri kalitesi tavsiyelerini oluştur"""
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
    if date_issues:
        for col, info in date_issues.items():
            recs.append(f"'{col}': {info['issue']} — {info.get('recommendation', 'Düzeltilmeli')}")
    if range_issues:
        for col, issues in range_issues.items():
            for iss in issues:
                recs.append(f"'{col}': {iss['type']} — {iss.get('note', str(iss))}")
    if cross_checks:
        for chk in cross_checks:
            recs.append(f"Çapraz kontrol ihlali: {chk['rule']} ({chk['violations']} satır)")
    if completeness >= 90 and uniqueness >= 95 and consistency >= 90 and not date_issues and not range_issues and not cross_checks:
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
            # İstatistiksel test sonuçları
            stat_tests = comp.get("statistical_tests", {})
            if stat_tests:
                prompt += "\n**İstatistiksel Testler:**\n"
                for col, test_info in stat_tests.items():
                    prompt += f"- **{col}**: {test_info['test']} — p={test_info['p_value']}, {test_info['interpretation']}\n"
                    if test_info.get("cohens_d") is not None:
                        prompt += f"  Etki büyüklüğü (Cohen's d): {test_info['cohens_d']} ({test_info['effect_size']})\n"
                    if test_info.get("eta_squared") is not None:
                        prompt += f"  Etki büyüklüğü (Eta²): {test_info['eta_squared']} ({test_info['effect_size']})\n"
    
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
            prompt += f"\n### Anomali Tespiti (Genel Sağlık: {anom['overall_health']}, Yöntemler: {', '.join(anom.get('detection_methods', []))}):\n"
            prompt += f"- Toplam anomali: {anom['total_anomalies']}, Etkilenen sütun: {anom['columns_with_anomalies']}/{anom['total_columns_checked']}\n"
            for col, det in anom.get("anomaly_details", {}).items():
                methods = det.get("methods", {})
                severity = det.get("severity_breakdown", {})
                prompt += f"- **{col}** [{det['severity']}]: {det['total_anomalies']} anomali (Kritik:{severity.get('kritik',0)}, Orta:{severity.get('orta',0)}, Hafif:{severity.get('hafif',0)})\n"
                prompt += f"  Yöntemler: IQR={methods.get('iqr',{}).get('count',0)}, Z-Score={methods.get('zscore',{}).get('count',0)}, Modified-Z={methods.get('modified_zscore',{}).get('count',0)}"
                if 'rolling_window' in methods:
                    prompt += f", Rolling={methods['rolling_window']['count']}"
                prompt += "\n"
                if det.get("grubbs_test"):
                    gt = det["grubbs_test"]
                    prompt += f"  Grubbs testi: {gt['interpretation']}\n"
                if det.get("top_anomalies"):
                    prompt += f"  En büyük anomaliler: {', '.join(str(v) for v in det['top_anomalies'][:5])}\n"
    
    # Korelasyon Analizi
    if analysis_type == "correlation":
        corr = correlation_analysis(df)
        if corr.get("success"):
            prompt += f"\n### Detaylı Korelasyon Analizi ({corr['total_pairs']} çift incelendi):\n"
            prompt += f"- Güçlü ilişki: {corr['strong_count']}, Orta ilişki: {corr['moderate_count']}\n"
            for rel in corr.get("relationships", [])[:10]:
                emoji = "🔴" if abs(rel["pearson"]) > 0.7 else "🟡" if abs(rel["pearson"]) > 0.5 else "⚪"
                linearity = f", {rel.get('linearity', '')}" if rel.get('linearity') else ""
                sig = " ✓" if rel.get("significant") else " ✗"
                prompt += f"  {emoji} **{rel['col1']}** ↔ **{rel['col2']}**: Pearson={rel['pearson']}, Spearman={rel.get('spearman','N/A')} ({rel['strength']}, {rel['direction']}{linearity}){sig}\n"
                if rel.get("p_value") is not None:
                    prompt += f"    p-value={rel['p_value']}, Anlamlılık: {'Evet' if rel.get('significant') else 'Hayır'}\n"
    
    # Dağılım Analizi
    if analysis_type == "distribution":
        dist = distribution_analysis(df)
        if dist.get("success"):
            prompt += f"\n### Dağılım Analizi ({dist['columns_analyzed']} sütun):\n"
            for col, d in dist.get("distributions", {}).items():
                prompt += f"- **{col}**: {d['distribution_type']}, Ort={d['mean']}, Medyan={d['median']}, Std={d['std']}, CV=%{d['cv_pct']}\n"
                prompt += f"  Çarpıklık={d['skewness']}, Basıklık={d['kurtosis']}, IQR={d['iqr']}\n"
                prompt += f"  Yüzdelikler: P25={d['percentiles']['P25']}, P50={d['percentiles']['P50']}, P75={d['percentiles']['P75']}, P95={d['percentiles']['P95']}, P99={d['percentiles'].get('P99','N/A')}\n"
                if d.get("normality_test"):
                    nt = d["normality_test"]
                    prompt += f"  Normallik testi ({nt['test']}): p={nt['p_value']}, {nt['interpretation']}\n"
                if d.get("concentration_iqr_pct") is not None:
                    prompt += f"  Yoğunlaşma (IQR kapsamı): %{d['concentration_iqr_pct']}\n"
    
    # Tahminleme
    if analysis_type == "forecast":
        fc = forecast_analysis(df)
        if fc.get("success"):
            prompt += f"\n### Tahminleme ({fc.get('models_compared', 0)} model karşılaştırıldı, En iyi: {fc.get('best_model', 'Lineer')}):\n"
            prompt += f"- Mevcut değer: {fc.get('current_value')}, Dönem: {fc.get('forecast_periods', 'N/A')} periyot\n"
            
            # Her modelin sonuçları
            models = fc.get("models", {})
            if models:
                prompt += "- **Model Karşılaştırma Tablosu:**\n"
                for model_name, model_data in models.items():
                    is_best = " ★" if model_name == fc.get("best_model") else ""
                    mape = model_data.get("mape", "N/A")
                    trend = model_data.get("trend_direction", "")
                    forecast_vals = model_data.get("forecast", [])
                    forecast_str = ", ".join(str(v) for v in forecast_vals[:3]) if forecast_vals else "N/A"
                    prompt += f"  | {model_name}{is_best} | MAPE=%{mape} | Tahmin: {forecast_str}... | Trend: {trend} |\n"
                    if model_data.get("confidence_interval"):
                        ci = model_data["confidence_interval"]
                        prompt += f"    Güven aralığı: Alt={ci.get('lower', ['?'])[0]}, Üst={ci.get('upper', ['?'])[0]}\n"
            
            # Genel özet
            prompt += f"- En iyi model MAPE: %{fc.get('best_mape', 'N/A')}\n"
            if fc.get("predicted_change_pct") is not None:
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
            dims = qual.get("dimensions", {})
            prompt += f"\n### Veri Kalitesi Raporu (Skor: {qual['quality_score']}/100, Not: {qual['quality_grade']}):\n"
            prompt += f"- Bütünlük: %{dims.get('completeness', qual['completeness']['score'])} ({qual['completeness']['total_missing']} eksik hücre)\n"
            prompt += f"- Teksillik: %{dims.get('uniqueness', qual['uniqueness']['score'])} ({qual['uniqueness']['duplicate_rows']} tekrar satır)\n"
            prompt += f"- Tutarlılık: %{dims.get('consistency', qual['consistency']['score'])} ({len(qual['consistency']['type_issues'])} tip sorunu)\n"
            prompt += f"- Geçerlilik: %{dims.get('validity', 100)}\n"
            # Tarih sorunları
            validity = qual.get("validity", {})
            if validity.get("date_issues"):
                prompt += "- **Tarih Sorunları**:\n"
                for col, info in validity["date_issues"].items():
                    prompt += f"  • {col}: {info['issue']}\n"
            # Aralık sorunları
            if validity.get("range_issues"):
                prompt += "- **Aralık Sorunları**:\n"
                for col, issues in validity["range_issues"].items():
                    for iss in issues:
                        prompt += f"  • {col}: {iss['type']}\n"
            # Çapraz kontrol
            if validity.get("cross_column_checks"):
                prompt += "- **Çapraz Kontrol İhlalleri**:\n"
                for chk in validity["cross_column_checks"]:
                    prompt += f"  • {chk['rule']}: {chk['violations']} satır\n"
            # Eksik veri desenleri
            if qual['completeness'].get("missing_patterns"):
                prompt += "- **Eksik Veri Desenleri** (birlikte boş olan sütunlar):\n"
                for pair, cnt in qual['completeness']['missing_patterns'].items():
                    prompt += f"  • {pair}: {cnt} satır\n"
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
**GÖREV**: Grupları istatistiksel testlerle birlikte kapsamlı karşılaştır:
1. En iyi ve en kötü performans gösteren gruplar (neden?)
2. Medyan vs ortalama farklarının gösterdiği dağılım özellikleri
3. t-test/ANOVA sonuçları — gruplar arası fark istatistiksel olarak anlamlı mı?
4. Etki büyüklüğü (Cohen's d veya Eta²) — fark pratikte ne kadar önemli?
5. Genel ortalamadan sapma analizi
6. Standart sapma ile tutarlılık değerlendirmesi
7. Her grup için spesifik aksiyon önerileri
⚠️ p-value<0.05 = anlamlı fark, değilse fark rastlantısal olabilir."""

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
**GÖREV**: Çok-yöntemli anomali tespitini detaylı raporla:
1. Tespit edilen anomalilerin seviye dağılımı (Kritik/Orta/Hafif) ve anlamları
2. Hangi yöntemler (IQR, Z-Score, Modified Z-Score, Rolling Window) hangi anomalileri yakaladı
3. Grubbs testi sonuçları — en uç değer istatistiksel olarak gerçek aykırı mı?
4. Rolling window anomalileri — trend değişimi mi yoksa tek seferlik sapma mı?
5. Her anomalinin olası nedenleri (veri hatası mı, gerçek sapma mı?)
6. Temizleme stratejisi: Silinmeli / araştırılmalı / düzeltilmeli
7. Anomalilerin iş süreçlerine potansiyel etkisi
Her bulguyu birden fazla istatistiksel yöntemle destekle."""

    elif analysis_type == "correlation":
        prompt += """
**GÖREV**: Pearson + Spearman korelasyon ilişkilerini iş perspektifinden yorumla:
1. En güçlü pozitif ve negatif ilişkiler (Pearson vs Spearman karşılaştırması)
2. Doğrusal vs doğrusal olmayan ilişkiler — Spearman>Pearson olan çiftler ne anlama geliyor?
3. İstatistiksel anlamlılık — p-value<0.05 olan ilişkiler güvenilir, diğerleri rastlantısal olabilir
4. Beklenmeyen ilişkiler (neden-sonuç tartışması, korelasyon ≠ nedensellik uyarısı)
5. Birbirine bağımlı değişken grupları (cluster)
6. Stratejik öneriler: "X'i artırırsanız Y de artma/azalma eğiliminde"
Her ilişkiyi hem Pearson hem Spearman katsayısıyla birlikte sun."""

    elif analysis_type == "distribution":
        prompt += """
**GÖREV**: Veri dağılımlarını normallik testleriyle birlikte analiz et:
1. Her sütunun dağılım tipi ve normallik testi sonucu (Shapiro-Wilk/KS p-value)
2. Normal dağılan sütunlar → parametrik testler güvenilir
3. Normal dağılmayan sütunlar → medyan bazlı analiz tercih edilmeli
4. Çarpıklık/basıklık: Verilerin nerede yoğunlaştığı ve uç değer riski
5. P99 yüzdelik vs P75 farkı — üst uçtaki yayılma
6. Yoğunlaşma (IQR kapsamı) — verinin ne kadarı merkeze yakın?
7. Değişkenlik katsayısı (CV) ile tutarlılık değerlendirmesi
İstatistiksel terimleri anlaşılır iş diline çevir."""

    elif analysis_type == "forecast":
        prompt += """
**GÖREV**: Çok modelli tahminleme sonuçlarını profesyonelce yorumla:
1. Model karşılaştırma tablosu — hangi model en düşük MAPE ile kazandı ve neden?
2. Modeller arası tutarlılık: Hepsi aynı yönü mü gösteriyor?
3. ARIMA/Holt-Winters gibi gelişmiş modeller lineerden ne kadar farklı?
4. Güven aralıkları — tahminlerin belirsizlik düzeyi
5. En iyi/en kötü senaryo tahminleri (güven aralığı alt-üst)
6. Bu tahminlere göre alınması gereken stratejik aksiyonlar
7. Model kısıtlamaları: Veri yetersizliği, mevsimsellik tespiti, değişen trendler
⚠️ İstatistiksel modeller geçmiş verilere dayanır, gelecek garantisi değildir."""

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
**GÖREV**: Veri kalitesi denetim raporunu 4 boyutta (Bütünlük, Teksillik, Tutarlılık, Geçerlilik) profesyonelce sun:
1. Genel kalite skoru ve notunun değerlendirmesi
2. Bütünlük — eksik verilerin desenleri (birlikte boş olan sütunlar) ve etkisi
3. Teksillik — tekrar satırlar + near-duplicate (whitespace/büyük-küçük harf farklılıkları)
4. Tutarlılık — tip uyumsuzlukları ve düzeltme adımları
5. Geçerlilik — tarih formatı sorunları, mantıksız aralıklar, çapraz kontrol ihlalleri
6. Kardinalite — olası ID sütunları ve düşük kardinalite uyarıları
7. Öncelikli iyileştirme planı (en kritikten en az kritiğe)
8. Veri kalitesi iyileştikten sonra beklenen analiz doğruluğu artışı
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
