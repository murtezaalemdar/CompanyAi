"""Forecasting & Anomaly Detection Engine

Zaman serisi tahminleme ve anomali tespiti:
- ARIMA / SARIMA (statsmodels)          ← v3.3.0
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

# statsmodels opsiyonel — yoksa ARIMA devre dışı
try:
    from statsmodels.tsa.arima.model import ARIMA as _ARIMA
    from statsmodels.tsa.statespace.sarimax import SARIMAX as _SARIMAX
    from statsmodels.tsa.stattools import adfuller, acf, pacf
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False


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


# ──────────────────────────────────────────────────────────────
# 1b. ARIMA / SARIMA — İstatistiksel Model Tahminleme (v3.3.0)
# ──────────────────────────────────────────────────────────────

def _adf_test(values: list[float]) -> dict:
    """Augmented Dickey-Fuller durağanlık testi."""
    if not STATSMODELS_AVAILABLE:
        return {"stationary": None, "error": "statsmodels yüklü değil"}
    try:
        result = adfuller(values, autolag="AIC")
        return {
            "statistic": round(result[0], 4),
            "p_value": round(result[1], 4),
            "lags_used": result[2],
            "stationary": result[1] < 0.05,  # p < 0.05 → durağan
        }
    except Exception as e:
        return {"stationary": None, "error": str(e)}


def _auto_arima_order(values: list[float], max_p: int = 4, max_q: int = 4) -> tuple:
    """AIC bazlı otomatik (p,d,q) sıra seçimi.
    
    Basit grid-search — statsmodels auto_arima gerektirmez.
    """
    import warnings
    warnings.filterwarnings("ignore")
    
    arr = np.array(values, dtype=float)
    
    # Durağanlık testi → d belirle
    adf = _adf_test(values)
    if adf.get("stationary"):
        d = 0
    else:
        d = 1
        # Bir kez fark al ve tekrar test et
        diff = np.diff(arr)
        adf2 = _adf_test(diff.tolist())
        if not adf2.get("stationary"):
            d = 2
    
    best_aic = float("inf")
    best_order = (1, d, 1)
    
    for p in range(0, max_p + 1):
        for q in range(0, max_q + 1):
            if p == 0 and q == 0:
                continue
            try:
                model = _ARIMA(arr, order=(p, d, q))
                fit = model.fit()
                if fit.aic < best_aic:
                    best_aic = fit.aic
                    best_order = (p, d, q)
            except Exception:
                continue
    
    return best_order, best_aic


def arima_forecast(
    values: list[float],
    order: tuple = None,
    forecast_periods: int = 6,
    auto_select: bool = True,
) -> dict:
    """ARIMA tahmin motoru — otomatik (p,d,q) seçimi ile.
    
    Args:
        values: Zaman serisi verileri
        order: (p,d,q) tuple — None ise otomatik seçilir
        forecast_periods: Kaç dönem tahmin edilecek
        auto_select: True ise AIC ile en iyi sıra seçilir
    
    Returns:
        dict: Tahmin sonuçları + model bilgileri
    """
    if not STATSMODELS_AVAILABLE:
        # Fallback: Holt Linear Trend
        logger.warning("statsmodels yüklü değil, Holt'a düşülüyor")
        return holt_linear_trend(values, forecast_periods=forecast_periods)
    
    if len(values) < 10:
        return {"success": False, "error": "ARIMA için en az 10 veri noktası gerekli"}
    
    import warnings
    warnings.filterwarnings("ignore")
    
    arr = np.array(values, dtype=float)
    
    try:
        # Sıra seçimi
        if order is None and auto_select:
            order, aic = _auto_arima_order(values, max_p=3, max_q=3)
        elif order is None:
            order = (1, 1, 1)
            aic = None
        else:
            aic = None
        
        # Model fit
        model = _ARIMA(arr, order=order)
        fit = model.fit()
        
        if aic is None:
            aic = fit.aic
        
        # In-sample fitted
        fitted = fit.fittedvalues.tolist()
        
        # Forecast
        fc = fit.get_forecast(steps=forecast_periods)
        forecasts = fc.predicted_mean.tolist()
        ci = fc.conf_int(alpha=0.05)  # 95% CI
        # conf_int() DataFrame veya ndarray dönebilir
        ci_arr = ci.values if hasattr(ci, 'values') else np.asarray(ci)
        
        confidence_intervals = []
        for i in range(forecast_periods):
            confidence_intervals.append({
                "lower": round(float(ci_arr[i, 0]), 2),
                "upper": round(float(ci_arr[i, 1]), 2),
            })
        
        # Diagnostik
        residuals = fit.resid.tolist()
        
        # Trend yönü
        if len(forecasts) >= 2:
            trend_dir = "Artış" if forecasts[-1] > forecasts[0] else "Azalma" if forecasts[-1] < forecasts[0] else "Stabil"
        else:
            trend_dir = "N/A"
        
        # ADF durağanlık bilgisi
        stationarity = _adf_test(values)
        
        return {
            "success": True,
            "method": f"ARIMA{order}",
            "order": {"p": order[0], "d": order[1], "q": order[2]},
            "aic": round(aic, 2),
            "bic": round(fit.bic, 2),
            "fitted_values": [round(f, 2) for f in fitted],
            "forecasts": [round(f, 2) for f in forecasts],
            "confidence_intervals": confidence_intervals,
            "trend_direction": trend_dir,
            "mape": round(_calculate_mape(values, fitted), 2),
            "residual_std": round(float(np.std(residuals)), 2),
            "stationarity": stationarity,
            "model_summary": {
                "log_likelihood": round(fit.llf, 2),
                "n_observations": len(values),
            },
        }
    
    except Exception as e:
        logger.error("ARIMA hatası", error=str(e))
        # Fallback
        return holt_linear_trend(values, forecast_periods=forecast_periods)


def sarima_forecast(
    values: list[float],
    seasonal_period: int = 12,
    order: tuple = None,
    seasonal_order: tuple = None,
    forecast_periods: int = 6,
) -> dict:
    """SARIMA (Seasonal ARIMA) tahmin motoru.
    
    Mevsimsel bileşeni de modelleyen ARIMA — tekstil sektöründe
    sezon bazlı üretim/satış tahmininde kritik.
    
    Args:
        values: Zaman serisi
        seasonal_period: Mevsimsel periyot (12=aylık, 4=çeyreklik)
        order: (p,d,q) — None ise (1,1,1)
        seasonal_order: (P,D,Q,s) — None ise (1,1,1,s)
        forecast_periods: Tahmin dönem sayısı
    """
    if not STATSMODELS_AVAILABLE:
        logger.warning("statsmodels yüklü değil, Holt-Winters'a düşülüyor")
        return holt_winters_seasonal(values, season_length=seasonal_period, forecast_periods=forecast_periods)
    
    if len(values) < seasonal_period * 2:
        return {"success": False, "error": f"SARIMA için en az {seasonal_period * 2} veri noktası gerekli"}
    
    import warnings
    warnings.filterwarnings("ignore")
    
    arr = np.array(values, dtype=float)
    
    try:
        if order is None:
            order = (1, 1, 1)
        if seasonal_order is None:
            seasonal_order = (1, 1, 1, seasonal_period)
        
        # SARIMA fit — en iyi modeli AIC ile seç
        best_aic = float("inf")
        best_fit = None
        best_order = order
        best_seasonal = seasonal_order
        
        # Küçük grid search
        for p in range(0, 3):
            for q in range(0, 3):
                for P in range(0, 2):
                    for Q in range(0, 2):
                        try:
                            _o = (p, 1, q)
                            _so = (P, 1, Q, seasonal_period)
                            m = _SARIMAX(arr, order=_o, seasonal_order=_so,
                                        enforce_stationarity=False,
                                        enforce_invertibility=False)
                            f = m.fit(disp=False, maxiter=50)
                            if f.aic < best_aic:
                                best_aic = f.aic
                                best_fit = f
                                best_order = _o
                                best_seasonal = _so
                        except Exception:
                            continue
        
        if best_fit is None:
            # Grid search başarısız → basit model
            m = _SARIMAX(arr, order=order, seasonal_order=seasonal_order,
                        enforce_stationarity=False, enforce_invertibility=False)
            best_fit = m.fit(disp=False)
            best_aic = best_fit.aic
        
        # Fitted values
        fitted = best_fit.fittedvalues.tolist()
        
        # Forecast + CI
        fc = best_fit.get_forecast(steps=forecast_periods)
        forecasts = fc.predicted_mean.tolist()
        ci = fc.conf_int(alpha=0.05)
        ci_arr = ci.values if hasattr(ci, 'values') else np.asarray(ci)
        
        confidence_intervals = []
        for i in range(forecast_periods):
            confidence_intervals.append({
                "lower": round(float(ci_arr[i, 0]), 2),
                "upper": round(float(ci_arr[i, 1]), 2),
            })
        
        # Mevsimsel indeksler çıkar (basit)
        seasonal_indices = []
        for s in range(seasonal_period):
            indices = list(range(s, len(values), seasonal_period))
            avg = np.mean([values[i] for i in indices if i < len(values)])
            seasonal_indices.append(round(float(avg), 2))
        grand_mean = np.mean(values)
        seasonal_factors = [round(si / grand_mean, 3) if grand_mean != 0 else 1.0 for si in seasonal_indices]
        
        # Trend
        if len(forecasts) >= 2:
            trend_dir = "Artış" if forecasts[-1] > forecasts[0] else "Azalma" if forecasts[-1] < forecasts[0] else "Stabil"
        else:
            trend_dir = "N/A"
        
        return {
            "success": True,
            "method": f"SARIMA{best_order}x{best_seasonal}",
            "order": {"p": best_order[0], "d": best_order[1], "q": best_order[2]},
            "seasonal_order": {"P": best_seasonal[0], "D": best_seasonal[1], "Q": best_seasonal[2], "s": best_seasonal[3]},
            "aic": round(best_aic, 2),
            "bic": round(best_fit.bic, 2),
            "fitted_values": [round(f, 2) for f in fitted],
            "forecasts": [round(f, 2) for f in forecasts],
            "confidence_intervals": confidence_intervals,
            "seasonal_factors": seasonal_factors,
            "seasonal_period": seasonal_period,
            "trend_direction": trend_dir,
            "mape": round(_calculate_mape(values, fitted), 2),
            "model_summary": {
                "log_likelihood": round(best_fit.llf, 2),
                "n_observations": len(values),
            },
        }
    
    except Exception as e:
        logger.error("SARIMA hatası", error=str(e))
        return holt_winters_seasonal(values, season_length=seasonal_period, forecast_periods=forecast_periods)


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
    """Otomatik tahminleme — en iyi yöntemi seçer (ARIMA dahil)."""
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
    
    # 4. ARIMA (statsmodels varsa) — v3.3.0
    if STATSMODELS_AVAILABLE and len(values) >= 10:
        arima = arima_forecast(values, forecast_periods=forecast_periods)
        if arima.get("success"):
            results["arima"] = arima
    
    # 5. SARIMA (mevsimsel + yeterli veri varsa) — v3.3.0
    if STATSMODELS_AVAILABLE and len(values) >= 30:
        season_len = 12 if len(values) >= 30 else 4
        sarima = sarima_forecast(values, seasonal_period=season_len, forecast_periods=forecast_periods)
        if sarima.get("success"):
            results["sarima"] = sarima
    
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
