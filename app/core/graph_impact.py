"""
Graph Impact Mapping Engine — v3.2.0
======================================
KPI, Departman, Risk ve Finansal Metrikler arası ilişki graf haritası.
Neo4j gerektirmez — in-memory adjacency list ile çalışır.

Enterprise Pipeline 7. adım: GraphImpactMapping
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# ──────────────────── Graf Düğüm Tipleri ────────────────────

NODE_TYPES = {
    "KPI": "📊",
    "Department": "🏢",
    "Risk": "⚠️",
    "FinancialMetric": "💰",
    "Process": "⚙️",
    "Strategy": "🎯",
}

# ──────────────────── Varsayılan Tekstil Bilgi Grafı ────────────────────

DEFAULT_NODES: list[dict[str, str]] = [
    # Departmanlar
    {"id": "dept_uretim", "label": "Üretim", "type": "Department"},
    {"id": "dept_satis", "label": "Satış", "type": "Department"},
    {"id": "dept_finans", "label": "Finans", "type": "Department"},
    {"id": "dept_ik", "label": "İK", "type": "Department"},
    {"id": "dept_lojistik", "label": "Lojistik", "type": "Department"},
    {"id": "dept_kalite", "label": "Kalite", "type": "Department"},
    # KPI'lar
    {"id": "kpi_oee", "label": "OEE", "type": "KPI"},
    {"id": "kpi_fire", "label": "Fire Oranı", "type": "KPI"},
    {"id": "kpi_teslimat", "label": "Zamanında Teslimat", "type": "KPI"},
    {"id": "kpi_gelir", "label": "Gelir", "type": "KPI"},
    {"id": "kpi_maliyet", "label": "Üretim Maliyeti", "type": "KPI"},
    {"id": "kpi_devir", "label": "Personel Devir Oranı", "type": "KPI"},
    {"id": "kpi_stok", "label": "Stok Devir Hızı", "type": "KPI"},
    {"id": "kpi_ret", "label": "Ret Oranı", "type": "KPI"},
    {"id": "kpi_musteri_kaybi", "label": "Müşteri Kaybı", "type": "KPI"},
    # Risk'ler
    {"id": "risk_makine", "label": "Makine Arıza Riski", "type": "Risk"},
    {"id": "risk_hammadde", "label": "Hammadde Tedarik Riski", "type": "Risk"},
    {"id": "risk_kalite", "label": "Kalite Sapma Riski", "type": "Risk"},
    {"id": "risk_personel", "label": "Nitelikli Personel Kaybı", "type": "Risk"},
    {"id": "risk_doviz", "label": "Döviz Kuru Riski", "type": "Risk"},
    # Finansal Metrikler
    {"id": "fin_brut_kar", "label": "Brüt Kâr Marjı", "type": "FinancialMetric"},
    {"id": "fin_nakit", "label": "Nakit Akış", "type": "FinancialMetric"},
    {"id": "fin_borc", "label": "Borç/Özkaynak", "type": "FinancialMetric"},
    # Süreçler
    {"id": "proc_dokuma", "label": "Dokuma Süreci", "type": "Process"},
    {"id": "proc_boya", "label": "Boyama Süreci", "type": "Process"},
    {"id": "proc_kalite_kontrol", "label": "Kalite Kontrol", "type": "Process"},
]

# İlişkiler: (kaynak_id, hedef_id, ilişki_tipi, etki_ağırlığı)
DEFAULT_EDGES: list[tuple[str, str, str, float]] = [
    # Departman → KPI sahiplikleri
    ("dept_uretim", "kpi_oee", "sahip", 1.0),
    ("dept_uretim", "kpi_fire", "sahip", 1.0),
    ("dept_uretim", "kpi_maliyet", "etkiler", 0.9),
    ("dept_satis", "kpi_gelir", "sahip", 1.0),
    ("dept_satis", "kpi_musteri_kaybi", "sahip", 1.0),
    ("dept_finans", "fin_brut_kar", "sahip", 1.0),
    ("dept_finans", "fin_nakit", "sahip", 1.0),
    ("dept_finans", "fin_borc", "sahip", 1.0),
    ("dept_ik", "kpi_devir", "sahip", 1.0),
    ("dept_lojistik", "kpi_stok", "sahip", 1.0),
    ("dept_lojistik", "kpi_teslimat", "sahip", 1.0),
    ("dept_kalite", "kpi_ret", "sahip", 1.0),
    # KPI ↔ KPI etkileşimleri
    ("kpi_oee", "kpi_maliyet", "azaltır", 0.8),
    ("kpi_oee", "kpi_teslimat", "artırır", 0.7),
    ("kpi_fire", "kpi_maliyet", "artırır", 0.9),
    ("kpi_fire", "fin_brut_kar", "azaltır", 0.8),
    ("kpi_ret", "kpi_musteri_kaybi", "artırır", 0.7),
    ("kpi_ret", "kpi_fire", "ilişkili", 0.6),
    ("kpi_devir", "kpi_oee", "azaltır", 0.5),
    ("kpi_stok", "fin_nakit", "etkiler", 0.6),
    ("kpi_gelir", "fin_brut_kar", "artırır", 1.0),
    # Risk → KPI etkileri
    ("risk_makine", "kpi_oee", "düşürür", 0.9),
    ("risk_makine", "kpi_teslimat", "düşürür", 0.7),
    ("risk_hammadde", "kpi_maliyet", "artırır", 0.8),
    ("risk_hammadde", "kpi_teslimat", "düşürür", 0.6),
    ("risk_kalite", "kpi_ret", "artırır", 0.9),
    ("risk_kalite", "kpi_fire", "artırır", 0.7),
    ("risk_personel", "kpi_devir", "artırır", 0.9),
    ("risk_personel", "kpi_oee", "düşürür", 0.5),
    ("risk_doviz", "kpi_maliyet", "artırır", 0.7),
    ("risk_doviz", "fin_brut_kar", "azaltır", 0.6),
    # Süreç → KPI / Risk bağlantıları
    ("proc_dokuma", "kpi_oee", "belirler", 0.9),
    ("proc_dokuma", "risk_makine", "kaynağı", 0.8),
    ("proc_boya", "kpi_fire", "belirler", 0.9),
    ("proc_boya", "risk_kalite", "kaynağı", 0.7),
    ("proc_kalite_kontrol", "kpi_ret", "belirler", 1.0),
    ("proc_kalite_kontrol", "risk_kalite", "azaltır", 0.8),
]


# ──────────────────── Veri Yapıları ────────────────────

@dataclass
class GraphNode:
    id: str
    label: str
    node_type: str
    icon: str = ""
    impact_score: float = 0.0  # analiz sırasında hesaplanır


@dataclass
class GraphEdge:
    source: str
    target: str
    relation: str
    weight: float = 1.0


@dataclass
class ImpactPath:
    """Bir düğümden diğerine etki yolu."""
    path: list[str] = field(default_factory=list)
    total_weight: float = 0.0
    relations: list[str] = field(default_factory=list)


@dataclass
class GraphImpactResult:
    """Graf etki analizi sonucu."""
    focus_node: str = ""
    focus_type: str = ""
    impacted_nodes: list[dict[str, Any]] = field(default_factory=list)
    impact_paths: list[ImpactPath] = field(default_factory=list)
    total_nodes_affected: int = 0
    max_depth: int = 0
    critical_chain: str = ""
    summary: str = ""


# ──────────────────── Graf Motoru ────────────────────

class ImpactGraph:
    """In-memory graf motoru — adjacency list tabanlı."""
    
    def __init__(self):
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []
        self.adjacency: dict[str, list[tuple[str, str, float]]] = {}  # id → [(target, relation, weight)]
        self._load_defaults()
    
    def _load_defaults(self):
        """Varsayılan tekstil sektörü bilgi grafını yükle."""
        for n in DEFAULT_NODES:
            node = GraphNode(
                id=n["id"],
                label=n["label"],
                node_type=n["type"],
                icon=NODE_TYPES.get(n["type"], "📌"),
            )
            self.nodes[n["id"]] = node
            self.adjacency.setdefault(n["id"], [])
        
        for src, tgt, rel, weight in DEFAULT_EDGES:
            self.edges.append(GraphEdge(src, tgt, rel, weight))
            self.adjacency.setdefault(src, []).append((tgt, rel, weight))
            # Çift yönlü (undirected) — ters yön daha düşük ağırlıkla
            self.adjacency.setdefault(tgt, []).append((src, f"←{rel}", weight * 0.6))
    
    def find_node_by_keyword(self, keyword: str) -> Optional[str]:
        """Anahtar kelimeden düğüm ID'si bul."""
        kw = keyword.lower().strip()
        
        # Doğrudan label eşleşmesi
        for nid, node in self.nodes.items():
            if kw in node.label.lower() or node.label.lower() in kw:
                return nid
        
        # Kısmi eşleşme
        for nid, node in self.nodes.items():
            parts = kw.split()
            if any(p in node.label.lower() for p in parts if len(p) > 2):
                return nid
        
        return None
    
    def analyze_impact(
        self,
        focus_keyword: str,
        max_depth: int = 3,
    ) -> GraphImpactResult:
        """
        Odak düğümünden başlayarak etki yayılımını analiz et (BFS).
        """
        focus_id = self.find_node_by_keyword(focus_keyword)
        
        if not focus_id:
            # Keyword'e en yakın düğümleri bul
            logger.warning("graph_node_not_found", keyword=focus_keyword)
            return GraphImpactResult(
                focus_node=focus_keyword,
                summary=f"'{focus_keyword}' ile eşleşen düğüm bulunamadı.",
            )
        
        focus_node = self.nodes[focus_id]
        
        # BFS ile etki yayılımı
        visited: set[str] = {focus_id}
        queue: list[tuple[str, int, float, list[str], list[str]]] = []
        # (node_id, depth, cumulative_weight, path, relations)
        
        for tgt, rel, weight in self.adjacency.get(focus_id, []):
            if tgt not in visited:
                queue.append((tgt, 1, weight, [focus_id, tgt], [rel]))
        
        impacted: list[dict[str, Any]] = []
        paths: list[ImpactPath] = []
        max_reached_depth = 0
        
        while queue:
            node_id, depth, cum_weight, path, rels = queue.pop(0)
            
            if node_id in visited or depth > max_depth:
                continue
            
            visited.add(node_id)
            max_reached_depth = max(max_reached_depth, depth)
            
            node = self.nodes.get(node_id)
            if not node:
                continue
            
            # Etki skoru = ağırlık × derinlik cezası
            decay = 1.0 / (depth ** 0.5)  # sqrt decay
            impact_score = cum_weight * decay
            
            impacted.append({
                "id": node_id,
                "label": node.label,
                "type": node.node_type,
                "icon": node.icon,
                "depth": depth,
                "impact_score": round(impact_score, 3),
                "relation_chain": " → ".join(rels),
            })
            
            paths.append(ImpactPath(
                path=[self.nodes[p].label if p in self.nodes else p for p in path],
                total_weight=round(cum_weight, 3),
                relations=rels,
            ))
            
            # Sonraki seviye komşular
            if depth < max_depth:
                for tgt, rel, weight in self.adjacency.get(node_id, []):
                    if tgt not in visited:
                        queue.append((
                            tgt,
                            depth + 1,
                            cum_weight * weight,
                            path + [tgt],
                            rels + [rel],
                        ))
        
        # Etkiye göre sırala
        impacted.sort(key=lambda x: x["impact_score"], reverse=True)
        
        # Kritik zincir — en yüksek ağırlıklı yol
        critical = ""
        if paths:
            best_path = max(paths, key=lambda p: p.total_weight)
            critical = " → ".join(best_path.path)
        
        summary = self._build_summary(focus_node, impacted, max_reached_depth)
        
        result = GraphImpactResult(
            focus_node=focus_node.label,
            focus_type=focus_node.node_type,
            impacted_nodes=impacted,
            impact_paths=paths,
            total_nodes_affected=len(impacted),
            max_depth=max_reached_depth,
            critical_chain=critical,
            summary=summary,
        )
        
        logger.info("graph_impact_analyzed",
                     focus=focus_node.label,
                     affected=len(impacted),
                     depth=max_reached_depth)
        
        return result
    
    def _build_summary(
        self,
        focus: GraphNode,
        impacted: list[dict],
        depth: int,
    ) -> str:
        lines = []
        lines.append(f"**{focus.icon} {focus.label}** üzerindeki değişiklik "
                      f"**{len(impacted)} düğümü** etkiler (maks. {depth} seviye derinlik).\n")
        
        by_type: dict[str, int] = {}
        for imp in impacted:
            by_type[imp["type"]] = by_type.get(imp["type"], 0) + 1
        
        for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
            icon = NODE_TYPES.get(t, "📌")
            lines.append(f"- {icon} {t}: {count} etkilenen düğüm")
        
        # En çok etkilenen 3
        if impacted:
            lines.append("\n**En Çok Etkilenen:**")
            for imp in impacted[:3]:
                lines.append(f"  - {imp['icon']} {imp['label']} "
                             f"(skor: {imp['impact_score']}, derinlik: {imp['depth']})")
        
        return "\n".join(lines)


# ──────────────────── Singleton ────────────────────
impact_graph = ImpactGraph()


# ──────────────────── Formatlama ────────────────────

def format_graph_impact(result: GraphImpactResult) -> str:
    """Graf etki sonucunu markdown tablo olarak formatla."""
    if not result.impacted_nodes:
        return f"_'{result.focus_node}' için graf etkisi bulunamadı._"
    
    lines = [
        f"\n### 🕸️ Graf Etki Haritası — {result.focus_node}\n",
        "| # | Düğüm | Tip | Derinlik | Etki Skoru | İlişki Zinciri |",
        "|---|-------|-----|----------|------------|----------------|",
    ]
    
    for i, imp in enumerate(result.impacted_nodes[:15], 1):
        lines.append(
            f"| {i} | {imp['icon']} {imp['label']} | {imp['type']} | "
            f"{imp['depth']} | {imp['impact_score']} | {imp['relation_chain']} |"
        )
    
    lines.append("")
    
    if result.critical_chain:
        lines.append(f"**🔗 Kritik Zincir:** {result.critical_chain}")
    
    lines.append("")
    lines.append(result.summary)
    
    return "\n".join(lines)


# ──────────────────── LLM Sorusundan Otomatik Analiz ────────────────────

def auto_graph_analysis(question: str, context: str = "") -> Optional[GraphImpactResult]:
    """
    Sorudaki anahtar kelimelerden otomatik graf analizi yap.
    Eğer ilgili düğüm bulunursa analiz döndürür, bulunamazsa None.
    """
    # Anahtar kelimeleri çıkar
    keywords = [
        "oee", "fire", "teslimat", "gelir", "maliyet", "devir", "stok", "ret",
        "makine", "hammadde", "kalite", "personel", "döviz", "kur",
        "dokuma", "boya", "boyama", "üretim", "satış", "finans", "lojistik",
        "kâr", "nakit", "borç", "müşteri",
    ]
    
    q_lower = question.lower()
    
    for kw in keywords:
        if kw in q_lower:
            result = impact_graph.analyze_impact(kw)
            if result.total_nodes_affected > 0:
                return result
    
    return None


# ──────────────────── Tool Wrapper ────────────────────

def graph_impact_tool(question: str, context: str = "") -> str:
    """Tool registry'den çağrılabilir graf etki wrapper."""
    result = auto_graph_analysis(question, context)
    if result:
        return format_graph_impact(result)
    return "Soruda graf analizi uygulanabilir bir metrik bulunamadı."
