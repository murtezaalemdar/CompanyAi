"""
Otomatik İçgörü (Insight) Motoru — CompanyAi v3.9.0
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
DataFrame verisinden 7 farklı tipte içgörü çıkarır:
  1. Korelasyon analizi
  2. Anomali tespiti (IQR)
  3. Pareto analizi (80/20)
  4. Yoğunlaşma analizi
  5. Trend analizi
  6. Eşik değer kontrolü
  7. Karşılaştırma analizi
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Textile Sektörü Eşik Değerleri ───────────────────────────
TEXTILE_THRESHOLDS: dict[str, dict] = {
    "fire": {"max": 5.0, "unit": "%", "label": "Fire Oranı"},
    "fire_orani": {"max": 5.0, "unit": "%", "label": "Fire Oranı"},
    "verimlilik": {"min": 85.0, "unit": "%", "label": "Verimlilik"},
    "efficiency": {"min": 85.0, "unit": "%", "label": "Verimlilik"},
    "iade_orani": {"max": 3.0, "unit": "%", "label": "İade Oranı"},
    "return_rate": {"max": 3.0, "unit": "%", "label": "İade Oranı"},
    "hata_orani": {"max": 2.0, "unit": "%", "label": "Hata Oranı"},
    "defect_rate": {"max": 2.0, "unit": "%", "label": "Hata Oranı"},
    "kapasite_kullanimi": {"min": 75.0, "max": 95.0, "unit": "%", "label": "Kapasite Kullanımı"},
    "capacity_utilization": {"min": 75.0, "max": 95.0, "unit": "%", "label": "Kapasite Kullanımı"},
    "oee": {"min": 65.0, "unit": "%", "label": "OEE"},
    "duruş_suresi": {"max": 10.0, "unit": "%", "label": "Duruş Süresi"},
    "downtime": {"max": 10.0, "unit": "%", "label": "Duruş Süresi"},
    "enerji_tuketim": {"max": 120.0, "unit": "kWh/ton", "label": "Enerji Tüketimi"},
    "personel_devir": {"max": 15.0, "unit": "%", "label": "Personel Devir Hızı"},
}


@dataclass
class Insight:
    """Tek bir içgörü."""
    type: str          # correlation | anomaly | pareto | concentration | trend | threshold | comparison
    severity: str      # critical | warning | info
    title: str
    description: str
    metric: str = ""
    value: Any = None
    recommendation: str = ""


@dataclass
class InsightReport:
    """Bir veri seti için üretilen tüm içgörüler."""
    insights: list[Insight] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    row_count: int = 0
    col_count: int = 0


# ══════════════════════════════════════════════════════════════
#  ANA FONKSİYON
# ══════════════════════════════════════════════════════════════
def extract_insights(df: pd.DataFrame, max_insights: int = 20) -> InsightReport:
    """DataFrame'den otomatik içgörü çıkar."""
    if df is None or df.empty:
        return InsightReport()

    report = InsightReport(row_count=len(df), col_count=len(df.columns))

    try:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if not numeric_cols:
            report.insights.append(Insight(
                type="info", severity="info",
                title="Sayısal Veri Yok",
                description="Veri setinde sayısal sütun bulunamadı, içgörü üretilemiyor."
            ))
            return report

        # 1) Korelasyon
        _extract_correlations(df, numeric_cols, report)
        # 2) Anomali
        _extract_anomalies(df, numeric_cols, report)
        # 3) Pareto
        _extract_pareto(df, numeric_cols, report)
        # 4) Yoğunlaşma
        _extract_concentration(df, numeric_cols, report)
        # 5) Trend
        _extract_trends(df, numeric_cols, report)
        # 6) Eşik değer
        _extract_threshold_violations(df, numeric_cols, report)
        # 7) Karşılaştırma
        _extract_comparisons(df, numeric_cols, report)

        # Öncelik sıralaması: critical → warning → info
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        report.insights.sort(key=lambda i: severity_order.get(i.severity, 3))
        report.insights = report.insights[:max_insights]

    except Exception as e:
        logger.error("Insight extraction error: %s", e)
        report.insights.append(Insight(
            type="error", severity="warning",
            title="İçgörü Üretim Hatası",
            description=f"Analiz sırasında hata: {str(e)}"
        ))

    return report


# ══════════════════════════════════════════════════════════════
#  İÇGÖRÜ FONKSİYONLARI
# ══════════════════════════════════════════════════════════════
def _extract_correlations(df: pd.DataFrame, cols: list[str], report: InsightReport) -> None:
    """Güçlü korelasyonları bul (|r| > 0.7)."""
    if len(cols) < 2:
        return
    try:
        corr = df[cols].corr()
        seen: set[tuple] = set()
        for i, c1 in enumerate(cols):
            for j, c2 in enumerate(cols):
                if i >= j:
                    continue
                r = corr.loc[c1, c2]
                if abs(r) > 0.7 and (c1, c2) not in seen:
                    seen.add((c1, c2))
                    direction = "pozitif" if r > 0 else "negatif"
                    severity = "warning" if abs(r) > 0.9 else "info"
                    report.insights.append(Insight(
                        type="correlation", severity=severity,
                        title=f"Güçlü {direction} korelasyon",
                        description=f"{c1} ↔ {c2} arasında {direction} korelasyon (r={r:.2f})",
                        metric=f"{c1}↔{c2}", value=round(r, 3),
                        recommendation=f"{c1} değiştiğinde {c2} üzerindeki etkiyi takip edin."
                    ))
    except Exception:
        pass


def _extract_anomalies(df: pd.DataFrame, cols: list[str], report: InsightReport) -> None:
    """IQR yöntemiyle aykırı değer tespit et."""
    for col in cols[:10]:
        try:
            series = df[col].dropna()
            if len(series) < 10:
                continue
            q1, q3 = series.quantile(0.25), series.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue
            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            outliers = series[(series < lower) | (series > upper)]
            pct = len(outliers) / len(series) * 100
            if pct > 1:
                severity = "critical" if pct > 10 else ("warning" if pct > 5 else "info")
                report.insights.append(Insight(
                    type="anomaly", severity=severity,
                    title=f"{col} aykırı değer",
                    description=f"{col} sütununda %{pct:.1f} oranında aykırı değer ({len(outliers)} kayıt)",
                    metric=col, value=round(pct, 2),
                    recommendation=f"Aykırı kayıtları inceleyin, veri girişi hatası olabilir."
                ))
        except Exception:
            continue


def _extract_pareto(df: pd.DataFrame, cols: list[str], report: InsightReport) -> None:
    """Pareto analizi — %20 kaynak %80 etkiyi oluşturuyor mu?"""
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    for cat in cat_cols[:5]:
        for num in cols[:5]:
            try:
                grouped = df.groupby(cat)[num].sum().sort_values(ascending=False)
                if len(grouped) < 3:
                    continue
                total = grouped.sum()
                if total == 0:
                    continue
                top_n = max(1, int(len(grouped) * 0.2))
                top_share = grouped.iloc[:top_n].sum() / total * 100
                if top_share >= 70:
                    report.insights.append(Insight(
                        type="pareto", severity="warning",
                        title=f"Pareto etkisi: {cat} → {num}",
                        description=f"Üst %20 {cat} ({top_n} kategori), toplam {num} değerinin %{top_share:.0f}'ini oluşturuyor.",
                        metric=f"{cat}→{num}", value=round(top_share, 1),
                        recommendation=f"En etkili {top_n} {cat} kategorisine odaklanın."
                    ))
            except Exception:
                continue


def _extract_concentration(df: pd.DataFrame, cols: list[str], report: InsightReport) -> None:
    """Tek bir değere yoğunlaşma tespiti."""
    for col in cols[:10]:
        try:
            series = df[col].dropna()
            if len(series) < 5:
                continue
            mode_count = series.value_counts().iloc[0]
            pct = mode_count / len(series) * 100
            if pct > 50:
                report.insights.append(Insight(
                    type="concentration", severity="info",
                    title=f"{col} yoğunlaşma",
                    description=f"{col} değerlerinin %{pct:.0f}'i tek bir değerde yoğunlaşmış ({series.mode().iloc[0]})",
                    metric=col, value=round(pct, 1),
                    recommendation="Veri çeşitliliği düşük, segmentasyon gerekebilir."
                ))
        except Exception:
            continue


def _extract_trends(df: pd.DataFrame, cols: list[str], report: InsightReport) -> None:
    """Zaman serisi veya sıralı veri üzerinde trend tespit et."""
    date_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()
    if not date_cols and len(df) < 10:
        return

    for num in cols[:8]:
        try:
            series = df[num].dropna()
            if len(series) < 10:
                continue
            # Basit doğrusal trend (numpy polyfit)
            x = np.arange(len(series))
            coeffs = np.polyfit(x, series.values, 1)
            slope = coeffs[0]
            mean_val = series.mean()
            if mean_val == 0:
                continue
            pct_change = (slope * len(series)) / abs(mean_val) * 100

            if abs(pct_change) > 15:
                direction = "artış" if slope > 0 else "azalış"
                severity = "warning" if abs(pct_change) > 30 else "info"
                report.insights.append(Insight(
                    type="trend", severity=severity,
                    title=f"{num} {direction} trendi",
                    description=f"{num} sütununda %{abs(pct_change):.0f} {direction} trendi tespit edildi.",
                    metric=num, value=round(pct_change, 1),
                    recommendation=f"Bu {'artış' if slope > 0 else 'azalış'} trendinin nedenini araştırın."
                ))
        except Exception:
            continue


def _extract_threshold_violations(df: pd.DataFrame, cols: list[str], report: InsightReport) -> None:
    """Sektörel eşik değer ihlallerini kontrol et."""
    for col in cols:
        col_lower = col.lower().replace(" ", "_").replace("-", "_")
        threshold = TEXTILE_THRESHOLDS.get(col_lower)
        if not threshold:
            continue

        try:
            mean_val = df[col].dropna().mean()
            label = threshold.get("label", col)
            unit = threshold.get("unit", "")

            if "max" in threshold and mean_val > threshold["max"]:
                report.insights.append(Insight(
                    type="threshold", severity="critical",
                    title=f"{label} eşik aşımı",
                    description=f"{label} ortalaması ({mean_val:.1f}{unit}) sektör üst limitini ({threshold['max']}{unit}) aşıyor.",
                    metric=col, value=round(mean_val, 2),
                    recommendation=f"{label} değerini {threshold['max']}{unit} altına indirmek için iyileştirme planı hazırlayın."
                ))
            elif "min" in threshold and mean_val < threshold["min"]:
                report.insights.append(Insight(
                    type="threshold", severity="critical",
                    title=f"{label} eşik altı",
                    description=f"{label} ortalaması ({mean_val:.1f}{unit}) sektör alt limitinin ({threshold['min']}{unit}) altında.",
                    metric=col, value=round(mean_val, 2),
                    recommendation=f"{label} değerini {threshold['min']}{unit} üzerine çıkarmak için aksiyon alın."
                ))
        except Exception:
            continue


def _extract_comparisons(df: pd.DataFrame, cols: list[str], report: InsightReport) -> None:
    """Kategorik gruplara göre performans karşılaştırması."""
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    for cat in cat_cols[:3]:
        try:
            unique = df[cat].nunique()
            if unique < 2 or unique > 20:
                continue
            for num in cols[:5]:
                grouped = df.groupby(cat)[num].mean()
                if len(grouped) < 2:
                    continue
                best = grouped.idxmax()
                worst = grouped.idxmin()
                diff_pct = ((grouped[best] - grouped[worst]) / abs(grouped[worst]) * 100) if grouped[worst] != 0 else 0
                if diff_pct > 30:
                    report.insights.append(Insight(
                        type="comparison", severity="warning",
                        title=f"{cat} bazlı {num} farkı",
                        description=f"{cat} kategorisinde {best} ({grouped[best]:.1f}) ile {worst} ({grouped[worst]:.1f}) arasında %{diff_pct:.0f} fark var.",
                        metric=f"{cat}:{num}", value=round(diff_pct, 1),
                        recommendation=f"{worst} kategorisini {best} seviyesine çıkarmak için best-practice paylaşımı yapın."
                    ))
        except Exception:
            continue


# ══════════════════════════════════════════════════════════════
#  FORMAT / EXPORT
# ══════════════════════════════════════════════════════════════
def format_insight_report(report: InsightReport) -> str:
    """İçgörü raporunu Markdown formatına çevir."""
    if not report.insights:
        return "📊 Otomatik içgörü analizi tamamlandı, önemli bulgu bulunamadı."

    lines = [
        "# 📊 Otomatik İçgörü Raporu",
        f"*{report.row_count} satır × {report.col_count} sütun analiz edildi*\n",
    ]

    severity_icons = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
    type_headers = {
        "correlation": "Korelasyon", "anomaly": "Anomali", "pareto": "Pareto",
        "concentration": "Yoğunlaşma", "trend": "Trend",
        "threshold": "Eşik Kontrolü", "comparison": "Karşılaştırma",
    }

    current_type = None
    for insight in report.insights:
        if insight.type != current_type:
            current_type = insight.type
            header = type_headers.get(current_type, current_type.title())
            lines.append(f"\n## {header} Bulguları")

        icon = severity_icons.get(insight.severity, "⚪")
        lines.append(f"\n### {icon} {insight.title}")
        lines.append(insight.description)
        if insight.recommendation:
            lines.append(f"💡 **Öneri:** {insight.recommendation}")

    critical = sum(1 for i in report.insights if i.severity == "critical")
    warning = sum(1 for i in report.insights if i.severity == "warning")
    lines.append(f"\n---\n*Toplam {len(report.insights)} bulgu: 🔴 {critical} kritik · 🟡 {warning} uyarı*")

    return "\n".join(lines)


def insights_to_dict(report: InsightReport) -> dict:
    """InsightReport'u JSON-serializable dict'e çevir."""
    return {
        "generated_at": report.generated_at,
        "row_count": report.row_count,
        "col_count": report.col_count,
        "total_insights": len(report.insights),
        "critical_count": sum(1 for i in report.insights if i.severity == "critical"),
        "warning_count": sum(1 for i in report.insights if i.severity == "warning"),
        "info_count": sum(1 for i in report.insights if i.severity == "info"),
        "insights": [
            {
                "type": i.type,
                "severity": i.severity,
                "title": i.title,
                "description": i.description,
                "metric": i.metric,
                "value": i.value,
                "recommendation": i.recommendation,
            }
            for i in report.insights
        ],
    }
