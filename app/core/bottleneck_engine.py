"""Darboğaz Tespit Motoru — Bottleneck Analysis Engine v1.0

CEO sorusu: "Operasyon nerede tıkanıyor?"

Yetenekler:
- Süreç darboğaz tespiti (en yavaş, en pahalı, en verimsiz)
- Kaynak kullanım haritalaması
- Kuyruk analizi (bekleme süresi / işlem süresi oranı)
- Kapasite kullanım oranı
- Darboğaz zincirleme etki analizi
- Otomatik iyileştirme önerileri
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import structlog

logger = structlog.get_logger()


# ══════════════════════════════════════════════════════════════
# VERİ MODELLERİ
# ══════════════════════════════════════════════════════════════

@dataclass
class ProcessStep:
    """Bir süreç adımı."""
    name: str
    cycle_time_min: float        # Çevrim süresi (dakika)
    wait_time_min: float = 0.0   # Bekleme süresi (dakika)
    capacity_used_pct: float = 0.0  # Kapasite kullanımı (%)
    error_rate_pct: float = 0.0  # Hata oranı (%)
    cost_per_unit: float = 0.0   # Birim maliyet
    workers: int = 1             # Çalışan sayısı
    machines: int = 1            # Makine sayısı
    description: str = ""


@dataclass
class BottleneckResult:
    """Darboğaz analiz sonucu."""
    process_name: str
    bottleneck_step: str
    bottleneck_type: str          # time, cost, quality, capacity
    severity: str                 # critical, high, medium, low
    score: float                  # 0-100 (yüksek = ciddi darboğaz)
    impact_description: str
    recommendations: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    chain_effects: list = field(default_factory=list)


# ══════════════════════════════════════════════════════════════
# TEKSTİL SEKTÖRÜ SÜREÇ ŞABLONLARI
# ══════════════════════════════════════════════════════════════

TEXTILE_PROCESS_TEMPLATES = {
    "iplik_uretim": {
        "name": "İplik Üretim Hattı",
        "steps": ["Hammadde Hazırlama", "Tarak", "Cer", "Fitil", "Ring", "Bobin", "Kalite Kontrol"],
        "benchmark_cycle_times": [15, 20, 12, 18, 25, 10, 8],  # dakika
        "benchmark_capacity": [85, 80, 90, 75, 70, 88, 92],    # %
    },
    "dokuma": {
        "name": "Dokuma Hattı",
        "steps": ["Çözgü Hazırlama", "Haşıllama", "Taharlama", "Dokuma", "Ham Kontrol", "Paketleme"],
        "benchmark_cycle_times": [30, 45, 20, 60, 15, 10],
        "benchmark_capacity": [80, 75, 85, 70, 90, 92],
    },
    "boyama": {
        "name": "Boyahane Hattı",
        "steps": ["Reçete Hazırlama", "Ön Terbiye", "Boyama", "Yıkama", "Kurutma", "Kalite Kontrol"],
        "benchmark_cycle_times": [10, 40, 90, 30, 45, 15],
        "benchmark_capacity": [95, 78, 65, 80, 72, 90],
    },
    "konfeksiyon": {
        "name": "Konfeksiyon Hattı",
        "steps": ["Kesim", "Dikim Hazırlık", "Dikim", "Ütü / Press", "Kalite Kontrol", "Paketleme"],
        "benchmark_cycle_times": [20, 10, 45, 15, 12, 8],
        "benchmark_capacity": [85, 90, 68, 80, 88, 93],
    },
    "genel_uretim": {
        "name": "Genel Üretim Hattı",
        "steps": ["Hammadde", "İşleme", "Montaj", "Test", "Paketleme"],
        "benchmark_cycle_times": [15, 30, 45, 20, 10],
        "benchmark_capacity": [85, 75, 70, 85, 90],
    },
}


# ══════════════════════════════════════════════════════════════
# DARBOĞAZ ANALİZ FONKSİYONLARI
# ══════════════════════════════════════════════════════════════

def analyze_bottleneck(steps: list[ProcessStep], process_name: str = "Üretim Hattı") -> BottleneckResult:
    """
    Süreç adımlarını analiz ederek darboğazı tespit eder.
    
    Darboğaz Tespiti Kriterleri:
    1. En uzun çevrim süresi (TIME bottleneck)
    2. En yüksek kapasite kullanımı (CAPACITY bottleneck)
    3. En yüksek hata oranı (QUALITY bottleneck)
    4. En yüksek birim maliyet (COST bottleneck)
    """
    if not steps:
        return BottleneckResult(
            process_name=process_name,
            bottleneck_step="Bilinmiyor",
            bottleneck_type="unknown",
            severity="low",
            score=0,
            impact_description="Süreç adımı bulunamadı",
        )
    
    # ── Metrikleri hesapla ──
    total_cycle = sum(s.cycle_time_min for s in steps)
    total_wait = sum(s.wait_time_min for s in steps)
    total_throughput_time = total_cycle + total_wait
    avg_cycle = total_cycle / len(steps)
    avg_capacity = sum(s.capacity_used_pct for s in steps) / len(steps) if steps else 0
    
    # ── Darboğaz tespit puanları ──
    step_scores = []
    for s in steps:
        # Zaman puanı: çevrim süresi ortalamanın ne kadar üstünde
        time_score = (s.cycle_time_min / avg_cycle - 1) * 40 if avg_cycle > 0 else 0
        time_score = max(0, min(100, time_score + 50))
        
        # Bekleme puanı: bekleme / çevrim oranı
        wait_ratio_score = (s.wait_time_min / s.cycle_time_min * 100) if s.cycle_time_min > 0 else 0
        wait_ratio_score = min(100, wait_ratio_score)
        
        # Kapasite puanı (>85% = darboğaz riski, >95% = kritik)
        cap_score = 0
        if s.capacity_used_pct >= 95:
            cap_score = 100
        elif s.capacity_used_pct >= 85:
            cap_score = 70 + (s.capacity_used_pct - 85) * 3
        elif s.capacity_used_pct >= 70:
            cap_score = 30 + (s.capacity_used_pct - 70) * 2.67
        
        # Hata puanı
        error_score = min(100, s.error_rate_pct * 10)
        
        # Maliyet puanı (normalize edilemez — göreceli)
        cost_score = 0  # Sonra hesaplanacak
        
        # Bileşik puan (ağırlıklı)
        composite = (
            time_score * 0.30 +
            wait_ratio_score * 0.15 +
            cap_score * 0.30 +
            error_score * 0.15 +
            cost_score * 0.10
        )
        
        step_scores.append({
            "step": s,
            "time_score": round(time_score, 1),
            "wait_ratio_score": round(wait_ratio_score, 1),
            "capacity_score": round(cap_score, 1),
            "error_score": round(error_score, 1),
            "composite": round(composite, 1),
        })
    
    # Maliyet normalize (en pahalıya 100, en ucuza 0)
    costs = [s.cost_per_unit for s in steps]
    max_cost = max(costs) if costs else 1
    min_cost = min(costs) if costs else 0
    cost_range = max_cost - min_cost if max_cost != min_cost else 1
    for ss in step_scores:
        cost_norm = ((ss["step"].cost_per_unit - min_cost) / cost_range) * 100
        ss["cost_score"] = round(cost_norm, 1)
        # Composit'i güncelle
        ss["composite"] = round(
            ss["time_score"] * 0.30 +
            ss["wait_ratio_score"] * 0.15 +
            ss["capacity_score"] * 0.30 +
            ss["error_score"] * 0.15 +
            ss["cost_score"] * 0.10,
            1
        )
    
    # ── En ciddi darboğazı bul ──
    step_scores.sort(key=lambda x: x["composite"], reverse=True)
    worst = step_scores[0]
    bottleneck_step = worst["step"]
    
    # Darboğaz tipi: en yüksek alt-puan
    sub_scores = {
        "time": worst["time_score"],
        "capacity": worst["capacity_score"],
        "quality": worst["error_score"],
        "cost": worst["cost_score"],
        "wait": worst["wait_ratio_score"],
    }
    bottleneck_type = max(sub_scores, key=sub_scores.get)
    
    # Severity
    score = worst["composite"]
    if score >= 75:
        severity = "critical"
    elif score >= 55:
        severity = "high"
    elif score >= 35:
        severity = "medium"
    else:
        severity = "low"
    
    # Etki tanımı
    type_labels = {
        "time": "Zaman Darboğazı — Bu adım sürecin en yavaş noktası",
        "capacity": "Kapasite Darboğazı — Bu adım kapasite sınırına yakın çalışıyor",
        "quality": "Kalite Darboğazı — Bu adımda hata oranı yüksek",
        "cost": "Maliyet Darboğazı — Bu adım en yüksek birim maliyete sahip",
        "wait": "Bekleme Darboğazı — Bu adımda bekleme süresi orantısız yüksek",
    }
    
    # Zincirleme etki
    chain_effects = _calculate_chain_effects(steps, bottleneck_step.name, bottleneck_type)
    
    # Öneriler
    recommendations = _generate_recommendations(bottleneck_step, bottleneck_type, worst)
    
    # Detaylı metrikler
    metrics = {
        "total_cycle_time_min": round(total_cycle, 1),
        "total_wait_time_min": round(total_wait, 1),
        "total_throughput_time_min": round(total_throughput_time, 1),
        "flow_efficiency_pct": round((total_cycle / total_throughput_time * 100) if total_throughput_time > 0 else 0, 1),
        "avg_capacity_utilization_pct": round(avg_capacity, 1),
        "bottleneck_cycle_time_min": bottleneck_step.cycle_time_min,
        "bottleneck_capacity_pct": bottleneck_step.capacity_used_pct,
        "bottleneck_error_rate_pct": bottleneck_step.error_rate_pct,
        "bottleneck_wait_time_min": bottleneck_step.wait_time_min,
        "process_step_count": len(steps),
        "step_rankings": [
            {
                "rank": i + 1,
                "step": ss["step"].name,
                "score": ss["composite"],
                "dominant_issue": max(
                    {"time": ss["time_score"], "capacity": ss["capacity_score"], 
                     "quality": ss["error_score"], "cost": ss["cost_score"]},
                    key=lambda k: {"time": ss["time_score"], "capacity": ss["capacity_score"],
                                   "quality": ss["error_score"], "cost": ss["cost_score"]}[k]
                ),
            }
            for i, ss in enumerate(step_scores[:5])
        ],
    }
    
    return BottleneckResult(
        process_name=process_name,
        bottleneck_step=bottleneck_step.name,
        bottleneck_type=bottleneck_type,
        severity=severity,
        score=score,
        impact_description=type_labels.get(bottleneck_type, "Darboğaz tespit edildi"),
        recommendations=recommendations,
        metrics=metrics,
        chain_effects=chain_effects,
    )


def _calculate_chain_effects(steps: list[ProcessStep], bottleneck_name: str, bottleneck_type: str) -> list[dict]:
    """Darboğazın sonraki adımlara zincirleme etkisini hesapla."""
    effects = []
    found = False
    cumulative_delay = 0
    
    for s in steps:
        if s.name == bottleneck_name:
            found = True
            continue
        if found:
            # Darboğaz sonrası her adım gecikmeden etkilenir
            if bottleneck_type == "time":
                delay = s.wait_time_min * 0.3  # Bekleme süreleri artar
                cumulative_delay += delay
            elif bottleneck_type == "capacity":
                delay = s.cycle_time_min * 0.15  # Kapasite kısıtı yayılır
                cumulative_delay += delay
            elif bottleneck_type == "quality":
                delay = s.cycle_time_min * (s.error_rate_pct / 100) * 0.5
                cumulative_delay += delay
            else:
                delay = s.wait_time_min * 0.1
                cumulative_delay += delay
            
            effects.append({
                "step": s.name,
                "estimated_delay_min": round(cumulative_delay, 1),
                "impact": "Yüksek" if cumulative_delay > 30 else "Orta" if cumulative_delay > 10 else "Düşük",
            })
    
    return effects


def _generate_recommendations(step: ProcessStep, bottleneck_type: str, scores: dict) -> list[str]:
    """Darboğaz tipine göre iyileştirme önerileri üret."""
    recs = []
    
    if bottleneck_type == "time":
        recs.append(f"⏱️ {step.name} adımında çevrim süresini azaltmak için iş etüdü yapılmalı")
        if step.machines > 0:
            recs.append(f"🔧 Paralel makine eklenmesi ({step.machines} → {step.machines + 1}) süreyi ~%{int(100 / (step.machines + 1))} azaltabilir")
        recs.append("📋 SMED (Tekli Dakika Kalıp Değişimi) metodolojisi uygulanmalı")
        
    elif bottleneck_type == "capacity":
        recs.append(f"📈 {step.name} adımı %{step.capacity_used_pct:.0f} kapasite ile çalışıyor — ek kapasite yatırımı değerlendirilmeli")
        recs.append("🔄 Vardiya planlaması optimize edilmeli (darboğaz adımına ek vardiya)")
        recs.append("⚡ Bakım planlarını darboğaz adımına öncelikli hale getirin (TPM)")
        
    elif bottleneck_type == "quality":
        recs.append(f"🔍 {step.name} adımında hata oranı %{step.error_rate_pct:.1f} — kök neden analizi (5 Neden) yapılmalı")
        recs.append("📊 İstatistiksel Süreç Kontrolü (SPC) uygulanmalı")
        recs.append("🛡️ Poka-Yoke (hata önleme) mekanizmaları kurulmalı")
        
    elif bottleneck_type == "cost":
        recs.append(f"💰 {step.name} adımı en yüksek birim maliyete sahip — maliyet kırılımı yapılmalı")
        recs.append("♻️ Hammadde kullanım verimliliği artırılmalı (fire azaltma)")
        recs.append("📉 Enerji tüketimi optimizasyonu değerlendirilmeli")
        
    elif bottleneck_type == "wait":
        recs.append(f"⏳ {step.name} adımında bekleme süresi ({step.wait_time_min:.0f} dk) çevrim süresine göre yüksek")
        recs.append("🔗 Önceki adımla senkronizasyon geliştirilmeli (FIFO hatları)")
        recs.append("📋 Kanban sistemi ile WIP (yarı mamul) kontrolü sağlanmalı")
    
    # Genel öneriler
    if scores.get("composite", 0) >= 70:
        recs.append("🚨 KRİTİK: Bu darboğaz toplam verimliliği ciddi şekilde etkiliyor — acil aksiyon gerekli")
    
    return recs


def analyze_from_data(data: dict, process_type: str = "genel_uretim") -> BottleneckResult:
    """
    Sözlük formatında gelen veriyi analiz eder.
    
    data formatı:
    {
        "steps": [
            {"name": "Kesim", "cycle_time": 20, "wait_time": 5, "capacity": 85, "error_rate": 2, "cost": 15},
            ...
        ],
        "process_name": "Dokuma Hattı"
    }
    """
    steps = []
    raw_steps = data.get("steps", [])
    
    if not raw_steps and process_type in TEXTILE_PROCESS_TEMPLATES:
        # Şablon verisi kullan
        template = TEXTILE_PROCESS_TEMPLATES[process_type]
        for i, step_name in enumerate(template["steps"]):
            steps.append(ProcessStep(
                name=step_name,
                cycle_time_min=template["benchmark_cycle_times"][i],
                capacity_used_pct=template["benchmark_capacity"][i],
            ))
    else:
        for raw in raw_steps:
            steps.append(ProcessStep(
                name=raw.get("name", f"Adım {len(steps)+1}"),
                cycle_time_min=float(raw.get("cycle_time", raw.get("cycle_time_min", 0))),
                wait_time_min=float(raw.get("wait_time", raw.get("wait_time_min", 0))),
                capacity_used_pct=float(raw.get("capacity", raw.get("capacity_used_pct", 0))),
                error_rate_pct=float(raw.get("error_rate", raw.get("error_rate_pct", 0))),
                cost_per_unit=float(raw.get("cost", raw.get("cost_per_unit", 0))),
                workers=int(raw.get("workers", 1)),
                machines=int(raw.get("machines", 1)),
            ))
    
    process_name = data.get("process_name", TEXTILE_PROCESS_TEMPLATES.get(process_type, {}).get("name", "Üretim Hattı"))
    return analyze_bottleneck(steps, process_name)


def get_template_analysis(process_type: str = "dokuma") -> BottleneckResult:
    """Hazır tekstil şablonuyla demo analiz çalıştır."""
    return analyze_from_data({}, process_type)


def list_templates() -> list[dict]:
    """Mevcut süreç şablonlarını listele."""
    return [
        {
            "id": key,
            "name": tmpl["name"],
            "step_count": len(tmpl["steps"]),
            "steps": tmpl["steps"],
        }
        for key, tmpl in TEXTILE_PROCESS_TEMPLATES.items()
    ]


def format_bottleneck_report(result: BottleneckResult) -> str:
    """Darboğaz sonucunu Markdown rapor formatına çevir."""
    severity_icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
    icon = severity_icons.get(result.severity, "⚪")
    
    lines = [
        f"\n\n---\n## 🔧 Darboğaz Analizi — {result.process_name}",
        f"\n**Darboğaz Noktası:** {icon} **{result.bottleneck_step}**",
        f"**Tip:** {result.impact_description}",
        f"**Ciddiyet Skoru:** {result.score:.0f}/100 ({result.severity.upper()})",
    ]
    
    m = result.metrics
    if m:
        lines.append(f"\n### 📊 Süreç Metrikleri")
        lines.append(f"| Metrik | Değer |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Toplam Çevrim Süresi | {m.get('total_cycle_time_min', 0)} dk |")
        lines.append(f"| Toplam Bekleme Süresi | {m.get('total_wait_time_min', 0)} dk |")
        lines.append(f"| Akış Verimliliği | %{m.get('flow_efficiency_pct', 0)} |")
        lines.append(f"| Ort. Kapasite Kullanımı | %{m.get('avg_capacity_utilization_pct', 0)} |")
    
    if result.chain_effects:
        lines.append(f"\n### 🔗 Zincirleme Etki")
        for eff in result.chain_effects:
            lines.append(f"- **{eff['step']}**: ~{eff['estimated_delay_min']} dk gecikme ({eff['impact']})")
    
    if result.recommendations:
        lines.append(f"\n### 💡 İyileştirme Önerileri")
        for rec in result.recommendations:
            lines.append(f"- {rec}")
    
    return "\n".join(lines)


# ── Tool Registry Entegrasyonu ──
def bottleneck_tool(params: dict) -> dict:
    """Tool calling wrapper."""
    process_type = params.get("process_type", "genel_uretim")
    data = params.get("data", {})
    
    if data:
        result = analyze_from_data(data, process_type)
    else:
        result = get_template_analysis(process_type)
    
    return {
        "bottleneck": result.bottleneck_step,
        "type": result.bottleneck_type,
        "severity": result.severity,
        "score": result.score,
        "report": format_bottleneck_report(result),
    }
