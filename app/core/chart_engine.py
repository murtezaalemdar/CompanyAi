"""Chart Engine — Grafik/Görselleştirme Motoru (v4.4.0)

Veri analiz sonuçlarından otomatik grafik üretir.
Desteklenen grafikler:
- Çubuk grafik (bar)
- Çizgi grafik (line)
- Pasta grafik (pie)
- Karşılaştırma (grouped bar)
- Trend çizgisi (line + marker)
- Isı haritası (heatmap)

Çıktı: Base64 PNG veya dosya yolu
"""

import io
import re
import base64
import structlog
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

logger = structlog.get_logger()

# Matplotlib — headless mode
try:
    import matplotlib
    matplotlib.use('Agg')  # Headless
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    plt.rcParams['font.family'] = 'DejaVu Sans'
    plt.rcParams['figure.dpi'] = 150
    plt.rcParams['figure.figsize'] = (10, 6)
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib_not_installed", message="Grafik özellikleri devre dışı")

# CompanyAI renk paleti
COLORS = [
    '#2563eb',  # Mavi
    '#dc2626',  # Kırmızı
    '#16a34a',  # Yeşil
    '#ea580c',  # Turuncu
    '#9333ea',  # Mor
    '#0891b2',  # Cyan
    '#ca8a04',  # Sarı
    '#6b7280',  # Gri
]


def create_bar_chart(
    labels: List[str],
    values: List[float],
    title: str = "Grafik",
    xlabel: str = "",
    ylabel: str = "",
    color: str = None,
    horizontal: bool = False,
    show_values: bool = True,
) -> Dict[str, Any]:
    """Çubuk grafik oluştur.
    
    Returns:
        {"image_base64": str, "format": "png", "width": int, "height": int}
    """
    if not MATPLOTLIB_AVAILABLE:
        return {"error": "matplotlib yüklü değil"}
    
    try:
        fig, ax = plt.subplots()
        bar_color = color or COLORS[0]
        
        if horizontal:
            bars = ax.barh(labels, values, color=bar_color, edgecolor='white')
            if show_values:
                for bar, val in zip(bars, values):
                    ax.text(bar.get_width() + max(values) * 0.02, bar.get_y() + bar.get_height() / 2,
                            f'{val:,.1f}', va='center', fontsize=9)
            ax.set_xlabel(ylabel)
            ax.set_ylabel(xlabel)
        else:
            bars = ax.bar(labels, values, color=bar_color, edgecolor='white')
            if show_values:
                for bar, val in zip(bars, values):
                    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(values) * 0.02,
                            f'{val:,.1f}', ha='center', fontsize=9)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            plt.xticks(rotation=45, ha='right')
        
        ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(axis='y' if not horizontal else 'x', alpha=0.3)
        
        plt.tight_layout()
        return _fig_to_result(fig)
        
    except Exception as e:
        logger.error("bar_chart_failed", error=str(e))
        return {"error": str(e)}


def create_line_chart(
    x_labels: List[str],
    series: Dict[str, List[float]],
    title: str = "Trend",
    xlabel: str = "",
    ylabel: str = "",
    show_markers: bool = True,
) -> Dict[str, Any]:
    """Çizgi grafik (çoklu seri destekli).
    
    Args:
        x_labels: X ekseni etiketleri
        series: {"seri_adı": [değerler]} — birden fazla çizgi
        title: Başlık
    """
    if not MATPLOTLIB_AVAILABLE:
        return {"error": "matplotlib yüklü değil"}
    
    try:
        fig, ax = plt.subplots()
        
        for i, (name, values) in enumerate(series.items()):
            color = COLORS[i % len(COLORS)]
            marker = 'o' if show_markers else None
            ax.plot(x_labels[:len(values)], values, color=color, marker=marker,
                    linewidth=2, markersize=6, label=name)
        
        ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.legend(loc='best', framealpha=0.9)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(alpha=0.3)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        return _fig_to_result(fig)
        
    except Exception as e:
        logger.error("line_chart_failed", error=str(e))
        return {"error": str(e)}


def create_pie_chart(
    labels: List[str],
    values: List[float],
    title: str = "Dağılım",
    show_percent: bool = True,
) -> Dict[str, Any]:
    """Pasta grafik."""
    if not MATPLOTLIB_AVAILABLE:
        return {"error": "matplotlib yüklü değil"}
    
    try:
        fig, ax = plt.subplots()
        colors = COLORS[:len(labels)]
        
        autopct = '%1.1f%%' if show_percent else None
        wedges, texts, autotexts = ax.pie(
            values, labels=labels, colors=colors,
            autopct=autopct, startangle=90,
            pctdistance=0.75,
        )
        
        for text in autotexts:
            text.set_fontsize(9)
            text.set_fontweight('bold')
        
        ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
        plt.tight_layout()
        
        return _fig_to_result(fig)
        
    except Exception as e:
        logger.error("pie_chart_failed", error=str(e))
        return {"error": str(e)}


def create_grouped_bar(
    labels: List[str],
    groups: Dict[str, List[float]],
    title: str = "Karşılaştırma",
    xlabel: str = "",
    ylabel: str = "",
) -> Dict[str, Any]:
    """Gruplu çubuk grafik — birden fazla seriyi yan yana."""
    if not MATPLOTLIB_AVAILABLE:
        return {"error": "matplotlib yüklü değil"}
    
    try:
        import numpy as np
        fig, ax = plt.subplots()
        
        n_groups = len(labels)
        n_series = len(groups)
        bar_width = 0.8 / n_series
        x = np.arange(n_groups)
        
        for i, (name, values) in enumerate(groups.items()):
            offset = (i - n_series / 2 + 0.5) * bar_width
            bars = ax.bar(x + offset, values[:n_groups], bar_width,
                         label=name, color=COLORS[i % len(COLORS)],
                         edgecolor='white')
        
        ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.legend(loc='best', framealpha=0.9)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        
        return _fig_to_result(fig)
        
    except Exception as e:
        logger.error("grouped_bar_failed", error=str(e))
        return {"error": str(e)}


def create_heatmap(
    data: List[List[float]],
    row_labels: List[str],
    col_labels: List[str],
    title: str = "Isı Haritası",
    cmap: str = "YlOrRd",
) -> Dict[str, Any]:
    """Isı haritası."""
    if not MATPLOTLIB_AVAILABLE:
        return {"error": "matplotlib yüklü değil"}
    
    try:
        import numpy as np
        fig, ax = plt.subplots()
        
        arr = np.array(data)
        im = ax.imshow(arr, cmap=cmap, aspect='auto')
        
        ax.set_xticks(range(len(col_labels)))
        ax.set_yticks(range(len(row_labels)))
        ax.set_xticklabels(col_labels, rotation=45, ha='right')
        ax.set_yticklabels(row_labels)
        
        # Değerleri hücrelere yaz
        for i in range(len(row_labels)):
            for j in range(len(col_labels)):
                if i < arr.shape[0] and j < arr.shape[1]:
                    ax.text(j, i, f'{arr[i, j]:.1f}',
                           ha='center', va='center', fontsize=8,
                           color='white' if arr[i, j] > arr.max() * 0.6 else 'black')
        
        fig.colorbar(im, ax=ax, shrink=0.8)
        ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
        plt.tight_layout()
        
        return _fig_to_result(fig)
        
    except Exception as e:
        logger.error("heatmap_failed", error=str(e))
        return {"error": str(e)}


def auto_chart_from_data(
    data: Dict[str, Any],
    title: str = None,
) -> Dict[str, Any]:
    """Veriden otomatik en uygun grafik tipini seç ve oluştur.
    
    Heuristik:
    - key:value çiftleri → bar chart
    - Zaman serisi → line chart
    - Dağılım/yüzde → pie chart
    - Matris → heatmap
    """
    if not data:
        return {"error": "Veri boş"}
    
    # Dict[str, number] → basit bar chart
    if all(isinstance(v, (int, float)) for v in data.values()):
        labels = list(data.keys())
        values = list(data.values())
        
        # Yüzde toplamı ~100 ise pie chart
        total = sum(values)
        if 95 <= total <= 105 and len(values) <= 8:
            return create_pie_chart(labels, values, title=title or "Dağılım")
        
        return create_bar_chart(labels, values, title=title or "Grafik")
    
    # Dict[str, list] → line chart veya grouped bar
    if all(isinstance(v, list) for v in data.values()):
        first_key = list(data.keys())[0]
        if first_key.lower() in ('x', 'labels', 'etiketler', 'aylar', 'tarih'):
            x_labels = [str(x) for x in data[first_key]]
            series = {k: v for k, v in data.items() if k != first_key}
            return create_line_chart(x_labels, series, title=title or "Trend")
        
        # Hepsi aynı uzunlukta → grouped bar
        lengths = [len(v) for v in data.values()]
        if len(set(lengths)) == 1:
            first_vals = list(data.values())[0]
            if all(isinstance(x, str) for x in first_vals):
                labels = first_vals
                groups = {k: v for k, v in list(data.items())[1:]}
                return create_grouped_bar(labels, groups, title=title or "Karşılaştırma")
    
    return {"error": "Veri formatı otomatik grafik için uygun değil"}


def extract_chart_data_from_text(text: str) -> Optional[Dict]:
    """LLM yanıtından tablo/veri çıkar ve chart'a dönüştür.
    
    Markdown tabloları ve key:value listelerini otomatik algılar.
    """
    if not text:
        return None
    
    # Markdown tablo algılama: | A | B | C |
    table_match = re.findall(r'^\|(.+)\|$', text, re.MULTILINE)
    if len(table_match) >= 3:
        try:
            # Header
            headers = [h.strip() for h in table_match[0].split('|') if h.strip()]
            # Separator satırını atla
            data_rows = []
            for row_text in table_match[2:]:
                if '---' in row_text:
                    continue
                cells = [c.strip() for c in row_text.split('|') if c.strip()]
                if cells:
                    data_rows.append(cells)
            
            if headers and data_rows:
                # İlk sütun etiket, geri kalanlar sayısal mı?
                labels = [row[0] for row in data_rows if row]
                values = []
                for row in data_rows:
                    if len(row) >= 2:
                        try:
                            val = float(re.sub(r'[^\d.,\-]', '', row[1]).replace(',', '.'))
                            values.append(val)
                        except (ValueError, IndexError):
                            pass
                
                if labels and values and len(labels) == len(values):
                    return {
                        "type": "bar",
                        "labels": labels,
                        "values": values,
                        "title": headers[0] if headers else "Grafik",
                        "ylabel": headers[1] if len(headers) > 1 else "",
                    }
        except Exception:
            pass
    
    # Basit key: value formatı algılama
    kv_matches = re.findall(r'[-•*]\s*(.+?):\s*([\d.,]+)\s*(?:%|TL|ton|adet|kg)?', text)
    if len(kv_matches) >= 3:
        labels = [m[0].strip() for m in kv_matches]
        values = []
        for m in kv_matches:
            try:
                values.append(float(m[1].replace(',', '.')))
            except ValueError:
                pass
        if len(labels) == len(values):
            return {
                "type": "bar",
                "labels": labels,
                "values": values,
            }
    
    return None


# ── Yardımcı ──

def _fig_to_result(fig) -> Dict[str, Any]:
    """Matplotlib figure'ı base64 PNG'ye çevir."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)
    
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    
    return {
        "image_base64": img_base64,
        "format": "png",
        "mime_type": "image/png",
    }


def get_chart_capabilities() -> Dict:
    """Grafik motor yetenekleri."""
    return {
        "available": MATPLOTLIB_AVAILABLE,
        "chart_types": [
            "bar", "horizontal_bar", "line", "pie",
            "grouped_bar", "heatmap", "auto",
        ] if MATPLOTLIB_AVAILABLE else [],
        "output_format": "base64_png",
    }
