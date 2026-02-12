"""Structured JSON Output — LLM çıktılarını yapılandırılmış formata çevirir

LLM'in serbest metin çıktısını parse ederek:
- JSON extraction
- Schema validation
- Tablo algılama ve formatting
- KPI/metrik extraction
"""

import re
import json
from typing import Any, Optional
import structlog

logger = structlog.get_logger()


# ══════════════════════════════════════════════════════════════
# 1. JSON EXTRACTION — LLM çıktısından JSON blokları çıkar
# ══════════════════════════════════════════════════════════════

def extract_json(text: str) -> Optional[dict | list]:
    """LLM çıktısından JSON bloğu çıkar."""
    # 1. ```json ... ``` blokları
    json_blocks = re.findall(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    for block in json_blocks:
        try:
            return json.loads(block.strip())
        except json.JSONDecodeError:
            continue
    
    # 2. Direkt { ... } veya [ ... ] arama
    for pattern in [r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', r'\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]']:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
    
    return None


def force_json_output(text: str, schema: dict = None) -> dict:
    """
    LLM çıktısını her durumda structured dict'e çevirir.
    JSON bulunamazsa metni analiz ederek yapılandırır.
    """
    # Önce direkt JSON dene
    extracted = extract_json(text)
    if extracted and isinstance(extracted, dict):
        if schema:
            return validate_schema(extracted, schema)
        return extracted
    
    # JSON bulunamadı — metni otomatik yapılandır
    return auto_structure(text)


def auto_structure(text: str) -> dict:
    """Serbest metni otomatik olarak yapılandırılmış formata çevirir."""
    result = {
        "summary": "",
        "sections": [],
        "data_tables": [],
        "metrics": {},
        "recommendations": [],
        "risks": [],
        "confidence": 0.7,
    }
    
    lines = text.strip().split('\n')
    current_section = None
    current_content = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        
        # Başlık algılama (##, ###, **, numaralı)
        header_match = re.match(r'^#{1,4}\s+(.+)', stripped)
        bold_header = re.match(r'^\*\*(.+?)\*\*\s*:?\s*(.*)', stripped)
        
        if header_match or bold_header:
            # Önceki bölümü kaydet
            if current_section and current_content:
                result["sections"].append({
                    "title": current_section,
                    "content": '\n'.join(current_content)
                })
            current_section = (header_match.group(1) if header_match 
                             else bold_header.group(1))
            current_content = []
            if bold_header and bold_header.group(2):
                current_content.append(bold_header.group(2))
        else:
            current_content.append(stripped)
        
        # Metrik algılama (sayısal değerler)
        metric_match = re.findall(
            r'[%₺$€]?\s*[\d.,]+\s*[%₺$€]?\s*(?:milyon|milyar|bin|adet|kg|ton|m|gün|saat)?',
            stripped
        )
        if metric_match:
            for m in metric_match:
                clean = m.strip()
                if len(clean) > 1:
                    result["metrics"][f"metric_{len(result['metrics'])+1}"] = clean
        
        # Öneri algılama
        if re.match(r'^[-•✅]\s', stripped) or re.match(r'^\d+[\.\)]\s', stripped):
            content = re.sub(r'^[-•✅\d\.\)]+\s*', '', stripped)
            if any(kw in stripped.lower() for kw in ['öneri', 'tavsiye', 'yapılmalı', 'gerekli']):
                result["recommendations"].append(content)
            elif any(kw in stripped.lower() for kw in ['risk', 'tehlike', 'dikkat', 'uyarı']):
                result["risks"].append(content)
    
    # Son bölümü kaydet
    if current_section and current_content:
        result["sections"].append({
            "title": current_section,
            "content": '\n'.join(current_content)
        })
    
    # Özet — ilk cümle
    first_meaningful = next(
        (l for l in lines if l.strip() and not l.strip().startswith('#')), 
        ""
    )
    result["summary"] = first_meaningful[:200]
    
    # Tablo algılama
    tables = extract_tables(text)
    if tables:
        result["data_tables"] = tables
    
    return result


# ══════════════════════════════════════════════════════════════
# 2. TABLO EXTRACTION — Markdown tablolarını parse et
# ══════════════════════════════════════════════════════════════

def extract_tables(text: str) -> list[dict]:
    """Markdown tablolarını algıla ve dict listesine çevir."""
    tables = []
    
    # Markdown tablo pattern: | col1 | col2 | ...
    table_pattern = re.compile(
        r'(\|[^\n]+\|\n\|[-:\s|]+\|\n(?:\|[^\n]+\|\n?)+)', 
        re.MULTILINE
    )
    
    for match in table_pattern.finditer(text):
        table_text = match.group(0)
        rows = [r.strip() for r in table_text.strip().split('\n') if r.strip()]
        
        if len(rows) < 3:  # header + separator + at least 1 data row
            continue
        
        # Header
        headers = [h.strip() for h in rows[0].split('|') if h.strip()]
        
        # Data rows (skip separator row)
        data = []
        for row in rows[2:]:
            cells = [c.strip() for c in row.split('|') if c.strip()]
            if len(cells) == len(headers):
                data.append(dict(zip(headers, cells)))
        
        if data:
            tables.append({"headers": headers, "rows": data})
    
    return tables


# ══════════════════════════════════════════════════════════════
# 3. SCHEMA VALIDATION
# ══════════════════════════════════════════════════════════════

def validate_schema(data: dict, schema: dict) -> dict:
    """Basit schema validasyonu — eksik alanları default ile doldur."""
    result = {}
    for key, spec in schema.items():
        if key in data:
            expected_type = spec.get("type", "any")
            value = data[key]
            
            # Tip kontrolü
            if expected_type == "string" and not isinstance(value, str):
                value = str(value)
            elif expected_type == "number" and not isinstance(value, (int, float)):
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    value = spec.get("default", 0)
            elif expected_type == "list" and not isinstance(value, list):
                value = [value] if value else []
            
            result[key] = value
        else:
            result[key] = spec.get("default", None)
    
    # Schema'da olmayan ama data'da olan alanlar
    for key in data:
        if key not in result:
            result[key] = data[key]
    
    return result


# ══════════════════════════════════════════════════════════════
# 4. METRİK EXTRACTION — Metinden sayısal değerleri çıkar
# ══════════════════════════════════════════════════════════════

def extract_metrics(text: str) -> dict:
    """Metinden KPI/metrik değerlerini çıkar."""
    metrics = {}
    
    patterns = [
        # Yüzde değerler: %45.2, 45.2%, %45
        (r'%\s*([\d.,]+)', 'percentage'),
        (r'([\d.,]+)\s*%', 'percentage'),
        # Para: ₺1.234, $1,234, 1.234 TL
        (r'[₺$€]\s*([\d.,]+(?:\s*(?:milyon|milyar|bin))?)', 'currency'),
        (r'([\d.,]+)\s*(?:TL|₺|\$|€|USD|EUR)', 'currency'),
        # Süre: 45 gün, 3 saat, 2 hafta
        (r'([\d.,]+)\s*(gün|saat|dakika|hafta|ay|yıl)', 'duration'),
        # Miktar: 1.234 adet, 500 kg, 2.5 ton
        (r'([\d.,]+)\s*(adet|kg|ton|metre|m²|m2|litre|lt)', 'quantity'),
        # Oran: 3:1, 1/4
        (r'(\d+)\s*[:/]\s*(\d+)', 'ratio'),
    ]
    
    for pattern, metric_type in patterns:
        matches = re.findall(pattern, text)
        for i, match in enumerate(matches):
            if isinstance(match, tuple):
                value = ' '.join(match)
            else:
                value = match
            key = f"{metric_type}_{i+1}"
            metrics[key] = {"value": value, "type": metric_type}
    
    return metrics


# ══════════════════════════════════════════════════════════════
# 5. RAPOR SCHEMA'LARI
# ══════════════════════════════════════════════════════════════

REPORT_SCHEMA = {
    "executive_summary": {"type": "string", "default": ""},
    "status": {"type": "string", "default": "normal"},  # critical/warning/normal/good
    "main_finding": {"type": "string", "default": ""},
    "impact": {"type": "string", "default": ""},
    "data": {"type": "list", "default": []},
    "insights": {"type": "list", "default": []},
    "recommendations": {"type": "list", "default": []},
    "risks": {"type": "list", "default": []},
    "next_steps": {"type": "list", "default": []},
    "confidence": {"type": "number", "default": 0.7},
}

KPI_SCHEMA = {
    "kpi_name": {"type": "string", "default": ""},
    "current_value": {"type": "number", "default": 0},
    "target_value": {"type": "number", "default": 0},
    "previous_value": {"type": "number", "default": 0},
    "unit": {"type": "string", "default": ""},
    "trend": {"type": "string", "default": "stable"},  # up/down/stable
    "status": {"type": "string", "default": "normal"},
    "interpretation": {"type": "string", "default": ""},
    "action_required": {"type": "string", "default": ""},
}

ANALYSIS_SCHEMA = {
    "summary": {"type": "string", "default": ""},
    "data_quality": {"type": "string", "default": "iyi"},
    "key_findings": {"type": "list", "default": []},
    "correlations": {"type": "list", "default": []},
    "anomalies": {"type": "list", "default": []},
    "trends": {"type": "list", "default": []},
    "recommendations": {"type": "list", "default": []},
    "risks": {"type": "list", "default": []},
}


# ══════════════════════════════════════════════════════════════
# 6. EXECUTIVE OUTPUT SCHEMA — Tier-0 Enterprise Çıktı Şeması
# ══════════════════════════════════════════════════════════════

EXECUTIVE_SCHEMA = {
    "executive_summary": {"type": "string", "default": ""},
    "data_integrity_score": {"type": "number", "default": 70},
    "kpi_analysis": {"type": "dict", "default": {}},
    "risk_analysis": {"type": "dict", "default": {}},
    "financial_impact_projection": {"type": "dict", "default": {}},
    "graph_impact_analysis": {"type": "dict", "default": {}},
    "scenario_simulation": {
        "type": "dict",
        "default": {"best_case": "", "expected_case": "", "worst_case": ""},
    },
    "decision_priority_ranking": {"type": "list", "default": []},
    "strategic_recommendations": {"type": "dict", "default": {}},
    "confidence": {"type": "number", "default": 0.7},
}


def get_schema_for_mode(mode: str) -> Optional[dict]:
    """Moda göre uygun schema döndür."""
    schemas = {
        "Rapor": REPORT_SCHEMA,
        "Analiz": ANALYSIS_SCHEMA,
        "Executive": EXECUTIVE_SCHEMA,
    }
    return schemas.get(mode)
