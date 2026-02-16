"""Structured JSON Output — LLM çıktılarını yapılandırılmış formata çevirir

JSON extraction (tekli+çoklu), gelişmiş schema validation (nested, enum,
regex, min/max), tablo algılama, KPI/metrik extraction, YAML-benzeri parsing,
güven skoru, çıktı şablonları, schema registry ve istatistik dashboard.
"""

import re
import json
from typing import Any, Optional
import structlog

logger = structlog.get_logger()

# ── Rapor Şemaları ───────────────────────────────────────────

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

# ── Output Templates ─────────────────────────────────────────

_OUTPUT_TEMPLATES: dict[str, str] = {
    "rapor_ozet": (
        "📊 **Rapor Özeti**\n"
        "Durum: {status}\n"
        "Özet: {executive_summary}\n"
        "Temel Bulgu: {main_finding}\n"
        "Etki: {impact}\n"
        "Güven Skoru: {confidence}\n"
    ),
    "kpi_kart": (
        "📈 **{kpi_name}**\n"
        "Güncel: {current_value} {unit} | Hedef: {target_value} {unit}\n"
        "Trend: {trend} | Durum: {status}\n"
        "Yorum: {interpretation}\n"
    ),
    "analiz_ozet": (
        "🔍 **Analiz Sonuçları**\n"
        "Özet: {summary}\n"
        "Veri Kalitesi: {data_quality}\n"
        "Anahtar Bulgular: {key_findings}\n"
        "Öneriler: {recommendations}\n"
    ),
    "executive_brief": (
        "🏢 **Yönetici Brifing**\n"
        "Özet: {executive_summary}\n"
        "Veri Bütünlük Skoru: {data_integrity_score}\n"
        "Stratejik Öneriler: {strategic_recommendations}\n"
        "Güven: {confidence}\n"
    ),
}

# ── StructuredOutputParser — Singleton ────────────────────────

class StructuredOutputParser:
    """Merkezi singleton parser — extraction, validation, template, istatistik."""

    _instance: Optional["StructuredOutputParser"] = None

    def __new__(cls) -> "StructuredOutputParser":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._stats: dict[str, Any] = {
            "total_parses": 0, "json_extracted": 0, "json_failed": 0,
            "multi_json_extracted": 0, "tables_found": 0,
            "schemas_validated": 0, "schema_errors": 0,
            "yaml_parsed": 0, "templates_rendered": 0,
            "avg_confidence": 0.0, "_confidence_sum": 0.0,
            "_confidence_count": 0,
        }
        self._custom_schemas: dict[str, dict] = {}

    # ── İstatistik & Dashboard ──

    def _track_confidence(self, score: float) -> None:
        self._stats["_confidence_sum"] += score
        self._stats["_confidence_count"] += 1
        cnt = self._stats["_confidence_count"]
        self._stats["avg_confidence"] = round(self._stats["_confidence_sum"] / cnt, 4)

    def get_dashboard(self) -> dict:
        """Parser istatistik panosunu döndürür."""
        public = {k: v for k, v in self._stats.items() if not k.startswith("_")}
        public["registered_schemas"] = len(self._custom_schemas)
        public["available_templates"] = list(_OUTPUT_TEMPLATES.keys())
        return public

    def reset_stats(self) -> None:
        for key in self._stats:
            if isinstance(self._stats[key], (int, float)):
                self._stats[key] = 0 if isinstance(self._stats[key], int) else 0.0

    # ── JSON Extraction ──

    def extract_json(self, text: str) -> Optional[dict | list]:
        """LLM çıktısından ilk JSON bloğunu çıkar."""
        self._stats["total_parses"] += 1
        # ```json ... ``` blokları
        json_blocks = re.findall(
            r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL
        )
        for block in json_blocks:
            try:
                parsed = json.loads(block.strip())
                self._stats["json_extracted"] += 1
                return parsed
            except json.JSONDecodeError:
                continue
        # Direkt { ... } veya [ ... ] arama
        for pattern in [
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
            r'\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]',
        ]:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    parsed = json.loads(match)
                    self._stats["json_extracted"] += 1
                    return parsed
                except json.JSONDecodeError:
                    continue

        self._stats["json_failed"] += 1
        return None

    def extract_all_json(self, text: str) -> list[dict | list]:
        """Metindeki TÜM JSON bloklarını çıkar."""
        self._stats["total_parses"] += 1
        results: list[dict | list] = []
        # Fenced code blokları
        json_blocks = re.findall(
            r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL
        )
        for block in json_blocks:
            try:
                results.append(json.loads(block.strip()))
            except json.JSONDecodeError:
                continue
        # Serbest { ... } ve [ ... ] blokları
        for pattern in [
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
            r'\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]',
        ]:
            for match in re.findall(pattern, text, re.DOTALL):
                try:
                    parsed = json.loads(match)
                    # Tekrar ekleme kontrolü
                    if parsed not in results:
                        results.append(parsed)
                except json.JSONDecodeError:
                    continue

        if results:
            self._stats["multi_json_extracted"] += len(results)
            self._stats["json_extracted"] += len(results)
        else:
            self._stats["json_failed"] += 1

        return results

    # ── YAML-benzeri key:value parsing ──

    def parse_yaml_like(self, text: str) -> dict:
        """LLM çıktısındaki 'Anahtar: Değer' satırlarını dict'e çevirir."""
        result: dict[str, Any] = {}
        pattern = re.compile(
            r'^\s*\*{0,2}([A-Za-zÇçĞğİıÖöŞşÜü_][\w\s]*?)\*{0,2}\s*:\s*(.+)',
            re.MULTILINE,
        )
        for match in pattern.finditer(text):
            key = match.group(1).strip().lower().replace(" ", "_")
            raw_value = match.group(2).strip()

            # Sayısal değer dönüşümü
            if re.fullmatch(r'-?[\d.,]+', raw_value):
                cleaned = raw_value.replace(".", "").replace(",", ".")
                try:
                    value: Any = float(cleaned)
                    if value == int(value):
                        value = int(value)
                except ValueError:
                    value = raw_value
            elif raw_value.lower() in ("evet", "true", "yes"):
                value = True
            elif raw_value.lower() in ("hayır", "false", "no"):
                value = False
            else:
                value = raw_value

            result[key] = value

        if result:
            self._stats["yaml_parsed"] += 1
        return result

    # ── Confidence (Güven) Skoru ──

    def compute_confidence(self, text: str, extracted: Any) -> float:
        """Extraction güven skorunu hesaplar (0.0 – 1.0)."""
        score = 0.0

        # JSON başarıyla çıkarıldıysa yüksek başlangıç
        if extracted is not None:
            score += 0.45
            # Dict ise ve anahtar zenginliği
            if isinstance(extracted, dict) and len(extracted) >= 3:
                score += 0.15
            elif isinstance(extracted, list) and len(extracted) >= 1:
                score += 0.10
        else:
            score += 0.10  # Hiç JSON bulunamadı

        # Yapısal ipuçları
        if re.search(r'```(?:json)?', text):
            score += 0.10  # Fenced code bloğu var
        if re.search(r'\|.+\|', text):
            score += 0.05  # Tablo varlığı
        if re.search(r'^#{1,4}\s+', text, re.MULTILINE):
            score += 0.05  # Markdown başlık
        if re.search(r'^[-•✅]\s', text, re.MULTILINE):
            score += 0.05  # Liste öğeleri

        # Metin kısalık bonusu — çok uzun metin genelde daha az yapısal
        length = len(text)
        if 50 < length < 2000:
            score += 0.10
        elif length <= 50:
            score += 0.05

        final = round(min(score, 1.0), 2)
        self._track_confidence(final)
        return final

    # ── Gelişmiş Schema Validation ──

    def validate_schema(self, data: dict, schema: dict) -> dict:
        """Gelişmiş schema validasyonu (nested, enum, regex, min/max, required)."""
        self._stats["schemas_validated"] += 1
        errors: list[str] = []
        result = self._validate_object(data, schema, errors, path="")

        # Schema'da olmayan ama data'da olan alanları koru
        for key in data:
            if key not in result:
                result[key] = data[key]

        if errors:
            self._stats["schema_errors"] += len(errors)
            logger.warning(
                "schema_validation_errors",
                error_count=len(errors),
                errors=errors[:10],
            )

        return result

    def _validate_object(self, data: dict, schema: dict, errors: list, path: str) -> dict:
        """Özyinelemeli obje validasyonu."""
        result: dict[str, Any] = {}
        for key, spec in schema.items():
            full_path = f"{path}.{key}" if path else key
            if spec.get("required") and key not in data:
                errors.append(f"Zorunlu alan eksik: {full_path}")
            if key in data:
                value = data[key]
                value = self._coerce_type(value, spec, errors, full_path)
                value = self._apply_constraints(value, spec, errors, full_path)
                # Nested obje validasyonu
                if spec.get("type") == "dict" and isinstance(value, dict) and "properties" in spec:
                    value = self._validate_object(value, spec["properties"], errors, full_path)
                # Array item validasyonu
                if spec.get("type") == "list" and isinstance(value, list) and "items" in spec:
                    value = self._validate_array_items(value, spec["items"], errors, full_path)
                result[key] = value
            else:
                result[key] = spec.get("default", None)
        return result

    def _coerce_type(self, value: Any, spec: dict, errors: list, path: str) -> Any:
        """Değeri beklenen tipe zorlar."""
        expected = spec.get("type", "any")
        if expected == "string" and not isinstance(value, str):
            value = str(value)
        elif expected == "number" and not isinstance(value, (int, float)):
            try:
                value = float(value)
            except (ValueError, TypeError):
                errors.append(f"Sayısal dönüşüm hatası: {path}")
                value = spec.get("default", 0)
        elif expected == "list" and not isinstance(value, list):
            value = [value] if value else []
        elif expected == "dict" and not isinstance(value, dict):
            try:
                value = json.loads(value) if isinstance(value, str) else {}
            except (json.JSONDecodeError, TypeError):
                errors.append(f"Dict dönüşüm hatası: {path}")
                value = spec.get("default", {})
        elif expected == "bool" and not isinstance(value, bool):
            value = bool(value)
        return value

    def _apply_constraints(self, value: Any, spec: dict, errors: list, path: str) -> Any:
        """Enum, regex, min/max, minLength/maxLength kısıtlamalarını uygular."""
        if "enum" in spec and value not in spec["enum"]:
            errors.append(f"Enum hatası ({path}): '{value}' ∉ {spec['enum']}")
            value = spec.get("default", spec["enum"][0] if spec["enum"] else value)
        if "pattern" in spec and isinstance(value, str):
            if not re.search(spec["pattern"], value):
                errors.append(f"Pattern hatası ({path}): '{value}' eşleşmiyor")
        if isinstance(value, (int, float)):
            if "min" in spec and value < spec["min"]:
                errors.append(f"Min hatası ({path}): {value} < {spec['min']}")
                value = spec["min"]
            if "max" in spec and value > spec["max"]:
                errors.append(f"Max hatası ({path}): {value} > {spec['max']}")
                value = spec["max"]
        if isinstance(value, str):
            if "minLength" in spec and len(value) < spec["minLength"]:
                errors.append(f"minLength hatası ({path}): len={len(value)} < {spec['minLength']}")
            if "maxLength" in spec and len(value) > spec["maxLength"]:
                value = value[: spec["maxLength"]]
                errors.append(f"maxLength aşıldı, kesildi ({path})")
        return value

    def _validate_array_items(self, items: list, item_spec: dict, errors: list, path: str) -> list:
        """Dizideki her öğeyi item schema'sına göre doğrular."""
        validated: list[Any] = []
        for idx, item in enumerate(items):
            item_path = f"{path}[{idx}]"
            if isinstance(item, dict) and "properties" in item_spec:
                validated.append(self._validate_object(item, item_spec["properties"], errors, item_path))
            else:
                coerced = self._coerce_type(item, item_spec, errors, item_path)
                coerced = self._apply_constraints(coerced, item_spec, errors, item_path)
                validated.append(coerced)
        return validated

    # ── Force JSON & Auto Structure ──

    def force_json_output(self, text: str, schema: dict = None) -> dict:
        """LLM çıktısını her durumda structured dict'e çevirir."""
        # Önce direkt JSON dene
        extracted = self.extract_json(text)
        if extracted and isinstance(extracted, dict):
            if schema:
                return self.validate_schema(extracted, schema)
            return extracted

        # JSON bulunamadı — metni otomatik yapılandır
        return self.auto_structure(text)

    def auto_structure(self, text: str) -> dict:
        """Serbest metni otomatik yapılandırılmış formata çevirir."""
        result: dict[str, Any] = {
            "summary": "", "sections": [], "data_tables": [],
            "metrics": {}, "recommendations": [], "risks": [],
            "confidence": 0.7,
        }
        lines = text.strip().split('\n')
        current_section: Optional[str] = None
        current_content: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            header_match = re.match(r'^#{1,4}\s+(.+)', stripped)
            bold_header = re.match(r'^\*\*(.+?)\*\*\s*:?\s*(.*)', stripped)
            if header_match or bold_header:
                if current_section and current_content:
                    result["sections"].append({
                        "title": current_section,
                        "content": '\n'.join(current_content),
                    })
                current_section = header_match.group(1) if header_match else bold_header.group(1)
                current_content = []
                if bold_header and bold_header.group(2):
                    current_content.append(bold_header.group(2))
            else:
                current_content.append(stripped)
            metric_match = re.findall(
                r'[%₺$€]?\s*[\d.,]+\s*[%₺$€]?'
                r'\s*(?:milyon|milyar|bin|adet|kg|ton|m|gün|saat)?',
                stripped,
            )
            if metric_match:
                for m in metric_match:
                    clean = m.strip()
                    if len(clean) > 1:
                        result["metrics"][f"metric_{len(result['metrics']) + 1}"] = clean
            if re.match(r'^[-•✅]\s', stripped) or re.match(r'^\d+[\.\)]\s', stripped):
                content = re.sub(r'^[-•✅\d\.\)]+\s*', '', stripped)
                if any(kw in stripped.lower() for kw in ['öneri', 'tavsiye', 'yapılmalı', 'gerekli']):
                    result["recommendations"].append(content)
                elif any(kw in stripped.lower() for kw in ['risk', 'tehlike', 'dikkat', 'uyarı']):
                    result["risks"].append(content)
        if current_section and current_content:
            result["sections"].append({
                "title": current_section,
                "content": '\n'.join(current_content),
            })
        first_meaningful = next(
            (l for l in lines if l.strip() and not l.strip().startswith('#')), "",
        )
        result["summary"] = first_meaningful[:200]
        tables = self.extract_tables(text)
        if tables:
            result["data_tables"] = tables
        result["confidence"] = self.compute_confidence(text, result)
        return result

    # ── Tablo Extraction ──

    def extract_tables(self, text: str) -> list[dict]:
        """Markdown tablolarını algıla ve dict listesine çevir."""
        tables: list[dict] = []
        table_pattern = re.compile(
            r'(\|[^\n]+\|\n\|[-:\s|]+\|\n(?:\|[^\n]+\|\n?)+)',
            re.MULTILINE,
        )
        for match in table_pattern.finditer(text):
            table_text = match.group(0)
            rows = [r.strip() for r in table_text.strip().split('\n') if r.strip()]
            if len(rows) < 3:
                continue
            headers = [h.strip() for h in rows[0].split('|') if h.strip()]
            data: list[dict] = []
            for row in rows[2:]:
                cells = [c.strip() for c in row.split('|') if c.strip()]
                if len(cells) == len(headers):
                    data.append(dict(zip(headers, cells)))

            if data:
                tables.append({"headers": headers, "rows": data})
                self._stats["tables_found"] += 1
        return tables

    # ── Metrik Extraction ──

    def extract_metrics(self, text: str) -> dict:
        """Metinden KPI/metrik değerlerini çıkar."""
        metrics: dict[str, dict] = {}
        patterns = [
            (r'%\s*([\d.,]+)', 'percentage'),
            (r'([\d.,]+)\s*%', 'percentage'),
            (r'[₺$€]\s*([\d.,]+(?:\s*(?:milyon|milyar|bin))?)', 'currency'),
            (r'([\d.,]+)\s*(?:TL|₺|\$|€|USD|EUR)', 'currency'),
            (r'([\d.,]+)\s*(gün|saat|dakika|hafta|ay|yıl)', 'duration'),
            (r'([\d.,]+)\s*(adet|kg|ton|metre|m²|m2|litre|lt)', 'quantity'),
            (r'(\d+)\s*[:/]\s*(\d+)', 'ratio'),
        ]
        for pattern, metric_type in patterns:
            matches = re.findall(pattern, text)
            for i, match in enumerate(matches):
                if isinstance(match, tuple):
                    value = ' '.join(match)
                else:
                    value = match
                key = f"{metric_type}_{i + 1}"
                metrics[key] = {"value": value, "type": metric_type}

        return metrics

    # ── Schema Registry ──

    def register_schema(self, name: str, schema: dict) -> None:
        """Özel schema kaydeder."""
        self._custom_schemas[name] = schema
        logger.info("schema_registered", name=name, keys=list(schema.keys()))

    def get_registered_schema(self, name: str) -> Optional[dict]:
        """Kayıtlı özel schema'yı döndürür."""
        return self._custom_schemas.get(name)

    def list_schemas(self) -> list[str]:
        """Tüm kayıtlı schema isimlerini döndürür."""
        built_in = ["Rapor", "Analiz", "Executive"]
        custom = list(self._custom_schemas.keys())
        return built_in + custom

    def get_schema_for_mode(self, mode: str) -> Optional[dict]:
        """Moda göre uygun schema döndürür (yerleşik + özel)."""
        built_in = {"Rapor": REPORT_SCHEMA, "Analiz": ANALYSIS_SCHEMA, "Executive": EXECUTIVE_SCHEMA}
        return built_in.get(mode) or self._custom_schemas.get(mode)

    # ── Output Templates ──

    def render_template(self, template_name: str, data: dict) -> str:
        """Veriyi şablona göre formatlar, bulunamazsa JSON döner."""
        self._stats["templates_rendered"] += 1
        tmpl = _OUTPUT_TEMPLATES.get(template_name)
        if not tmpl:
            logger.warning("template_not_found", name=template_name)
            return json.dumps(data, ensure_ascii=False, indent=2)

        try:
            return tmpl.format_map(_SafeFormatDict(data))
        except Exception:
            return json.dumps(data, ensure_ascii=False, indent=2)

    def register_template(self, name: str, template: str) -> None:
        """Yeni çıktı şablonu kaydeder."""
        _OUTPUT_TEMPLATES[name] = template
        logger.info("template_registered", name=name)


class _SafeFormatDict(dict):
    """Eksik anahtarları '—' ile dolduran format_map yardımcısı."""
    def __missing__(self, key: str) -> str:
        return "—"


# ── Modül Seviyesi Fonksiyonlar — geriye dönük uyumluluk ─────

def _parser() -> StructuredOutputParser:
    """Singleton parser erişimi."""
    return StructuredOutputParser()


def extract_json(text: str) -> Optional[dict | list]:
    return _parser().extract_json(text)

def extract_all_json(text: str) -> list[dict | list]:
    return _parser().extract_all_json(text)

def force_json_output(text: str, schema: dict = None) -> dict:
    return _parser().force_json_output(text, schema)

def auto_structure(text: str) -> dict:
    return _parser().auto_structure(text)

def extract_tables(text: str) -> list[dict]:
    return _parser().extract_tables(text)

def validate_schema(data: dict, schema: dict) -> dict:
    return _parser().validate_schema(data, schema)

def extract_metrics(text: str) -> dict:
    return _parser().extract_metrics(text)

def get_schema_for_mode(mode: str) -> Optional[dict]:
    return _parser().get_schema_for_mode(mode)

def parse_yaml_like(text: str) -> dict:
    return _parser().parse_yaml_like(text)

def compute_confidence(text: str, extracted: Any) -> float:
    return _parser().compute_confidence(text, extracted)

def get_dashboard() -> dict:
    return _parser().get_dashboard()

def register_schema(name: str, schema: dict) -> None:
    _parser().register_schema(name, schema)

def render_template(template_name: str, data: dict) -> str:
    return _parser().render_template(template_name, data)
