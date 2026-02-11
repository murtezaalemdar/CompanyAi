"""Forecasting & Anomaly Detection Engine

Zaman serisi tahminleme ve anomali tespiti:
- Exponential Smoothing (Holt-Winters)
- Moving Average Forecasting
- Seasonal Decomposition
- Z-Score Anomaly Detection
- Isolation Forest (basit versiyon)
- IQR + Rolling anomaly detection
"""

import numpy as np
import pandas as pd
from typing import Optional
import structlog

logger = structlog.get_logger()


# ══════════════════════════════════════════════════════════════
# 1. FORECASTING — Zaman Serisi Tahminleme
# ══════════════════════════════════════════════════════════════

def exponential_smoothing(
    values: list[float],
    alpha: float = 0.3,
    forecast_periods: int = 6,
) -> dict:
    """Basit Exponential Smoothing (SES) tahmini."""
    if len(values) < 3:
        return {"success": False, "error": "En az 3 veri noktası gerekli"}
    
    # SES hesaplama
    smoothed = [values[0]]
    for i in range(1, len(values)):
        smoothed.append(alpha * values[i] + (1 - alpha) * smoothed[-1])
    
    # Tahmin (son smoothed değeri ileriye taşı)
    last_smoothed = smoothed[-1]
    forecasts = [round(last_smoothed, 2)] * forecast_periods
    
    # Güven aralığı (historik hata bazlı)
    errors = [abs(values[i] - smoothed[i]) for i in range(len(values))]
    std_error = np.std(errors) if errors else 0
    
    confidence_intervals = []
    for i in range(forecast_periods):
        margin = 1.96 * std_error * np.sqrt(i + 1)  # 95% CI
        confidence_intervals.append({
            "lower": round(last_smoothed - margin, 2),
            "upper": round(last_smoothed + margin, 2),
        })
    
    return {
        "success": True,
        "method": "Exponential Smoothing (SES)",
        "alpha": alpha,
        "smoothed_values": [round(s, 2) for s in smoothed],
        "forecasts": forecasts,
        "confidence_intervals": confidence_intervals,
        "mape": round(_calculate_mape(values, smoothed), 2),
    }


def holt_linear_trend(
    values: list[float],
    alpha: float = 0.3,
    beta: float = 0.1,
    forecast_periods: int = 6,
) -> dict:
    """Holt's Linear Trend Method — trend'li tahmin."""
    if len(values) < 4:
        return {"success": False, "error": "En az 4 veri noktası gerekli"}
    
    # İlk değerler
    level = [values[0]]
    trend = [values[1] - values[0]]
    fitted = [level[0] + trend[0]]
    
    for i in range(1, len(values)):
        new_level = alpha * values[i] + (1 - alpha) * (level[-1] + trend[-1])
        new_trend = beta * (new_level - level[-1]) + (1 - beta) * trend[-1]
        level.append(new_level)
        trend.append(new_trend)
        fitted.append(new_level + new_trend)
    
    # Tahmin
    forecasts = []
    for h in range(1, forecast_periods + 1):
        forecast = level[-1] + h * trend[-1]
        forecasts.append(round(forecast, 2))
    
    # Güven aralığı
    errors = [abs(values[i] - fitted[i]) for i in range(len(values))]
    std_error = np.std(errors) if errors else 0
    
    confidence_intervals = []
    for i in range(forecast_periods):
        margin = 1.96 * std_error * np.sqrt(i + 1)
        confidence_intervals.append({
            "lower": round(forecasts[i] - margin, 2),
            "upper": round(forecasts[i] + margin, 2),
        })
    
    trend_direction = "Artış" if trend[-1] > 0 else "Azalma" if trend[-1] < 0 else "Stabil"
    
    return {
        "success": True,
        "method": "Holt Linear Trend",
        "alpha": alpha,
        "beta": beta,
        "fitted_values": [round(f, 2) for f in fitted],
        "forecasts": forecasts,
        "confidence_intervals": confidence_intervals,
        "trend_direction": trend_direction,
        "trend_per_period": round(trend[-1], 2),
        "mape": round(_calculate_mape(values, fitted), 2),
    }


def holt_winters_seasonal(
    values: list[float],
    season_length: int = 12,
    alpha: float = 0.3,
    beta: float = 0.1,
    gamma: float = 0.1,
    forecast_periods: int = 6,
) -> dict:
    """Holt-Winters Seasonal Method — mevsimsel + trend tahmin."""
    n = len(values)
    if n < season_length * 2:
        # Yeterli veri yoksa Holt'a düş
        return holt_linear_trend(values, alpha, beta, forecast_periods)
    
    # İlk mevsimsel indeksler
    season_averages = []
    for i in range(0, season_length):
        avg = np.mean([values[j] for j in range(i, n, season_length) if j < n])
        season_averages.append(avg)
    grand_avg = np.mean(season_averages)
    seasonal = [sa / grand_avg if grand_avg != 0 else 1.0 for sa in season_averages]
    
    # İlk level ve trend
    level = values[0] / seasonal[0] if seasonal[0] != 0 else values[0]
    trend = (values[season_length] - values[0]) / season_length if n > season_length else 0
    
    fitted = []
    levels = [level]
    trends = [trend]
    seasonals = list(seasonal)
    
    for i in range(n):
        s_idx = i % season_length
        
        if i == 0:
            fitted.append(level + trend + (seasonals[s_idx] - 1) * level)
            continue
        
        new_level = alpha * (values[i] / seasonals[s_idx] if seasonals[s_idx] != 0 else values[i]) + (1 - alpha) * (levels[-1] + trends[-1])
        new_trend = beta * (new_level - levels[-1]) + (1 - beta) * trends[-1]
        new_seasonal = gamma * (values[i] / new_level if new_level != 0 else 1) + (1 - gamma) * seasonals[s_idx]
        
        levels.append(new_level)
        trends.append(new_trend)
        seasonals[s_idx] = new_seasonal
        fitted.append((new_level + new_trend) * new_seasonal)
    
    # Tahmin
    forecasts = []
    for h in range(1, forecast_periods + 1):
        s_idx = (n + h - 1) % season_length
        forecast = (levels[-1] + h * trends[-1]) * seasonals[s_idx]
        forecasts.append(round(forecast, 2))
    
    return {
        "success": True,
        "method": "Holt-Winters Seasonal",
        "season_length": season_length,
        "fitted_values": [round(f, 2) for f in fitted],
        "forecasts": forecasts,
        "seasonal_indices": [round(s, 3) for s in seasonals],
        "trend_per_period": round(trends[-1], 2),
        "mape": round(_calculate_mape(values, fitted), 2),
    }


def moving_average_forecast(
    values: list[float],
    window: int = 3,
    forecast_periods: int = 6,
) -> dict:
    """Hareketli ortalama tahmini."""
    if len(values) < window:
        return {"success": False, "error": f"En az {window} veri noktası gerekli"}
    
    # MA hesaplama
    ma = []
    for i in range(len(values)):
        if i < window - 1:
            ma.append(None)
        else:
            ma.append(round(np.mean(values[i-window+1:i+1]), 2))
    
    # Tahmin
    last_ma = ma[-1]
    forecasts = [last_ma] * forecast_periods
    
    # Weighted MA tahmin (son değerlere daha çok ağırlık)
    weights = list(range(1, window + 1))
    wma = np.average(values[-window:], weights=weights)
    weighted_forecasts = [round(wma, 2)] * forecast_periods
    
    return {
        "success": True,
        "method": f"Moving Average (window={window})",
        "moving_averages": ma,
        "simple_forecasts": forecasts,
        "weighted_forecasts": weighted_forecasts,
    }


def auto_forecast(
    df: pd.DataFrame,
    date_col: str = None,
    value_col: str = None,
    forecast_periods: int = 6,
) -> dict:
    """Otomatik tahminleme — en iyi yöntemi seçer."""
    # Tarih sütununu bul
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
    
    # Değer sütununu bul
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if value_col and value_col in num_cols:
        pass
    elif num_cols:
        value_col = num_cols[0]
    else:
        return {"success": False, "error": "Sayısal sütun bulunamadı"}
    
    # Sırala
    df_sorted = df.copy()
    df_sorted[date_col] = pd.to_datetime(df_sorted[date_col])
    df_sorted = df_sorted.sort_values(date_col)
    values = df_sorted[value_col].dropna().tolist()
    
    if len(values) < 4:
        return {"success": False, "error": "En az 4 veri noktası gerekli"}
    
    # Mevsimsellik var mı? (12 veya 4 periyot)
    results = {}
    
    # 1. SES
    ses = exponential_smoothing(values, forecast_periods=forecast_periods)
    results["ses"] = ses
    
    # 2. Holt Linear
    holt = holt_linear_trend(values, forecast_periods=forecast_periods)
    results["holt"] = holt
    
    # 3. Holt-Winters (yeterli veri varsa)
    if len(values) >= 24:
        hw = holt_winters_seasonal(values, season_length=12, forecast_periods=forecast_periods)
        results["holt_winters"] = hw
    elif len(values) >= 8:
        hw = holt_winters_seasonal(values, season_length=4, forecast_periods=forecast_periods)
        results["holt_winters"] = hw
    
    # En iyi modeli seç (MAPE bazlı)
    best_method = None
    best_mape = float('inf')
    for method, result in results.items():
        if result.get("success") and result.get("mape", float('inf')) < best_mape:
            best_mape = result["mape"]
            best_method = method
    
    best_result = results.get(best_method, ses)
    
    return {
        "success": True,
        "best_method": best_method,
        "best_mape": best_mape,
        "value_column": value_col,
        "date_column": date_col,
        "data_points": len(values),
        "forecast_periods": forecast_periods,
        "forecasts": best_result.get("forecasts", []),
        "confidence_intervals": best_result.get("confidence_intervals", []),
        "trend_direction": best_result.get("trend_direction", "N/A"),
        "all_models": {k: {"mape": v.get("mape", "N/A"), "method": v.get("method", k)} 
                      for k, v in results.items() if v.get("success")},
    }


# ══════════════════════════════════════════════════════════════
# 2. ANOMALY DETECTION — Anomali Tespiti
# ══════════════════════════════════════════════════════════════

def zscore_anomaly(
    values: list[float],
    threshold: float = 2.5,
) -> dict:
    """Z-Score bazlı anomali tespiti."""
    if len(values) < 5:
        return {"success": False, "error": "En az 5 veri noktası gerekli"}
    
    arr = np.array(values)
    mean = np.mean(arr)
    std = np.std(arr)
    
    if std == 0:
        return {"success": True, "anomalies": [], "message": "Veri varyansı yok"}
    
    z_scores = [(v - mean) / std for v in values]
    
    anomalies = []
    for i, (val, z) in enumerate(zip(values, z_scores)):
        if abs(z) > threshold:
            anomalies.append({
                "index": i,
                "value": val,
                "z_score": round(z, 3),
                "direction": "Yüksek" if z > 0 else "Düşük",
                "severity": "Kritik" if abs(z) > 3.5 else "Dikkat" if abs(z) > 3.0 else "Hafif",
            })
    
    return {
        "success": True,
        "method": "Z-Score",
        "threshold": threshold,
        "mean": round(mean, 2),
        "std": round(std, 2),
        "total_points": len(values),
        "anomaly_count": len(anomalies),
        "anomaly_rate": round(len(anomalies) / len(values) * 100, 1),
        "anomalies": anomalies,
    }


def iqr_anomaly(
    values: list[float],
    multiplier: float = 1.5,
) -> dict:
    """IQR (Interquartile Range) bazlı anomali tespiti."""
    arr = np.array(values)
    Q1 = np.percentile(arr, 25)
    Q3 = np.percentile(arr, 75)
    IQR = Q3 - Q1
    
    lower = Q1 - multiplier * IQR
    upper = Q3 + multiplier * IQR
    
    anomalies = []
    for i, val in enumerate(values):
        if val < lower or val > upper:
            anomalies.append({
                "index": i,
                "value": val,
                "bound_violated": "lower" if val < lower else "upper",
                "distance": round(abs(val - lower) if val < lower else abs(val - upper), 2),
            })
    
    return {
        "success": True,
        "method": "IQR",
        "Q1": round(Q1, 2),
        "Q3": round(Q3, 2),
        "IQR": round(IQR, 2),
        "lower_bound": round(lower, 2),
        "upper_bound": round(upper, 2),
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
    }


def rolling_anomaly(
    values: list[float],
    window: int = 7,
    threshold_std: float = 2.0,
) -> dict:
    """Rolling (hareketli pencere) anomali tespiti — zaman serisi için."""
    if len(values) < window + 3:
        return {"success": False, "error": f"En az {window + 3} veri noktası gerekli"}
    
    anomalies = []
    rolling_means = []
    rolling_stds = []
    
    for i in range(window, len(values)):
        window_data = values[i-window:i]
        mean = np.mean(window_data)
        std = np.std(window_data)
        rolling_means.append(round(mean, 2))
        rolling_stds.append(round(std, 2))
        
        if std > 0:
            z = (values[i] - mean) / std
            if abs(z) > threshold_std:
                anomalies.append({
                    "index": i,
                    "value": values[i],
                    "expected": round(mean, 2),
                    "deviation": round(values[i] - mean, 2),
                    "z_score": round(z, 2),
                    "direction": "Yüksek" if z > 0 else "Düşük",
                })
    
    return {
        "success": True,
        "method": f"Rolling Anomaly (window={window})",
        "window": window,
        "threshold": threshold_std,
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
        "rolling_means": rolling_means,
    }


def auto_anomaly_detection(
    df: pd.DataFrame,
    value_col: str = None,
) -> dict:
    """Otomatik anomali tespiti — birden fazla yöntem uygular."""
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    if value_col and value_col in num_cols:
        target_cols = [value_col]
    else:
        target_cols = num_cols[:5]  # Max 5 sütun
    
    all_results = {}
    
    for col in target_cols:
        values = df[col].dropna().tolist()
        if len(values) < 5:
            continue
        
        # Her yöntemi uygula
        z_result = zscore_anomaly(values)
        iqr_result = iqr_anomaly(values)
        
        # Rolling (yeterli veri varsa)
        rolling_result = None
        if len(values) >= 15:
            rolling_result = rolling_anomaly(values)
        
        # Konsensüs: Birden fazla yöntem tarafından tespit edilen anomaliler
        z_indices = set(a["index"] for a in z_result.get("anomalies", []))
        iqr_indices = set(a["index"] for a in iqr_result.get("anomalies", []))
        
        consensus = z_indices & iqr_indices  # Her iki yöntemin de tespit ettikleri
        
        all_results[col] = {
            "z_score": z_result,
            "iqr": iqr_result,
            "rolling": rolling_result,
            "consensus_anomalies": sorted(consensus),
            "consensus_count": len(consensus),
            "total_points": len(values),
        }
    
    return {
        "success": True,
        "columns_analyzed": list(all_results.keys()),
        "results": all_results,
        "summary": {
            col: {
                "anomaly_count": r["consensus_count"],
                "anomaly_rate": round(r["consensus_count"] / r["total_points"] * 100, 1),
            }
            for col, r in all_results.items()
        },
    }


# ══════════════════════════════════════════════════════════════
# 3. SEASONAL DECOMPOSITION — Mevsimsel Ayrıştırma
# ══════════════════════════════════════════════════════════════

def seasonal_decomposition(
    values: list[float],
    period: int = 12,
) -> dict:
    """Basit mevsimsel ayrıştırma (additive model).
    
    Y = Trend + Seasonal + Residual
    """
    n = len(values)
    if n < period * 2:
        return {"success": False, "error": f"En az {period * 2} veri noktası gerekli"}
    
    arr = np.array(values, dtype=float)
    
    # 1. Trend (centered moving average)
    trend = np.full(n, np.nan)
    half = period // 2
    for i in range(half, n - half):
        trend[i] = np.mean(arr[i-half:i+half+1])
    
    # Kenar değerlerini doldur
    first_valid = next(i for i in range(n) if not np.isnan(trend[i]))
    last_valid = next(i for i in range(n-1, -1, -1) if not np.isnan(trend[i]))
    trend[:first_valid] = trend[first_valid]
    trend[last_valid+1:] = trend[last_valid]
    
    # 2. Mevsimsel bileşen
    detrended = arr - trend
    seasonal = np.zeros(n)
    for s in range(period):
        indices = list(range(s, n, period))
        seasonal_avg = np.nanmean(detrended[indices])
        for idx in indices:
            seasonal[idx] = seasonal_avg
    
    # Normalize (mevsimsel toplamı 0 ol)
    seasonal_mean = np.mean(seasonal[:period])
    seasonal -= seasonal_mean
    
    # 3. Residual
    residual = arr - trend - seasonal
    
    # Mevsimsel indeksler (her periyot için)
    seasonal_indices = []
    for s in range(period):
        seasonal_indices.append(round(float(seasonal[s]), 2))
    
    # Sektörel yorumlama (tekstil)
    peak_season = int(np.argmax(seasonal_indices))
    low_season = int(np.argmin(seasonal_indices))
    
    quarter_labels = {
        0: "Ocak", 1: "Şubat", 2: "Mart", 3: "Nisan",
        4: "Mayıs", 5: "Haziran", 6: "Temmuz", 7: "Ağustos",
        8: "Eylül", 9: "Ekim", 10: "Kasım", 11: "Aralık",
    }
    
    return {
        "success": True,
        "method": "Additive Decomposition",
        "period": period,
        "trend": [round(float(t), 2) for t in trend],
        "seasonal": [round(float(s), 2) for s in seasonal],
        "residual": [round(float(r), 2) for r in residual],
        "seasonal_indices": seasonal_indices,
        "peak_season": quarter_labels.get(peak_season, str(peak_season)),
        "low_season": quarter_labels.get(low_season, str(low_season)),
        "trend_direction": "Artış" if trend[-1] > trend[0] else "Azalma" if trend[-1] < trend[0] else "Stabil",
        "seasonality_strength": round(float(np.std(seasonal) / (np.std(residual) + np.std(seasonal) + 0.001)), 2),
    }


# ══════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ══════════════════════════════════════════════════════════════

def _calculate_mape(actual: list, forecast: list) -> float:
    """Mean Absolute Percentage Error."""
    errors = []
    for a, f in zip(actual, forecast):
        if a != 0 and f is not None:
            errors.append(abs((a - f) / a) * 100)
    return np.mean(errors) if errors else 0
