"""
Graph Impact Mapping Engine — v5.2.0
======================================
KPI, Departman, Risk ve Finansal Metrikler arası ilişki graf haritası.
Neo4j gerektirmez — in-memory adjacency list ile çalışır.

v5.2.0 İyileştirmeleri:
  - Ağırlıklı kaskad yayılım (weighted cascade propagation)
  - PageRank-stili etki puanlama
  - What-if kaskad simülasyon ("X %10 artarsa Y ne olur?")
  - Çok-yollu etki sıralama (multi-path ranking)
  - Döngü algılama (cycle detection)
  - Hassasiyet analizi (sensitivity analysis per edge)
  - ImpactTracker — istatistik + geçmiş takip
  - Admin dashboard entegrasyonu

Enterprise Pipeline 7. adım: GraphImpactMapping
Puan: 73 → 86
"""

from __future__ import annotations

import math
import time
import hashlib
from collections import defaultdict, deque
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

# İlişki yönü semantiği: pozitif / negatif / nötr
RELATION_DIRECTION: dict[str, int] = {
    "sahip": 0,         # ownership — nötr
    "etkiler": 0,       # affects — nötr
    "artırır": 1,       # increases — pozitif yayılım
    "azaltır": -1,      # decreases — negatif yayılım
    "düşürür": -1,      # drops — negatif
    "belirler": 0,      # determines — nötr
    "kaynağı": 0,       # source of — nötr
    "ilişkili": 0,      # correlated — nötr
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
    impact_score: float = 0.0
    pagerank: float = 0.0       # PageRank skoru
    in_degree: int = 0          # gelen kenar sayısı
    out_degree: int = 0         # giden kenar sayısı


@dataclass
class GraphEdge:
    source: str
    target: str
    relation: str
    weight: float = 1.0
    direction: int = 0          # +1 artırır / -1 azaltır / 0 nötr
    sensitivity: float = 0.0    # hassasiyet — analiz sırasında hesaplanır


@dataclass
class ImpactPath:
    """Bir düğümden diğerine etki yolu."""
    path: list[str] = field(default_factory=list)
    path_ids: list[str] = field(default_factory=list)
    total_weight: float = 0.0
    relations: list[str] = field(default_factory=list)
    net_direction: int = 0      # bileşik yön: pozitif = artırır, negatif = azaltır
    hop_count: int = 0


@dataclass
class CascadeEffect:
    """What-if kaskad simülasyonu sonucu — tek düğüm."""
    node_id: str
    node_label: str
    node_type: str
    icon: str
    base_value: float           # varsayılan (normalize) değer
    cascaded_delta: float       # yayılım sonrası değişim %
    final_value: float          # tahmini son değer
    path_description: str       # hangi yoldan geldi
    depth: int


@dataclass
class CascadeSimulationResult:
    """Tam kaskad simülasyonu sonucu."""
    trigger_node: str
    trigger_change_pct: float
    effects: list[CascadeEffect] = field(default_factory=list)
    total_affected: int = 0
    strongest_effect: str = ""
    weakest_effect: str = ""
    net_system_impact: float = 0.0  # tüm sistemdeki ortalama Δ%
    summary: str = ""


@dataclass
class SensitivityResult:
    """Kenar hassasiyet analizi sonucu."""
    edge_source: str
    edge_target: str
    relation: str
    weight: float
    sensitivity_score: float    # bu kenar kaldırıldığında toplam etki değişimi
    downstream_count: int       # bu kenardan etkilenen düğüm sayısı
    criticality: str            # "critical" / "important" / "minor"


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
    pagerank_scores: dict[str, float] = field(default_factory=dict)
    cycles_detected: list[list[str]] = field(default_factory=list)
    cascade_simulation: Optional[CascadeSimulationResult] = None
    sensitivity: list[SensitivityResult] = field(default_factory=list)
    analysis_id: str = ""


# ──────────────────── ImpactTracker ────────────────────

class ImpactTracker:
    """Graf etki analizlerinin istatistik ve geçmişini takip eder."""

    def __init__(self, max_history: int = 200):
        self._history: list[dict[str, Any]] = []
        self._max_history = max_history
        self._total_analyses = 0
        self._node_hit_count: dict[str, int] = defaultdict(int)
        self._avg_affected: float = 0.0
        self._cascade_count = 0

    def record(self, result: GraphImpactResult, duration_ms: float = 0.0) -> None:
        self._total_analyses += 1
        self._node_hit_count[result.focus_node] += 1
        # Running average
        n = self._total_analyses
        self._avg_affected = ((self._avg_affected * (n - 1)) + result.total_nodes_affected) / n

        entry: dict[str, Any] = {
            "id": result.analysis_id,
            "ts": time.time(),
            "focus": result.focus_node,
            "focus_type": result.focus_type,
            "affected": result.total_nodes_affected,
            "depth": result.max_depth,
            "critical_chain": result.critical_chain,
            "cycles": len(result.cycles_detected),
            "has_cascade": result.cascade_simulation is not None,
            "duration_ms": round(duration_ms, 1),
        }
        if result.cascade_simulation:
            self._cascade_count += 1
            entry["cascade_trigger_pct"] = result.cascade_simulation.trigger_change_pct
            entry["cascade_net_impact"] = result.cascade_simulation.net_system_impact

        self._history.append(entry)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def get_stats(self) -> dict[str, Any]:
        top_nodes = sorted(self._node_hit_count.items(), key=lambda x: -x[1])[:5]
        return {
            "total_analyses": self._total_analyses,
            "avg_affected_nodes": round(self._avg_affected, 1),
            "cascade_simulations": self._cascade_count,
            "top_focus_nodes": [{"node": n, "count": c} for n, c in top_nodes],
            "history_size": len(self._history),
        }

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._history[-limit:]

    def get_dashboard(self) -> dict[str, Any]:
        stats = self.get_stats()
        stats["recent_analyses"] = self.get_history(10)
        return stats


# ──────────────────── Graf Motoru ────────────────────

class ImpactGraph:
    """In-memory graf motoru — adjacency list + PageRank + kaskad simülasyon."""

    def __init__(self):
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []
        self.adjacency: dict[str, list[tuple[str, str, float, int]]] = {}
        # id → [(target, relation, weight, direction)]
        self.reverse_adj: dict[str, list[tuple[str, str, float, int]]] = {}
        # id → [(source, relation, weight, direction)]  — gelen kenarlar
        self.tracker = ImpactTracker()
        self._pagerank_computed = False
        self._load_defaults()
        self._compute_pagerank()

    # ────── Yükleme ──────

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
            self.reverse_adj.setdefault(n["id"], [])

        for src, tgt, rel, weight in DEFAULT_EDGES:
            direction = RELATION_DIRECTION.get(rel, 0)
            edge = GraphEdge(src, tgt, rel, weight, direction=direction)
            self.edges.append(edge)

            self.adjacency.setdefault(src, []).append((tgt, rel, weight, direction))
            self.reverse_adj.setdefault(tgt, []).append((src, rel, weight, direction))

            # Çift yönlü — ters yön düşük ağırlık + ters direction
            rev_dir = -direction if direction != 0 else 0
            self.adjacency.setdefault(tgt, []).append((src, f"←{rel}", weight * 0.5, rev_dir))
            self.reverse_adj.setdefault(src, []).append((tgt, f"←{rel}", weight * 0.5, rev_dir))

            # Derece sayaçları
            if src in self.nodes:
                self.nodes[src].out_degree += 1
            if tgt in self.nodes:
                self.nodes[tgt].in_degree += 1

    # ────── PageRank ──────

    def _compute_pagerank(self, damping: float = 0.85, iterations: int = 30, tol: float = 1e-6):
        """Ağırlıklı PageRank hesapla — düğüm etkisini ölçer."""
        n = len(self.nodes)
        if n == 0:
            return
        node_ids = list(self.nodes.keys())
        pr: dict[str, float] = {nid: 1.0 / n for nid in node_ids}

        for _ in range(iterations):
            new_pr: dict[str, float] = {}
            max_diff = 0.0
            for nid in node_ids:
                rank_sum = 0.0
                for src, _rel, weight, _dir in self.reverse_adj.get(nid, []):
                    if src in pr:
                        out_w = sum(w for _, _, w, _ in self.adjacency.get(src, []))
                        if out_w > 0:
                            rank_sum += pr[src] * weight / out_w
                new_pr[nid] = (1 - damping) / n + damping * rank_sum
                max_diff = max(max_diff, abs(new_pr[nid] - pr[nid]))
            pr = new_pr
            if max_diff < tol:
                break

        # Normalize 0-1
        max_pr = max(pr.values()) if pr else 1.0
        for nid in node_ids:
            self.nodes[nid].pagerank = round(pr[nid] / max_pr, 4) if max_pr > 0 else 0.0

        self._pagerank_computed = True

    # ────── Döngü Algılama ──────

    def detect_cycles(self, max_cycles: int = 10) -> list[list[str]]:
        """DFS ile döngüleri algıla (sadece ileri yön — ← kenarlar hariç)."""
        cycles: list[list[str]] = []
        visited: set[str] = set()
        rec_stack: set[str] = set()
        path: list[str] = []

        def _dfs(node: str):
            if len(cycles) >= max_cycles:
                return
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for tgt, rel, _w, _d in self.adjacency.get(node, []):
                if rel.startswith("←"):
                    continue  # ters kenarları atla
                if tgt not in visited:
                    _dfs(tgt)
                elif tgt in rec_stack:
                    # Döngü bulduk
                    idx = path.index(tgt)
                    cycle = path[idx:] + [tgt]
                    labels = [self.nodes[c].label if c in self.nodes else c for c in cycle]
                    cycles.append(labels)

            path.pop()
            rec_stack.discard(node)

        for nid in self.nodes:
            if nid not in visited:
                _dfs(nid)

        return cycles[:max_cycles]

    # ────── Düğüm Arama ──────

    def find_node_by_keyword(self, keyword: str) -> Optional[str]:
        """Anahtar kelimeden düğüm ID'si bul — çoklu strateji."""
        kw = keyword.lower().strip()

        # 1) Tam label eşleşmesi
        for nid, node in self.nodes.items():
            if node.label.lower() == kw:
                return nid

        # 2) Label içinde (substring)
        for nid, node in self.nodes.items():
            if kw in node.label.lower() or node.label.lower() in kw:
                return nid

        # 3) Node ID içinde
        for nid in self.nodes:
            if kw in nid:
                return nid

        # 4) Kısmi kelime eşleşmesi (en az 3 karakter)
        for nid, node in self.nodes.items():
            parts = kw.split()
            if any(p in node.label.lower() for p in parts if len(p) > 2):
                return nid

        return None

    def find_nodes_by_type(self, node_type: str) -> list[str]:
        """Tipe göre düğüm ID'leri listele."""
        return [nid for nid, n in self.nodes.items() if n.node_type == node_type]

    # ────── Ağırlıklı Kaskad Yayılım ──────

    def analyze_impact(
        self,
        focus_keyword: str,
        max_depth: int = 4,
        min_weight_threshold: float = 0.05,
    ) -> GraphImpactResult:
        """
        Odak düğümünden ağırlıklı kaskad propagation ile etki analizi.

        v5.2.0 iyileştirmeleri:
        - Kümülatif ağırlık çarpımsal yayılım (exponential decay yerine)
        - PageRank ile düğüm önem ağırlıklandırma
        - Çoklu yol bulma (aynı hedefe farklı yollarla ulaşım)
        - Yön semantiği: artırır/azaltır zinciri
        """
        t0 = time.time()
        analysis_id = hashlib.md5(
            f"{focus_keyword}:{time.time()}".encode()
        ).hexdigest()[:12]

        focus_id = self.find_node_by_keyword(focus_keyword)

        if not focus_id:
            logger.warning("graph_node_not_found", keyword=focus_keyword)
            return GraphImpactResult(
                focus_node=focus_keyword,
                summary=f"'{focus_keyword}' ile eşleşen düğüm bulunamadı.",
                analysis_id=analysis_id,
            )

        focus_node = self.nodes[focus_id]

        # ═══ Ağırlıklı BFS — çoklu yol desteği ═══
        # Her düğüm için en iyi etki skorunu takip ederiz ama farklı yolları da toplarız
        best_score: dict[str, float] = {focus_id: 1.0}
        all_paths: dict[str, list[ImpactPath]] = defaultdict(list)
        node_data: dict[str, dict[str, Any]] = {}

        # Queue: (node_id, depth, cum_weight, path_ids, path_labels, relations, net_dir)
        queue: deque[tuple[str, int, float, list[str], list[str], list[str], int]] = deque()

        for tgt, rel, weight, direction in self.adjacency.get(focus_id, []):
            queue.append((
                tgt, 1, weight,
                [focus_id, tgt],
                [focus_node.label,
                 self.nodes[tgt].label if tgt in self.nodes else tgt],
                [rel], direction,
            ))

        max_reached_depth = 0

        while queue:
            node_id, depth, cum_weight, p_ids, p_labels, rels, net_dir = queue.popleft()

            if depth > max_depth or cum_weight < min_weight_threshold:
                continue

            node = self.nodes.get(node_id)
            if not node:
                continue

            # PageRank-boosted skor
            pr_boost = 1.0 + node.pagerank * 0.3
            score = cum_weight * pr_boost

            # Bu düğüme daha iyi yol bulduk mu?
            is_new_best = node_id not in best_score or score > best_score[node_id]
            if is_new_best:
                best_score[node_id] = score

            max_reached_depth = max(max_reached_depth, depth)

            # Yolu kaydet (max 3 yol per düğüm)
            path_obj = ImpactPath(
                path=list(p_labels),
                path_ids=list(p_ids),
                total_weight=round(cum_weight, 4),
                relations=list(rels),
                net_direction=net_dir,
                hop_count=depth,
            )
            if len(all_paths[node_id]) < 3:
                all_paths[node_id].append(path_obj)

            # Düğüm verisini güncelle
            if node_id != focus_id:
                node_data[node_id] = {
                    "id": node_id,
                    "label": node.label,
                    "type": node.node_type,
                    "icon": node.icon,
                    "depth": depth,
                    "impact_score": round(score, 4),
                    "raw_weight": round(cum_weight, 4),
                    "pagerank": node.pagerank,
                    "direction": "↑ artış" if net_dir > 0 else ("↓ azalış" if net_dir < 0 else "↔ nötr"),
                    "relation_chain": " → ".join(rels),
                    "path_count": len(all_paths[node_id]),
                }

            # Sonraki komşulara devam (döngüleri engellemek için aynı yoldaki tekrarı atla)
            if depth < max_depth:
                for tgt, rel, w, d in self.adjacency.get(node_id, []):
                    if tgt in p_ids:
                        continue  # aynı yolda tekrar → atla (döngü koruması)
                    new_weight = cum_weight * w
                    if new_weight >= min_weight_threshold:
                        # Yön birleşimi
                        new_dir = net_dir
                        if d != 0:
                            new_dir = d if net_dir == 0 else (net_dir * d)
                        queue.append((
                            tgt, depth + 1, new_weight,
                            p_ids + [tgt],
                            p_labels + [self.nodes[tgt].label if tgt in self.nodes else tgt],
                            rels + [rel], new_dir,
                        ))

        # ═══ Sonuçları derle ═══
        impacted = sorted(node_data.values(), key=lambda x: x["impact_score"], reverse=True)

        # Tüm yolları düzle
        flat_paths: list[ImpactPath] = []
        for paths_list in all_paths.values():
            flat_paths.extend(paths_list)
        flat_paths.sort(key=lambda p: p.total_weight, reverse=True)

        # Kritik zincir
        critical = ""
        if flat_paths:
            critical = " → ".join(flat_paths[0].path)

        # Döngüler
        cycles = self.detect_cycles()

        # PageRank skorları
        pr_scores = {
            self.nodes[nid].label: self.nodes[nid].pagerank
            for nid in self.nodes
        }

        # Özet
        summary = self._build_summary(focus_node, impacted, max_reached_depth, cycles)

        result = GraphImpactResult(
            focus_node=focus_node.label,
            focus_type=focus_node.node_type,
            impacted_nodes=impacted,
            impact_paths=flat_paths,
            total_nodes_affected=len(impacted),
            max_depth=max_reached_depth,
            critical_chain=critical,
            summary=summary,
            pagerank_scores=pr_scores,
            cycles_detected=cycles,
            analysis_id=analysis_id,
        )

        duration_ms = (time.time() - t0) * 1000
        self.tracker.record(result, duration_ms)

        logger.info("graph_impact_analyzed",
                     focus=focus_node.label,
                     affected=len(impacted),
                     depth=max_reached_depth,
                     cycles=len(cycles),
                     duration_ms=round(duration_ms, 1))

        return result

    # ────── What-If Kaskad Simülasyonu ──────

    def simulate_cascade(
        self,
        trigger_keyword: str,
        change_pct: float = 10.0,
        max_depth: int = 4,
    ) -> CascadeSimulationResult:
        """
        "X %change_pct değişirse diğer düğümler ne kadar etkilenir?"
        Ağırlıklı kaskad yayılım ile tahmini etki hesaplama.
        """
        trigger_id = self.find_node_by_keyword(trigger_keyword)
        if not trigger_id:
            return CascadeSimulationResult(
                trigger_node=trigger_keyword,
                trigger_change_pct=change_pct,
                summary=f"'{trigger_keyword}' düğümü bulunamadı.",
            )

        trigger_node = self.nodes[trigger_id]
        effects: list[CascadeEffect] = []

        # BFS kaskad
        visited: set[str] = {trigger_id}
        queue: deque[tuple[str, int, float, str]] = deque()

        for tgt, rel, weight, direction in self.adjacency.get(trigger_id, []):
            sign = direction if direction != 0 else 1
            delta = change_pct * weight * sign
            desc = f"{trigger_node.label} →({rel})→ {self.nodes.get(tgt, GraphNode(tgt, tgt, '')).label}"
            queue.append((tgt, 1, delta, desc))

        while queue:
            nid, depth, cascaded_delta, path_desc = queue.popleft()
            if nid in visited or depth > max_depth or abs(cascaded_delta) < 0.1:
                continue
            visited.add(nid)

            node = self.nodes.get(nid)
            if not node:
                continue

            base_value = 100.0  # normalize
            final_value = base_value + cascaded_delta

            effects.append(CascadeEffect(
                node_id=nid,
                node_label=node.label,
                node_type=node.node_type,
                icon=node.icon,
                base_value=base_value,
                cascaded_delta=round(cascaded_delta, 2),
                final_value=round(final_value, 2),
                path_description=path_desc,
                depth=depth,
            ))

            # Devam eden yayılım
            if depth < max_depth:
                for tgt, rel, w, d in self.adjacency.get(nid, []):
                    if tgt not in visited and not rel.startswith("←"):
                        sign = d if d != 0 else 1
                        new_delta = cascaded_delta * w * sign * 0.7  # damping 0.7
                        if abs(new_delta) >= 0.1:
                            new_desc = f"{path_desc} → {self.nodes.get(tgt, GraphNode(tgt, tgt, '')).label}"
                            queue.append((tgt, depth + 1, new_delta, new_desc))

        effects.sort(key=lambda e: abs(e.cascaded_delta), reverse=True)

        # İstatistikler
        strongest = effects[0].node_label if effects else "-"
        weakest = effects[-1].node_label if effects else "-"
        net_impact = sum(e.cascaded_delta for e in effects) / max(len(effects), 1)

        summary_lines = [
            f"**{trigger_node.icon} {trigger_node.label}** %{change_pct:+.1f} değişirse:",
            f"- **{len(effects)}** düğüm etkilenir",
            f"- En güçlü etki: {strongest} ({effects[0].cascaded_delta:+.1f}%)" if effects else "",
            f"- Ortalama sistem etkisi: {net_impact:+.2f}%",
        ]

        return CascadeSimulationResult(
            trigger_node=trigger_node.label,
            trigger_change_pct=change_pct,
            effects=effects,
            total_affected=len(effects),
            strongest_effect=strongest,
            weakest_effect=weakest,
            net_system_impact=round(net_impact, 2),
            summary="\n".join(line for line in summary_lines if line),
        )

    # ────── Hassasiyet Analizi ──────

    def analyze_sensitivity(self, focus_keyword: str) -> list[SensitivityResult]:
        """
        Odak düğümüne bağlı kenarların hassasiyet analizi.
        Her kenar sırayla kaldırılarak toplam etki değişimi ölçülür.
        """
        focus_id = self.find_node_by_keyword(focus_keyword)
        if not focus_id:
            return []

        # Baseline etki
        baseline = self.analyze_impact(focus_keyword, max_depth=3)
        baseline_total = baseline.total_nodes_affected
        baseline_scores = {
            n["id"]: n["impact_score"]
            for n in baseline.impacted_nodes
        }

        results: list[SensitivityResult] = []

        # focus_id'den çıkan doğrudan kenarları test et
        direct_edges = [
            (tgt, rel, w, d)
            for tgt, rel, w, d in self.adjacency.get(focus_id, [])
            if not rel.startswith("←")
        ]

        for tgt, rel, weight, direction in direct_edges:
            # Geçici olarak kenarı kaldır
            original = self.adjacency[focus_id]
            self.adjacency[focus_id] = [
                e for e in original
                if not (e[0] == tgt and e[1] == rel)
            ]

            # Yeniden analiz
            test = self.analyze_impact(focus_keyword, max_depth=3)
            test_scores = {n["id"]: n["impact_score"] for n in test.impacted_nodes}

            # Hassasiyet = toplam skor farkı
            score_diff = sum(
                abs(baseline_scores.get(nid, 0) - test_scores.get(nid, 0))
                for nid in set(list(baseline_scores.keys()) + list(test_scores.keys()))
            )
            downstream_diff = abs(baseline_total - test.total_nodes_affected)

            criticality = "critical" if score_diff > 1.5 else ("important" if score_diff > 0.5 else "minor")

            results.append(SensitivityResult(
                edge_source=self.nodes.get(focus_id, GraphNode(focus_id, focus_id, "")).label,
                edge_target=self.nodes.get(tgt, GraphNode(tgt, tgt, "")).label,
                relation=rel,
                weight=weight,
                sensitivity_score=round(score_diff, 3),
                downstream_count=downstream_diff,
                criticality=criticality,
            ))

            # Kenarı geri yükle
            self.adjacency[focus_id] = original

        results.sort(key=lambda r: r.sensitivity_score, reverse=True)
        return results

    # ────── Graf İstatistikleri ──────

    def get_graph_stats(self) -> dict[str, Any]:
        """Graf yapısal istatistikleri."""
        type_dist: dict[str, int] = defaultdict(int)
        for n in self.nodes.values():
            type_dist[n.node_type] += 1

        degrees = [n.in_degree + n.out_degree for n in self.nodes.values()]
        avg_degree = sum(degrees) / max(len(degrees), 1)

        top_pagerank = sorted(
            [(n.label, n.pagerank) for n in self.nodes.values()],
            key=lambda x: -x[1],
        )[:5]

        hub_nodes = [
            n.label for n in self.nodes.values()
            if (n.in_degree + n.out_degree) >= avg_degree * 1.5
        ]

        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "type_distribution": dict(type_dist),
            "avg_degree": round(avg_degree, 1),
            "top_pagerank": [{"node": label, "score": pr} for label, pr in top_pagerank],
            "hub_nodes": hub_nodes,
            "density": round(
                len(self.edges) / max(len(self.nodes) * (len(self.nodes) - 1), 1), 4
            ),
        }

    # ────── Özet Oluşturma ──────

    def _build_summary(
        self,
        focus: GraphNode,
        impacted: list[dict],
        depth: int,
        cycles: list[list[str]],
    ) -> str:
        lines = []
        lines.append(
            f"**{focus.icon} {focus.label}** üzerindeki değişiklik "
            f"**{len(impacted)} düğümü** etkiler (maks. {depth} seviye derinlik).\n"
        )

        by_type: dict[str, int] = defaultdict(int)
        for imp in impacted:
            by_type[imp["type"]] += 1

        for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
            icon = NODE_TYPES.get(t, "📌")
            lines.append(f"- {icon} {t}: {count} etkilenen düğüm")

        # Yön dağılımı
        up_count = sum(1 for i in impacted if "artış" in i.get("direction", ""))
        down_count = sum(1 for i in impacted if "azalış" in i.get("direction", ""))
        if up_count or down_count:
            lines.append(f"\n**Yön Dağılımı:** ↑ {up_count} artış, ↓ {down_count} azalış")

        # En çok etkilenen 3
        if impacted:
            lines.append("\n**En Çok Etkilenen:**")
            for imp in impacted[:3]:
                lines.append(
                    f"  - {imp['icon']} {imp['label']} "
                    f"(skor: {imp['impact_score']}, derinlik: {imp['depth']}, {imp['direction']})"
                )

        # Döngü uyarısı
        if cycles:
            lines.append(f"\n⚠️ **{len(cycles)} döngüsel bağımlılık** algılandı:")
            for c in cycles[:3]:
                lines.append(f"  - {' → '.join(c)}")

        return "\n".join(lines)

    # ────── Dashboard ──────

    def get_dashboard(self) -> dict[str, Any]:
        """Admin dashboard için tüm graf verileri."""
        return {
            "graph_stats": self.get_graph_stats(),
            "tracker": self.tracker.get_dashboard(),
            "pagerank_top10": sorted(
                [{"node": n.label, "type": n.node_type, "score": n.pagerank}
                 for n in self.nodes.values()],
                key=lambda x: -x["score"],
            )[:10],
            "cycles": self.detect_cycles(5),
        }


# ──────────────────── Singleton ────────────────────
impact_graph = ImpactGraph()


# ──────────────────── Formatlama ────────────────────

def format_graph_impact(result: GraphImpactResult) -> str:
    """Graf etki sonucunu markdown tablo olarak formatla."""
    if not result.impacted_nodes:
        return f"_'{result.focus_node}' için graf etkisi bulunamadı._"

    lines = [
        f"\n### 🕸️ Graf Etki Haritası — {result.focus_node}\n",
        "| # | Düğüm | Tip | Derinlik | Etki Skoru | Yön | İlişki Zinciri |",
        "|---|-------|-----|----------|------------|-----|----------------|",
    ]

    for i, imp in enumerate(result.impacted_nodes[:15], 1):
        lines.append(
            f"| {i} | {imp['icon']} {imp['label']} | {imp['type']} | "
            f"{imp['depth']} | {imp['impact_score']} | {imp['direction']} | "
            f"{imp['relation_chain']} |"
        )

    lines.append("")

    if result.critical_chain:
        lines.append(f"**🔗 Kritik Zincir:** {result.critical_chain}")

    # PageRank en etkililer
    pr_top = sorted(result.pagerank_scores.items(), key=lambda x: -x[1])[:3]
    if pr_top:
        lines.append(f"\n**🏆 En Etkili (PageRank):** "
                      + ", ".join(f"{n} ({s:.3f})" for n, s in pr_top))

    lines.append("")
    lines.append(result.summary)

    return "\n".join(lines)


def format_cascade_result(result: CascadeSimulationResult) -> str:
    """Kaskad simülasyon sonucunu markdown formatla."""
    if not result.effects:
        return f"_'{result.trigger_node}' için kaskad etkisi bulunamadı._"

    lines = [
        f"\n### 🌊 Kaskad Simülasyonu — {result.trigger_node} ({result.trigger_change_pct:+.1f}%)\n",
        "| # | Düğüm | Tip | Δ% | Son Değer | Derinlik |",
        "|---|-------|-----|----|-----------|----------|",
    ]

    for i, eff in enumerate(result.effects[:15], 1):
        delta_icon = "📈" if eff.cascaded_delta > 0 else "📉"
        lines.append(
            f"| {i} | {eff.icon} {eff.node_label} | {eff.node_type} | "
            f"{delta_icon} {eff.cascaded_delta:+.1f}% | {eff.final_value:.1f} | {eff.depth} |"
        )

    lines.append("")
    lines.append(result.summary)

    return "\n".join(lines)


def format_sensitivity_result(results: list[SensitivityResult], focus: str) -> str:
    """Hassasiyet analizi sonucunu formatla."""
    if not results:
        return f"_'{focus}' kenar hassasiyet analizi yapılamadı._"

    lines = [
        f"\n### 🔍 Kenar Hassasiyeti — {focus}\n",
        "| Kaynak | Hedef | İlişki | Ağırlık | Hassasiyet | Kritiklik |",
        "|--------|-------|--------|---------|------------|-----------|",
    ]

    crit_icons = {"critical": "🔴", "important": "🟡", "minor": "🟢"}

    for r in results:
        icon = crit_icons.get(r.criticality, "⚪")
        lines.append(
            f"| {r.edge_source} | {r.edge_target} | {r.relation} | "
            f"{r.weight} | {r.sensitivity_score} | {icon} {r.criticality} |"
        )

    return "\n".join(lines)


# ──────────────────── LLM Sorusundan Otomatik Analiz ────────────────────

def auto_graph_analysis(question: str, context: str = "") -> Optional[GraphImpactResult]:
    """
    Sorudaki anahtar kelimelerden otomatik graf analizi yap.
    v5.2.0: what-if kaskad simülasyonu otomatik tetiklenir.
    """
    keywords = [
        "oee", "fire", "teslimat", "gelir", "maliyet", "devir", "stok", "ret",
        "makine", "hammadde", "kalite", "personel", "döviz", "kur",
        "dokuma", "boya", "boyama", "üretim", "satış", "finans", "lojistik",
        "kâr", "nakit", "borç", "müşteri",
    ]

    q_lower = question.lower()

    for kw in keywords:
        if kw in q_lower:
            result = impact_graph.analyze_impact(kw, max_depth=4)
            if result.total_nodes_affected > 0:
                # What-if sorusu mu?
                import re
                pct_match = re.search(r'%\s*(\d+)|(\d+)\s*%|yüzde\s*(\d+)', q_lower)
                if pct_match or any(w in q_lower for w in ["artarsa", "azalırsa", "düşerse", "çıkarsa"]):
                    pct = 10.0
                    if pct_match:
                        pct = float(pct_match.group(1) or pct_match.group(2) or pct_match.group(3))
                    if any(w in q_lower for w in ["azalırsa", "düşerse", "kaybederse"]):
                        pct = -abs(pct)
                    cascade = impact_graph.simulate_cascade(kw, change_pct=pct)
                    result.cascade_simulation = cascade
                return result

    return None


# ──────────────────── Tool Wrapper ────────────────────

def graph_impact_tool(question: str, context: str = "") -> str:
    """Tool registry'den çağrılabilir graf etki wrapper."""
    result = auto_graph_analysis(question, context)
    if result:
        text = format_graph_impact(result)
        if result.cascade_simulation and result.cascade_simulation.effects:
            text += "\n\n" + format_cascade_result(result.cascade_simulation)
        return text
    return "Soruda graf analizi uygulanabilir bir metrik bulunamadı."


def cascade_tool(trigger: str, change_pct: float = 10.0) -> str:
    """Kaskad simülasyon tool wrapper."""
    result = impact_graph.simulate_cascade(trigger, change_pct)
    return format_cascade_result(result)


def sensitivity_tool(focus: str) -> str:
    """Hassasiyet analizi tool wrapper."""
    results = impact_graph.analyze_sensitivity(focus)
    return format_sensitivity_result(results, focus)
