"""Tool Calling / Function Calling Sistemi

LLM'in kullanabileceği araçları tanımlar ve çalıştırır.
ReAct pattern ile entegre çalışır.

Araçlar:
- calculate: Matematiksel hesaplama
- search_documents: RAG bilgi tabanında ara
- web_search: İnternette ara
- analyze_data: Veri analizi (pivot, istatistik, trend)
- kpi_interpret: KPI değerini yorumla
- forecast: Tahminleme yap
- risk_assess: Risk değerlendirmesi
- sql_query: Doğal dilden SQL üret
- export_report: Rapor dosyası üret
"""

import re
import json
import math
from typing import Any, Optional, Callable
import structlog

logger = structlog.get_logger()


# ══════════════════════════════════════════════════════════════
# 1. TOOL REGISTRY — Araç tanımları
# ══════════════════════════════════════════════════════════════

class Tool:
    """Tek bir araç tanımı."""
    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler: Callable,
        category: str = "general",
    ):
        self.name = name
        self.description = description
        self.parameters = parameters  # {"param_name": {"type": "string", "description": "...", "required": True}}
        self.handler = handler
        self.category = category
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "category": self.category,
        }


class ToolRegistry:
    """Araç kayıt ve yönetim sistemi."""
    
    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._register_builtin_tools()
    
    def register(self, tool: Tool):
        self._tools[tool.name] = tool
        logger.debug("tool_registered", name=tool.name)
    
    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)
    
    def list_tools(self, category: str = None) -> list[dict]:
        tools = self._tools.values()
        if category:
            tools = [t for t in tools if t.category == category]
        return [t.to_dict() for t in tools]
    
    async def execute(self, tool_name: str, params: dict) -> dict:
        """Aracı çalıştır ve sonuç döndür."""
        tool = self._tools.get(tool_name)
        if not tool:
            return {"success": False, "error": f"Araç bulunamadı: {tool_name}"}
        
        try:
            # Parametre validasyonu
            for p_name, p_spec in tool.parameters.items():
                if p_spec.get("required") and p_name not in params:
                    return {"success": False, "error": f"Eksik parametre: {p_name}"}
            
            # Çalıştır
            import asyncio
            if asyncio.iscoroutinefunction(tool.handler):
                result = await tool.handler(**params)
            else:
                result = tool.handler(**params)
            
            logger.info("tool_executed", tool=tool_name, success=True)
            return {"success": True, "result": result, "tool": tool_name}
        
        except Exception as e:
            logger.error("tool_execution_error", tool=tool_name, error=str(e))
            return {"success": False, "error": str(e), "tool": tool_name}
    
    def _register_builtin_tools(self):
        """Yerleşik araçları kaydet."""
        # 1. Calculator
        self.register(Tool(
            name="calculate",
            description="Matematiksel hesaplama yapar. Dört işlem, yüzde, üs, karekök, trigonometri.",
            parameters={
                "expression": {"type": "string", "description": "Hesaplanacak matematiksel ifade", "required": True},
            },
            handler=_tool_calculate,
            category="math",
        ))
        
        # 2. KPI Yorumlama
        self.register(Tool(
            name="kpi_interpret",
            description="KPI değerini sektörel benchmark'larla karşılaştırarak yorumlar.",
            parameters={
                "kpi_name": {"type": "string", "description": "KPI adı (fire_orani, oee, brut_kar_marji, personel_devir, nakit_cevrim)", "required": True},
                "value": {"type": "number", "description": "KPI'ın mevcut değeri", "required": True},
            },
            handler=_tool_kpi_interpret,
            category="analysis",
        ))
        
        # 3. Risk Değerlendirmesi
        self.register(Tool(
            name="risk_assess",
            description="Risk değerlendirmesi yapar. Olasılık × Etki matrisi ile risk skoru hesaplar.",
            parameters={
                "risk_name": {"type": "string", "description": "Risk adı/açıklaması", "required": True},
                "probability": {"type": "number", "description": "Olasılık (1-5)", "required": True},
                "impact": {"type": "number", "description": "Etki (1-5)", "required": True},
                "category": {"type": "string", "description": "Kategori: operasyonel/finansal/insan/stratejik/uyum", "required": False},
            },
            handler=_tool_risk_assess,
            category="analysis",
        ))
        
        # 4. Birim Dönüştürücü
        self.register(Tool(
            name="convert_unit",
            description="Birim dönüşümü yapar (metre→yard, kg→lb, ₺→$, vb.)",
            parameters={
                "value": {"type": "number", "description": "Değer", "required": True},
                "from_unit": {"type": "string", "description": "Kaynak birim", "required": True},
                "to_unit": {"type": "string", "description": "Hedef birim", "required": True},
            },
            handler=_tool_convert_unit,
            category="math",
        ))
        
        # 5. Tarih Hesaplama
        self.register(Tool(
            name="date_calc",
            description="Tarih hesaplaması yapar (iki tarih arası gün, iş günü, vb.)",
            parameters={
                "operation": {"type": "string", "description": "days_between, add_days, workdays", "required": True},
                "date1": {"type": "string", "description": "Tarih 1 (YYYY-MM-DD)", "required": True},
                "date2": {"type": "string", "description": "Tarih 2 veya gün sayısı", "required": False},
            },
            handler=_tool_date_calc,
            category="math",
        ))
        
        # 6. Maliyet Hesaplama
        self.register(Tool(
            name="cost_breakdown",
            description="Maliyet kırılımı hesaplar ve yorumlar.",
            parameters={
                "items": {"type": "list", "description": "Maliyet kalemleri: [{name, amount, previous_amount}]", "required": True},
                "total_revenue": {"type": "number", "description": "Toplam gelir (marj hesabı için)", "required": False},
            },
            handler=_tool_cost_breakdown,
            category="finance",
        ))
        
        # 7. OEE Hesaplama
        self.register(Tool(
            name="oee_calculate",
            description="OEE (Overall Equipment Effectiveness) hesaplar ve darboğazı belirler.",
            parameters={
                "availability": {"type": "number", "description": "Kullanılabilirlik %", "required": True},
                "performance": {"type": "number", "description": "Performans %", "required": True},
                "quality": {"type": "number", "description": "Kalite %", "required": True},
            },
            handler=_tool_oee_calculate,
            category="production",
        ))
        
        # 8. Fire Oranı Hesaplama
        self.register(Tool(
            name="waste_rate",
            description="Fire (atık) oranını hesaplar ve yorumlar.",
            parameters={
                "waste_amount": {"type": "number", "description": "Fire miktarı", "required": True},
                "total_production": {"type": "number", "description": "Toplam üretim miktarı", "required": True},
                "unit": {"type": "string", "description": "Birim (kg, metre, adet)", "required": False},
            },
            handler=_tool_waste_rate,
            category="production",
        ))
        
        # 8. Senaryo Simülasyonu
        self.register(Tool(
            name="scenario_simulate",
            description="Best/Expected/Worst Case senaryo simülasyonu yapar. KPI veya metrik için 3 senaryo hesaplar.",
            parameters={
                "current_value": {"type": "number", "description": "Mevcut değer", "required": True},
                "target_value": {"type": "number", "description": "Hedef değer", "required": False},
                "trend_pct": {"type": "number", "description": "Mevcut trend yüzdesi (örn: 5.2 veya -3.1)", "required": False},
                "risk_score": {"type": "number", "description": "Risk skoru 0-100", "required": False},
                "metric_name": {"type": "string", "description": "Metrik adı", "required": False},
                "unit": {"type": "string", "description": "Birim (%, ₺, kg vb.)", "required": False},
            },
            handler=_tool_scenario_simulate,
            category="analysis",
        ))
        
        # 9. Finansal Etki Projeksiyonu
        self.register(Tool(
            name="financial_impact",
            description="Gelir/maliyet değişiminin finansal etkisini hesaplar ve projeksiyonunu yapar.",
            parameters={
                "revenue": {"type": "number", "description": "Mevcut gelir", "required": False},
                "cost": {"type": "number", "description": "Mevcut maliyet", "required": False},
                "revenue_change_pct": {"type": "number", "description": "Tahmini gelir değişimi %", "required": False},
                "cost_change_pct": {"type": "number", "description": "Tahmini maliyet değişimi %", "required": False},
                "investment": {"type": "number", "description": "Gereken yatırım", "required": False},
                "payback_months": {"type": "number", "description": "Geri ödeme süresi (ay)", "required": False},
            },
            handler=_tool_financial_impact,
            category="finance",
        ))
        
        # 10. Monte Carlo Risk Simülasyonu
        self.register(Tool(
            name="monte_carlo",
            description="Monte Carlo simülasyonu ile risk olasılığı ve kayıp dağılımı hesaplar.",
            parameters={
                "base_value": {"type": "number", "description": "Temel değer (gelir, üretim vb.)", "required": True},
                "volatility": {"type": "number", "description": "Oynaklık yüzdesi (%)", "required": False},
                "target": {"type": "number", "description": "Hedef değer (başarısızlık eşiği)", "required": False},
            },
            handler=_tool_monte_carlo,
            category="risk",
        ))
        
        # 11. A/B Strateji Simülasyonu
        self.register(Tool(
            name="ab_strategy",
            description="İki strateji alternatifini simüle ederek karşılaştırır.",
            parameters={
                "strategy_a": {"type": "string", "description": "Birinci strateji açıklaması", "required": True},
                "strategy_b": {"type": "string", "description": "İkinci strateji açıklaması", "required": True},
            },
            handler=_tool_ab_strategy,
            category="strategy",
        ))
        
        # 12. Çapraz Departman Etki Analizi
        self.register(Tool(
            name="cross_dept_impact",
            description="Bir departmandaki değişikliğin diğer departmanlara etkisini analiz eder.",
            parameters={
                "department": {"type": "string", "description": "Kaynak departman", "required": True},
                "change": {"type": "string", "description": "Değişiklik açıklaması", "required": True},
            },
            handler=_tool_cross_dept,
            category="strategy",
        ))
        
        # 13. Graf Etki Haritası
        self.register(Tool(
            name="graph_impact",
            description="KPI, Departman, Risk ve Finansal Metrikler arası ilişki graf haritasını analiz eder.",
            parameters={
                "keyword": {"type": "string", "description": "Analiz edilecek anahtar kelime (OEE, fire, maliyet vb.)", "required": True},
            },
            handler=_tool_graph_impact,
            category="analytics",
        ))


# ══════════════════════════════════════════════════════════════
# 2. ARAÇ FONKSİYONLARI
# ══════════════════════════════════════════════════════════════

def _tool_calculate(expression: str) -> dict:
    """Güvenli matematiksel hesaplama."""
    # Güvenli operatörleri tanımla
    safe_dict = {
        'abs': abs, 'round': round, 'min': min, 'max': max, 'sum': sum,
        'pow': pow, 'sqrt': math.sqrt, 'log': math.log, 'log10': math.log10,
        'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
        'pi': math.pi, 'e': math.e,
        'ceil': math.ceil, 'floor': math.floor,
    }
    
    # Tehlikeli ifadeleri engelle
    dangerous = ['import', 'exec', 'eval', 'open', '__', 'os.', 'sys.']
    if any(d in expression.lower() for d in dangerous):
        return {"error": "Güvenlik nedeniyle bu ifade hesaplanamaz"}
    
    try:
        # Türkçe operatörleri çevir
        expr = expression.replace(',', '.').replace('×', '*').replace('÷', '/')
        result = eval(expr, {"__builtins__": {}}, safe_dict)
        return {"expression": expression, "result": round(float(result), 6)}
    except Exception as e:
        return {"error": f"Hesaplama hatası: {str(e)}"}


def _tool_kpi_interpret(kpi_name: str, value: float) -> dict:
    """KPI yorumlama."""
    from app.llm.prompts import interpret_kpi, KPI_INTERPRETATION_TEMPLATES
    
    template = KPI_INTERPRETATION_TEMPLATES.get(kpi_name)
    if not template:
        return {
            "kpi": kpi_name,
            "value": value,
            "interpretation": f"{kpi_name}: {value} (benchmark bilgisi mevcut değil)",
        }
    
    benchmarks = template["benchmarks"]
    thresholds = sorted(benchmarks.items(), key=lambda x: x[1])
    
    seviye = list(benchmarks.keys())[-1]  # varsayılan: son (en kötü)
    for level, threshold in thresholds:
        if value <= threshold:
            seviye = level
            break
    
    return {
        "kpi": kpi_name,
        "metric": template["metric"],
        "value": value,
        "level": seviye,
        "formula": template["formula"],
        "benchmarks": benchmarks,
        "interpretation": interpret_kpi(kpi_name, value),
    }


def _tool_risk_assess(risk_name: str, probability: int, impact: int, category: str = "operasyonel") -> dict:
    """Risk değerlendirmesi."""
    probability = max(1, min(5, int(probability)))
    impact = max(1, min(5, int(impact)))
    score = probability * impact
    
    if score >= 20:
        level = "Kritik"
        color = "🔴"
        action = "Hemen aksiyon al, yönetime bildir"
        timeframe = "24 saat"
    elif score >= 12:
        level = "Yüksek"
        color = "🟠"
        action = "1 hafta içinde önlem al"
        timeframe = "1 hafta"
    elif score >= 6:
        level = "Orta"
        color = "🟡"
        action = "Planlı iyileştirme programına dahil et"
        timeframe = "1 ay"
    else:
        level = "Düşük"
        color = "🟢"
        action = "İzle ve periyodik kontrol et"
        timeframe = "Çeyreklik"
    
    return {
        "risk_name": risk_name,
        "probability": probability,
        "impact": impact,
        "score": score,
        "level": level,
        "color": color,
        "category": category,
        "action": action,
        "timeframe": timeframe,
        "matrix_position": f"P{probability}xE{impact}",
    }


def _tool_convert_unit(value: float, from_unit: str, to_unit: str) -> dict:
    """Birim dönüşümü."""
    conversions = {
        ("metre", "yard"): 1.09361,
        ("yard", "metre"): 0.9144,
        ("kg", "lb"): 2.20462,
        ("lb", "kg"): 0.453592,
        ("metre", "feet"): 3.28084,
        ("feet", "metre"): 0.3048,
        ("cm", "inch"): 0.393701,
        ("inch", "cm"): 2.54,
        ("km", "mile"): 0.621371,
        ("ton", "kg"): 1000,
        ("kg", "ton"): 0.001,
        ("m2", "feet2"): 10.7639,
        ("litre", "galon"): 0.264172,
    }
    
    key = (from_unit.lower(), to_unit.lower())
    factor = conversions.get(key)
    
    if not factor:
        return {"error": f"Birim dönüşümü desteklenmiyor: {from_unit} → {to_unit}"}
    
    result = value * factor
    return {
        "input": f"{value} {from_unit}",
        "output": f"{round(result, 4)} {to_unit}",
        "factor": factor,
    }


def _tool_date_calc(operation: str, date1: str, date2: str = None) -> dict:
    """Tarih hesaplaması."""
    from datetime import datetime, timedelta
    
    try:
        d1 = datetime.strptime(date1, "%Y-%m-%d")
    except ValueError:
        return {"error": f"Geçersiz tarih formatı: {date1}. YYYY-MM-DD kullanın."}
    
    if operation == "days_between":
        try:
            d2 = datetime.strptime(date2, "%Y-%m-%d")
            delta = abs((d2 - d1).days)
            return {"date1": date1, "date2": date2, "days": delta, "weeks": round(delta / 7, 1)}
        except (ValueError, TypeError):
            return {"error": "İkinci tarih geçersiz"}
    
    elif operation == "add_days":
        try:
            days = int(date2)
            result = d1 + timedelta(days=days)
            return {"start_date": date1, "days_added": days, "result_date": result.strftime("%Y-%m-%d")}
        except (ValueError, TypeError):
            return {"error": "Gün sayısı geçersiz"}
    
    elif operation == "workdays":
        try:
            d2 = datetime.strptime(date2, "%Y-%m-%d")
            workdays = 0
            current = min(d1, d2)
            end = max(d1, d2)
            while current <= end:
                if current.weekday() < 5:
                    workdays += 1
                current += timedelta(days=1)
            return {"date1": date1, "date2": date2, "workdays": workdays, "calendar_days": abs((d2 - d1).days)}
        except (ValueError, TypeError):
            return {"error": "Tarih geçersiz"}
    
    return {"error": f"Bilinmeyen operasyon: {operation}"}


def _tool_cost_breakdown(items: list, total_revenue: float = None) -> dict:
    """Maliyet kırılımı hesaplama."""
    if not items:
        return {"error": "Maliyet kalemi bulunamadı"}
    
    total_cost = 0
    breakdown = []
    
    for item in items:
        name = item.get("name", "Bilinmeyen")
        amount = float(item.get("amount", 0))
        prev = float(item.get("previous_amount", 0))
        total_cost += amount
        
        change_pct = ((amount - prev) / prev * 100) if prev > 0 else 0
        
        breakdown.append({
            "name": name,
            "amount": amount,
            "previous_amount": prev,
            "change_pct": round(change_pct, 1),
            "change_direction": "↑" if change_pct > 0 else "↓" if change_pct < 0 else "→",
        })
    
    # Payları hesapla
    for item in breakdown:
        item["share_pct"] = round(item["amount"] / total_cost * 100, 1) if total_cost > 0 else 0
    
    # Sırala (büyükten küçüğe)
    breakdown.sort(key=lambda x: x["amount"], reverse=True)
    
    result = {
        "total_cost": round(total_cost, 2),
        "items": breakdown,
        "largest_item": breakdown[0]["name"] if breakdown else None,
        "largest_share": breakdown[0]["share_pct"] if breakdown else 0,
    }
    
    if total_revenue:
        result["gross_margin"] = round((total_revenue - total_cost) / total_revenue * 100, 1)
        result["cost_to_revenue"] = round(total_cost / total_revenue * 100, 1)
    
    return result


def _tool_oee_calculate(availability: float, performance: float, quality: float) -> dict:
    """OEE hesaplama ve yorumlama."""
    oee = (availability / 100) * (performance / 100) * (quality / 100) * 100
    
    # Darboğaz
    factors = {"Kullanılabilirlik": availability, "Performans": performance, "Kalite": quality}
    bottleneck = min(factors, key=factors.get)
    
    # Seviye
    if oee >= 85:
        level = "Dünya Sınıfı"
        color = "🟢"
    elif oee >= 70:
        level = "İyi"
        color = "🟡"
    elif oee >= 55:
        level = "Orta"
        color = "🟠"
    else:
        level = "Düşük"
        color = "🔴"
    
    # Potansiyel kazanç (her %1 OEE iyileşmesi ≈ %2-3 üretim artışı tahmini)
    improvement_potential = 85 - oee if oee < 85 else 0
    
    return {
        "oee": round(oee, 1),
        "availability": availability,
        "performance": performance,
        "quality": quality,
        "level": level,
        "color": color,
        "bottleneck": bottleneck,
        "bottleneck_value": factors[bottleneck],
        "improvement_potential_pct": round(improvement_potential, 1),
        "interpretation": f"OEE %{round(oee,1)} → {level} {color}. Darboğaz: {bottleneck} (%{factors[bottleneck]}). İyileştirme potansiyeli: %{round(improvement_potential,1)}",
    }


def _tool_waste_rate(waste_amount: float, total_production: float, unit: str = "kg") -> dict:
    """Fire oranı hesaplama."""
    if total_production <= 0:
        return {"error": "Toplam üretim 0'dan büyük olmalı"}
    
    rate = (waste_amount / total_production) * 100
    
    if rate < 2:
        level = "İyi"
        color = "🟢"
        action = "Mevcut kalite süreçlerini sürdür"
    elif rate < 5:
        level = "Kabul Edilebilir"
        color = "🟡"
        action = "Pareto analizi ile en büyük fire kaynağını belirle"
    elif rate < 8:
        level = "Yüksek"
        color = "🟠"
        action = "Kalite iyileştirme projesi başlat, kök neden analizi uygula"
    else:
        level = "Kritik"
        color = "🔴"
        action = "ACİL: Üretimi durdur ve tam kalite denetimi yap"
    
    # Maliyet etkisi tahmini (fire maliyeti)
    estimated_cost_per_unit = 50  # varsayılan birim maliyet
    
    return {
        "waste_amount": waste_amount,
        "total_production": total_production,
        "waste_rate": round(rate, 2),
        "unit": unit,
        "level": level,
        "color": color,
        "action": action,
        "good_production": total_production - waste_amount,
        "interpretation": f"Fire oranı %{round(rate, 2)} ({waste_amount} {unit} / {total_production} {unit}) → {level} {color}. {action}",
        "benchmark": {"iyi": "<2%", "normal": "2-5%", "yüksek": "5-8%", "kritik": ">8%"},
    }


# ══════════════════════════════════════════════════════════════
# 3. TOOL CALL DETECTION — LLM çıktısından araç çağrısı algıla
# ══════════════════════════════════════════════════════════════

def detect_tool_calls(text: str) -> list[dict]:
    """LLM çıktısından tool call'ları algıla."""
    calls = []
    
    # JSON formatında tool call: {"tool": "xxx", "params": {...}}
    json_pattern = re.findall(
        r'\{\s*"tool"\s*:\s*"(\w+)"\s*,\s*"params"\s*:\s*(\{[^}]+\})\s*\}',
        text
    )
    for tool_name, params_str in json_pattern:
        try:
            params = json.loads(params_str)
            calls.append({"tool": tool_name, "params": params})
        except json.JSONDecodeError:
            continue
    
    # Doğal dil tool detection (fallback)
    if not calls:
        calls = _detect_implicit_tool_calls(text)
    
    return calls


def _detect_implicit_tool_calls(text: str) -> list[dict]:
    """Doğal dilden implicit araç çağrısı algıla."""
    calls = []
    q = text.lower()
    
    # Hesaplama talebi
    calc_match = re.search(r'(\d+[\s]*[+\-*/×÷%]\s*\d+[\s]*[+\-*/×÷%=]*\s*\d*)', text)
    if calc_match:
        calls.append({"tool": "calculate", "params": {"expression": calc_match.group(1)}})
    
    # OEE talebi
    if re.search(r'oee|genel\s*ekipman\s*verimlilik', q):
        nums = re.findall(r'%?([\d.]+)\s*%?', text)
        if len(nums) >= 3:
            calls.append({"tool": "oee_calculate", "params": {
                "availability": float(nums[0]),
                "performance": float(nums[1]),
                "quality": float(nums[2]),
            }})
    
    # Fire oranı talebi
    if re.search(r'fire\s*(oranı|hesapla|miktar)', q):
        nums = re.findall(r'([\d.,]+)', text)
        if len(nums) >= 2:
            calls.append({"tool": "waste_rate", "params": {
                "waste_amount": float(nums[0].replace(',', '.')),
                "total_production": float(nums[1].replace(',', '.')),
            }})
    
    return calls


def _tool_scenario_simulate(**params) -> dict:
    """Senaryo simülasyonu tool fonksiyonu."""
    try:
        from app.core.scenario_engine import simulate_scenarios, format_scenario_table
        result = simulate_scenarios(
            current_value=float(params.get("current_value", 0)),
            target_value=float(params["target_value"]) if params.get("target_value") else None,
            trend_pct=float(params.get("trend_pct", 0)),
            risk_score=float(params.get("risk_score", 50)),
            metric_name=str(params.get("metric_name", "Metrik")),
            unit=str(params.get("unit", "")),
        )
        return {"formatted": format_scenario_table(result), **result}
    except Exception as e:
        return {"error": str(e)}


def _tool_financial_impact(**params) -> dict:
    """Finansal etki projeksiyonu tool fonksiyonu."""
    try:
        from app.core.scenario_engine import project_financial_impact, format_financial_impact
        result = project_financial_impact(
            revenue_current=float(params.get("revenue", 0)),
            cost_current=float(params.get("cost", 0)),
            revenue_change_pct=float(params.get("revenue_change_pct", 0)),
            cost_change_pct=float(params.get("cost_change_pct", 0)),
            investment_required=float(params.get("investment", 0)),
            payback_months=int(params.get("payback_months", 0)),
        )
        return {"formatted": format_financial_impact(result), **result}
    except Exception as e:
        return {"error": str(e)}


def _tool_monte_carlo(**params) -> dict:
    """Monte Carlo risk simülasyonu tool fonksiyonu."""
    try:
        from app.core.monte_carlo import monte_carlo_simulate, format_monte_carlo_table
        result = monte_carlo_simulate(
            base_value=float(params.get("base_value", 1000000)),
            volatility_pct=float(params.get("volatility", 15)),
            target_value=float(params.get("target", 0)) or None,
        )
        return {"formatted": format_monte_carlo_table(result), **result}
    except Exception as e:
        return {"error": str(e)}


def _tool_ab_strategy(**params) -> dict:
    """A/B strateji simülasyonu tool fonksiyonu."""
    try:
        from app.core.experiment_layer import simulate_ab_strategy, format_ab_result
        result = simulate_ab_strategy(
            strategy_a_desc=str(params.get("strategy_a", "")),
            strategy_b_desc=str(params.get("strategy_b", "")),
        )
        return {"formatted": format_ab_result(result), "recommended": result.recommended}
    except Exception as e:
        return {"error": str(e)}


def _tool_cross_dept(**params) -> dict:
    """Çapraz departman etki analizi tool fonksiyonu."""
    try:
        from app.core.experiment_layer import analyze_cross_dept_impact, format_cross_dept_impact
        result = analyze_cross_dept_impact(
            source_department=str(params.get("department", "Üretim")),
            change_description=str(params.get("change", "")),
        )
        return {"formatted": format_cross_dept_impact(result), "positive": result.total_positive, "negative": result.total_negative}
    except Exception as e:
        return {"error": str(e)}


def _tool_graph_impact(**params) -> dict:
    """Graf etki haritası tool fonksiyonu."""
    try:
        from app.core.graph_impact import impact_graph, format_graph_impact
        result = impact_graph.analyze_impact(
            focus_keyword=str(params.get("keyword", "")),
        )
        return {"formatted": format_graph_impact(result), "affected": result.total_nodes_affected}
    except Exception as e:
        return {"error": str(e)}


# Singleton
tool_registry = ToolRegistry()
