"""Knowledge Graph v1.0 — Bilgi Grafiği Motoru

In-memory bilgi grafiği oluşturarak soru-cevap sürecinde
bağlamsal ilişkilendirme ve bilgi keşfi sağlar.

Bileşenler:
  1. EntityExtractor        → Metinden varlık çıkarımı (NER-benzeri, LLM-destekli)
  2. RelationExtractor      → Varlıklar arası ilişki çıkarımı
  3. KnowledgeStore         → In-memory graf deposu (adjacency list)
  4. GraphQueryEngine       → Graf üzerinde sorgu/traversal
  5. SemanticClusterer      → Bilgi kümeleme ve tema keşfi
  6. ContextEnricher        → Soru bağlamını graf bilgisiyle zenginleştirme
  7. GraphTracker           → İstatistik ve geçmiş

Kullanım Alanları:
  - "Bu kavramla ilişkili diğer kavramları göster"
  - "Departmanlar arası bağlantıları analiz et"
  - "Bilgi haritasını çıkar"
  - "İlişki grafiğini göster"
  - Bağlamsal soru zenginleştirme (tüm sorularda arka planda)

v5.0.0 — CompanyAI Enterprise
"""

from __future__ import annotations

import uuid
import time
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

import structlog

logger = structlog.get_logger(__name__)

# ═══════════════════════════════════════════════════════════════════
# SABİTLER
# ═══════════════════════════════════════════════════════════════════

MAX_ENTITIES = 5000
MAX_RELATIONS = 15000
MAX_QUERY_DEPTH = 5
MAX_CLUSTER_SIZE = 50
MAX_GRAPH_HISTORY = 500
KG_TRIGGER_MIN_LENGTH = 15

KG_TRIGGER_KEYWORDS = [
    "ilişki", "bağlantı", "graf", "graph", "harita", "ağ", "network",
    "knowledge graph", "bilgi graf", "kavram haritası", "concept map",
    "ilişkili", "bağlı", "bağlam", "ilişkilendir",
    "entity", "varlık", "düğüm", "node", "kenar", "edge",
]

ENTITY_TYPES = [
    "Organizasyon",
    "Departman",
    "Kişi",
    "Ürün",
    "Teknoloji",
    "Süreç",
    "Kavram",
    "Lokasyon",
    "Metrik",
    "Döküman",
    "Proje",
    "Risk",
    "Hedef",
    "Müşteri",
    "Tedarikçi",
]

RELATION_TYPES = [
    "sahip",                # Organizasyon → Departman
    "bağlı",               # Departman → Kişi
    "üretir",              # Departman → Ürün
    "kullanır",            # Süreç → Teknoloji
    "etkiler",             # Risk → Hedef
    "bağımlı",             # Proje → Proje
    "ölçer",               # Metrik → Süreç
    "sorumlu",             # Kişi → Proje
    "tedarik_eder",        # Tedarikçi → Ürün
    "müşterisi",           # Müşteri → Ürün
    "alt_kavram",          # Kavram → Kavram
    "ilişkili",            # genel ilişki
    "karşıt",             # zıt kavramlar
    "sebep_olur",          # neden-sonuç
    "benzer",              # benzerlik
]


def _utcnow_str() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
# ENUM & VERİ YAPILARI
# ═══════════════════════════════════════════════════════════════════

class EntityType(str, Enum):
    ORGANIZATION = "Organizasyon"
    DEPARTMENT = "Departman"
    PERSON = "Kişi"
    PRODUCT = "Ürün"
    TECHNOLOGY = "Teknoloji"
    PROCESS = "Süreç"
    CONCEPT = "Kavram"
    LOCATION = "Lokasyon"
    METRIC = "Metrik"
    DOCUMENT = "Döküman"
    PROJECT = "Proje"
    RISK = "Risk"
    GOAL = "Hedef"
    CUSTOMER = "Müşteri"
    SUPPLIER = "Tedarikçi"


class RelationType(str, Enum):
    OWNS = "sahip"
    BELONGS_TO = "bağlı"
    PRODUCES = "üretir"
    USES = "kullanır"
    AFFECTS = "etkiler"
    DEPENDS_ON = "bağımlı"
    MEASURES = "ölçer"
    RESPONSIBLE = "sorumlu"
    SUPPLIES = "tedarik_eder"
    CUSTOMER_OF = "müşterisi"
    SUBCONCEPT = "alt_kavram"
    RELATED = "ilişkili"
    OPPOSITE = "karşıt"
    CAUSES = "sebep_olur"
    SIMILAR = "benzer"


# ─── Veri yapıları ───

@dataclass
class Entity:
    """Graf düğümü — bir varlık."""
    entity_id: str = ""
    name: str = ""
    entity_type: str = "Kavram"
    description: str = ""
    department: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    mention_count: int = 1
    first_seen: str = ""
    last_seen: str = ""
    source_questions: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.entity_id:
            self.entity_id = f"E-{uuid.uuid4().hex[:8]}"
        now = _utcnow_str()
        if not self.first_seen:
            self.first_seen = now
        if not self.last_seen:
            self.last_seen = now

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "type": self.entity_type,
            "description": self.description,
            "department": self.department,
            "properties": self.properties,
            "mention_count": self.mention_count,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
        }


@dataclass
class Relation:
    """Graf kenarı — iki varlık arası ilişki."""
    relation_id: str = ""
    source_id: str = ""
    target_id: str = ""
    relation_type: str = "ilişkili"
    description: str = ""
    weight: float = 1.0
    confidence: float = 0.8
    bidirectional: bool = False
    properties: Dict[str, Any] = field(default_factory=dict)
    mention_count: int = 1
    first_seen: str = ""
    last_seen: str = ""

    def __post_init__(self):
        if not self.relation_id:
            self.relation_id = f"R-{uuid.uuid4().hex[:8]}"
        now = _utcnow_str()
        if not self.first_seen:
            self.first_seen = now
        if not self.last_seen:
            self.last_seen = now

    def to_dict(self) -> dict:
        return {
            "relation_id": self.relation_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "description": self.description,
            "weight": round(self.weight, 2),
            "confidence": round(self.confidence, 2),
            "bidirectional": self.bidirectional,
            "mention_count": self.mention_count,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
        }


@dataclass
class GraphCluster:
    """Semantik küme."""
    cluster_id: str = ""
    theme: str = ""
    entity_ids: List[str] = field(default_factory=list)
    central_entity_id: str = ""
    cohesion_score: float = 0.0
    description: str = ""

    def __post_init__(self):
        if not self.cluster_id:
            self.cluster_id = f"CL-{uuid.uuid4().hex[:6]}"

    def to_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "theme": self.theme,
            "entity_count": len(self.entity_ids),
            "entity_ids": self.entity_ids[:20],
            "central_entity_id": self.central_entity_id,
            "cohesion_score": round(self.cohesion_score, 2),
            "description": self.description,
        }


@dataclass
class GraphQueryResult:
    """Graf sorgusu sonucu."""
    query_id: str = ""
    query_text: str = ""
    entities_found: List[Entity] = field(default_factory=list)
    relations_found: List[Relation] = field(default_factory=list)
    paths: List[List[str]] = field(default_factory=list)
    clusters: List[GraphCluster] = field(default_factory=list)
    context_text: str = ""
    confidence_adjustment: float = 0.0
    total_time_ms: float = 0.0

    def __post_init__(self):
        if not self.query_id:
            self.query_id = f"GQ-{uuid.uuid4().hex[:6]}"

    def to_dict(self) -> dict:
        return {
            "query_id": self.query_id,
            "query_text": self.query_text[:200],
            "entities_found": [e.to_dict() for e in self.entities_found[:20]],
            "relations_found": [r.to_dict() for r in self.relations_found[:30]],
            "paths": self.paths[:10],
            "clusters": [c.to_dict() for c in self.clusters[:5]],
            "context_text": self.context_text[:500],
            "summary": {
                "total_entities": len(self.entities_found),
                "total_relations": len(self.relations_found),
                "total_paths": len(self.paths),
                "total_clusters": len(self.clusters),
            },
            "confidence_adjustment": self.confidence_adjustment,
            "total_time_ms": round(self.total_time_ms, 1),
        }


# ═══════════════════════════════════════════════════════════════════
# TETİKLEME KARARI
# ═══════════════════════════════════════════════════════════════════

def should_trigger_knowledge_graph(
    question: str,
    mode: str,
    intent: str,
    force: bool = False,
) -> Tuple[bool, str]:
    """Bu soruda knowledge graph kullanılmalı mı?"""
    if force:
        return True, "manual_trigger"

    if len(question.strip()) < KG_TRIGGER_MIN_LENGTH:
        return False, "too_short"

    if intent in ("sohbet", "selamlama"):
        return False, "casual_intent"

    q_lower = question.lower()
    keyword_hits = sum(1 for kw in KG_TRIGGER_KEYWORDS if kw in q_lower)

    if keyword_hits >= 2:
        return True, f"keyword_trigger:{keyword_hits}_hits"

    import re
    patterns = [
        r"ilişki\w*\s+(göster|analiz|çıkar)",
        r"bağlant[ıi]\w*\s+(göster|analiz|bul)",
        r"(?:knowledge|bilgi)\s+(?:graph|graf)",
        r"kavram\s+haritası",
        r"ilişkili\s+kavram",
        r"(?:grafik|graf)\s+(?:göster|oluştur|çiz)",
    ]
    for pattern in patterns:
        if re.search(pattern, q_lower):
            return True, f"pattern_trigger:{pattern}"

    return False, "no_trigger"


# ═══════════════════════════════════════════════════════════════════
# IN-MEMORY GRAF DEPOSU
# ═══════════════════════════════════════════════════════════════════

class KnowledgeStore:
    """Adjacency list tabanlı in-memory bilgi grafiği."""

    def __init__(self):
        self._entities: Dict[str, Entity] = {}
        self._name_index: Dict[str, str] = {}       # lowercase name → entity_id
        self._relations: Dict[str, Relation] = {}
        self._adjacency: Dict[str, Set[str]] = defaultdict(set)  # entity_id → {relation_ids}
        self._type_index: Dict[str, Set[str]] = defaultdict(set)  # entity_type → {entity_ids}

    # ─── Entity CRUD ───
    def add_entity(self, entity: Entity) -> Entity:
        name_key = entity.name.lower().strip()
        if name_key in self._name_index:
            existing = self._entities[self._name_index[name_key]]
            existing.mention_count += 1
            existing.last_seen = _utcnow_str()
            if entity.description and not existing.description:
                existing.description = entity.description
            return existing

        if len(self._entities) >= MAX_ENTITIES:
            self._evict_oldest_entity()

        self._entities[entity.entity_id] = entity
        self._name_index[name_key] = entity.entity_id
        self._type_index[entity.entity_type].add(entity.entity_id)
        return entity

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        return self._entities.get(entity_id)

    def find_entity_by_name(self, name: str) -> Optional[Entity]:
        name_key = name.lower().strip()
        eid = self._name_index.get(name_key)
        if eid:
            return self._entities.get(eid)
        for key, eid in self._name_index.items():
            if name_key in key or key in name_key:
                return self._entities.get(eid)
        return None

    def get_entities_by_type(self, entity_type: str) -> List[Entity]:
        eids = self._type_index.get(entity_type, set())
        return [self._entities[eid] for eid in eids if eid in self._entities]

    def search_entities(self, query: str, limit: int = 20) -> List[Entity]:
        q_lower = query.lower().strip()
        results = []
        for name_key, eid in self._name_index.items():
            if q_lower in name_key:
                e = self._entities.get(eid)
                if e:
                    results.append(e)
                if len(results) >= limit:
                    break
        return results

    def _evict_oldest_entity(self):
        if not self._entities:
            return
        oldest = min(self._entities.values(), key=lambda e: e.mention_count)
        self.remove_entity(oldest.entity_id)

    def remove_entity(self, entity_id: str):
        entity = self._entities.pop(entity_id, None)
        if not entity:
            return
        name_key = entity.name.lower().strip()
        self._name_index.pop(name_key, None)
        self._type_index.get(entity.entity_type, set()).discard(entity_id)
        rel_ids = list(self._adjacency.pop(entity_id, set()))
        for rid in rel_ids:
            rel = self._relations.pop(rid, None)
            if rel:
                other = rel.target_id if rel.source_id == entity_id else rel.source_id
                self._adjacency.get(other, set()).discard(rid)

    # ─── Relation CRUD ───
    def add_relation(self, relation: Relation) -> Relation:
        existing = self._find_existing_relation(
            relation.source_id, relation.target_id, relation.relation_type
        )
        if existing:
            existing.mention_count += 1
            existing.weight = min(existing.weight + 0.1, 5.0)
            existing.last_seen = _utcnow_str()
            return existing

        if len(self._relations) >= MAX_RELATIONS:
            self._evict_weakest_relation()

        self._relations[relation.relation_id] = relation
        self._adjacency[relation.source_id].add(relation.relation_id)
        self._adjacency[relation.target_id].add(relation.relation_id)
        return relation

    def _find_existing_relation(
        self, source_id: str, target_id: str, rel_type: str
    ) -> Optional[Relation]:
        for rid in self._adjacency.get(source_id, set()):
            rel = self._relations.get(rid)
            if rel and rel.target_id == target_id and rel.relation_type == rel_type:
                return rel
        return None

    def get_relations_for(self, entity_id: str) -> List[Relation]:
        rids = self._adjacency.get(entity_id, set())
        return [self._relations[rid] for rid in rids if rid in self._relations]

    def _evict_weakest_relation(self):
        if not self._relations:
            return
        weakest = min(self._relations.values(), key=lambda r: r.weight)
        self.remove_relation(weakest.relation_id)

    def remove_relation(self, relation_id: str):
        rel = self._relations.pop(relation_id, None)
        if rel:
            self._adjacency.get(rel.source_id, set()).discard(relation_id)
            self._adjacency.get(rel.target_id, set()).discard(relation_id)

    # ─── Graph Stats ───
    @property
    def entity_count(self) -> int:
        return len(self._entities)

    @property
    def relation_count(self) -> int:
        return len(self._relations)

    def get_stats(self) -> dict:
        type_dist = {t: len(ids) for t, ids in self._type_index.items() if ids}
        avg_degree = 0.0
        if self._entities:
            total_degree = sum(len(self._adjacency.get(eid, set())) for eid in self._entities)
            avg_degree = total_degree / len(self._entities)
        return {
            "total_entities": self.entity_count,
            "total_relations": self.relation_count,
            "type_distribution": type_dist,
            "avg_degree": round(avg_degree, 2),
        }

    def reset(self):
        self._entities.clear()
        self._name_index.clear()
        self._relations.clear()
        self._adjacency.clear()
        self._type_index.clear()
        logger.info("knowledge_store_reset")


# ═══════════════════════════════════════════════════════════════════
# VARLIK ÇIKARICI
# ═══════════════════════════════════════════════════════════════════

class EntityExtractor:
    """Metinden varlık çıkarımı — LLM-destekli."""

    @staticmethod
    def build_extraction_prompt(
        text: str,
        department: str,
    ) -> Tuple[str, str]:
        types = ", ".join(ENTITY_TYPES)
        system_prompt = (
            "Sen bir Doğal Dil İşleme (NLP) Uzmanısın. "
            "Verilen metinden varlıkları ve ilişkileri çıkarıyorsun.\n\n"
            f"Varlık Tipleri: {types}\n\n"
            "VARLIKLAR:\n"
            "Her varlık için:\n"
            "VARLIK: [ad] | Tip: [tip] | Açıklama: [kısa açıklama]\n\n"
            "İLİŞKİLER:\n"
            "Her ilişki için:\n"
            "İLİŞKİ: [kaynak] → [ilişki tipi] → [hedef] | Güven: [0.X]\n\n"
            f"Departman: {department}\n\n"
            "Kurallar:\n"
            "- Genel kavramları değil, spesifik varlıkları çıkar\n"
            "- İlişki tiplerini: sahip, bağlı, üretir, kullanır, etkiler, bağımlı, ölçer, "
            "sorumlu, tedarik_eder, müşterisi, alt_kavram, ilişkili, karşıt, sebep_olur, benzer\n"
            "- Tahmini ilişkiler için güven puanı düşük tut (< 0.5)"
        )
        user_prompt = f"Metin:\n{text[:2000]}"
        return system_prompt, user_prompt

    @staticmethod
    def parse_extraction_response(raw_text: str) -> Tuple[List[Dict], List[Dict]]:
        """Varlık+ilişki çıkarım yanıtını parse et."""
        import re
        entities: List[Dict] = []
        relations: List[Dict] = []

        for line in raw_text.strip().split("\n"):
            clean = line.strip()
            if not clean:
                continue

            ent_match = re.match(r"(?:VARLIK|ENTITY)\s*[:.]\s*(.*)", clean, re.IGNORECASE)
            if ent_match:
                parts = ent_match.group(1).split("|")
                name = parts[0].strip()
                etype = "Kavram"
                desc = ""
                if len(parts) > 1:
                    tp = parts[1].split(":", 1)
                    if len(tp) > 1:
                        etype = tp[1].strip()
                if len(parts) > 2:
                    dp = parts[2].split(":", 1)
                    if len(dp) > 1:
                        desc = dp[1].strip()
                if name:
                    entities.append({"name": name, "type": etype, "description": desc})
                continue

            rel_match = re.match(r"(?:İLİŞKİ|RELATION)\s*[:.]\s*(.*)", clean, re.IGNORECASE)
            if rel_match:
                text = rel_match.group(1)
                arrow = re.match(r"(.+?)\s*→\s*(.+?)\s*→\s*(.+?)(?:\s*\|\s*(.*))?$", text)
                if arrow:
                    source = arrow.group(1).strip()
                    rel_type = arrow.group(2).strip()
                    target = arrow.group(3).strip()
                    conf = 0.8
                    if arrow.group(4):
                        conf_match = re.search(r"(\d+\.?\d*)", arrow.group(4))
                        if conf_match:
                            conf = min(float(conf_match.group(1)), 1.0)
                    relations.append({
                        "source": source,
                        "target": target,
                        "type": rel_type,
                        "confidence": conf,
                    })

        return entities, relations


# ═══════════════════════════════════════════════════════════════════
# GRAF SORGU MOTORU
# ═══════════════════════════════════════════════════════════════════

class GraphQueryEngine:
    """Graf traversal ve sorgu."""

    def __init__(self, store: KnowledgeStore):
        self.store = store

    def get_neighborhood(
        self, entity_id: str, depth: int = 1, max_nodes: int = 30
    ) -> Tuple[List[Entity], List[Relation]]:
        """Bir düğümün komşuluk alt grafını döndür."""
        if depth > MAX_QUERY_DEPTH:
            depth = MAX_QUERY_DEPTH

        visited_entities: Set[str] = set()
        visited_relations: Set[str] = set()
        queue: deque = deque([(entity_id, 0)])

        while queue and len(visited_entities) < max_nodes:
            current_id, current_depth = queue.popleft()
            if current_id in visited_entities:
                continue
            visited_entities.add(current_id)

            if current_depth >= depth:
                continue

            for rel in self.store.get_relations_for(current_id):
                visited_relations.add(rel.relation_id)
                other = rel.target_id if rel.source_id == current_id else rel.source_id
                if other not in visited_entities:
                    queue.append((other, current_depth + 1))

        entities = [self.store.get_entity(eid) for eid in visited_entities]
        entities = [e for e in entities if e is not None]
        relations = [self.store._relations.get(rid) for rid in visited_relations]
        relations = [r for r in relations if r is not None]
        return entities, relations

    def find_path(
        self, start_id: str, end_id: str, max_depth: int = MAX_QUERY_DEPTH
    ) -> List[List[str]]:
        """İki düğüm arasındaki yolları bul (BFS)."""
        if start_id == end_id:
            return [[start_id]]

        paths: List[List[str]] = []
        queue: deque = deque([(start_id, [start_id])])
        visited: Set[str] = set()

        while queue and len(paths) < 5:
            current_id, path = queue.popleft()
            if len(path) > max_depth + 1:
                continue

            for rel in self.store.get_relations_for(current_id):
                other = rel.target_id if rel.source_id == current_id else rel.source_id
                if other == end_id:
                    paths.append(path + [end_id])
                    continue
                if other not in visited and other not in path:
                    visited.add(other)
                    queue.append((other, path + [other]))

        return paths

    def get_most_connected(self, limit: int = 10) -> List[Tuple[Entity, int]]:
        """En çok bağlantıya sahip düğümler."""
        degree_list: List[Tuple[str, int]] = [
            (eid, len(self.store._adjacency.get(eid, set())))
            for eid in self.store._entities
        ]
        degree_list.sort(key=lambda x: x[1], reverse=True)
        result = []
        for eid, degree in degree_list[:limit]:
            e = self.store.get_entity(eid)
            if e:
                result.append((e, degree))
        return result

    def get_hub_entities(self, min_degree: int = 3) -> List[Entity]:
        """Hub düğümleri (yüksek dereceli)."""
        hubs = []
        for eid in self.store._entities:
            degree = len(self.store._adjacency.get(eid, set()))
            if degree >= min_degree:
                e = self.store.get_entity(eid)
                if e:
                    hubs.append(e)
        return hubs


# ═══════════════════════════════════════════════════════════════════
# SEMANTİK KÜMELEYICI
# ═══════════════════════════════════════════════════════════════════

class SemanticClusterer:
    """Bilgi grafiğini tematik kümelere ayır."""

    def __init__(self, store: KnowledgeStore):
        self.store = store

    def cluster_by_connectivity(self) -> List[GraphCluster]:
        """Connected components tabanlı kümeleme."""
        visited: Set[str] = set()
        clusters: List[GraphCluster] = []

        for eid in self.store._entities:
            if eid in visited:
                continue
            component: List[str] = []
            queue: deque = deque([eid])
            while queue:
                current = queue.popleft()
                if current in visited:
                    continue
                visited.add(current)
                component.append(current)
                for rel in self.store.get_relations_for(current):
                    other = rel.target_id if rel.source_id == current else rel.source_id
                    if other not in visited:
                        queue.append(other)

            if len(component) >= 2:
                central = max(
                    component,
                    key=lambda x: len(self.store._adjacency.get(x, set()))
                )
                central_entity = self.store.get_entity(central)
                cluster = GraphCluster(
                    theme=central_entity.name if central_entity else "Unknown",
                    entity_ids=component[:MAX_CLUSTER_SIZE],
                    central_entity_id=central,
                    cohesion_score=self._compute_cohesion(component),
                )
                clusters.append(cluster)

        clusters.sort(key=lambda c: len(c.entity_ids), reverse=True)
        return clusters

    def cluster_by_type(self) -> List[GraphCluster]:
        """Varlık tipine göre kümeleme."""
        clusters: List[GraphCluster] = []
        for etype, eids in self.store._type_index.items():
            if len(eids) >= 2:
                eid_list = list(eids)[:MAX_CLUSTER_SIZE]
                central = max(
                    eid_list,
                    key=lambda x: len(self.store._adjacency.get(x, set()))
                )
                clusters.append(GraphCluster(
                    theme=f"Tip: {etype}",
                    entity_ids=eid_list,
                    central_entity_id=central,
                    cohesion_score=len(eid_list) / max(self.store.entity_count, 1),
                ))
        return clusters

    def _compute_cohesion(self, entity_ids: List[str]) -> float:
        if len(entity_ids) < 2:
            return 0.0
        internal_edges = 0
        entity_set = set(entity_ids)
        for eid in entity_ids:
            for rel in self.store.get_relations_for(eid):
                other = rel.target_id if rel.source_id == eid else rel.source_id
                if other in entity_set:
                    internal_edges += 1
        max_possible = len(entity_ids) * (len(entity_ids) - 1)
        if max_possible == 0:
            return 0.0
        return round(internal_edges / max_possible, 3)


# ═══════════════════════════════════════════════════════════════════
# BAĞLAM ZENGİNLEŞTİRİCİ
# ═══════════════════════════════════════════════════════════════════

class ContextEnricher:
    """Sorgu bağlamını graf bilgisiyle zenginleştir."""

    def __init__(self, store: KnowledgeStore, query_engine: GraphQueryEngine):
        self.store = store
        self.query_engine = query_engine

    def enrich_context(self, question: str, department: str = "") -> str:
        """Soruya graf bağlamı ekle."""
        if self.store.entity_count == 0:
            return ""

        words = question.lower().split()
        relevant_entities: List[Entity] = []

        for word in words:
            if len(word) < 3:
                continue
            matches = self.store.search_entities(word, limit=3)
            relevant_entities.extend(matches)

        seen_ids: Set[str] = set()
        unique: List[Entity] = []
        for e in relevant_entities:
            if e.entity_id not in seen_ids:
                seen_ids.add(e.entity_id)
                unique.append(e)

        if not unique:
            return ""

        context_parts = ["[Bilgi Grafiği Bağlamı]"]
        for entity in unique[:5]:
            rels = self.store.get_relations_for(entity.entity_id)
            rel_texts = []
            for rel in rels[:3]:
                source = self.store.get_entity(rel.source_id)
                target = self.store.get_entity(rel.target_id)
                if source and target:
                    rel_texts.append(
                        f"  {source.name} →({rel.relation_type})→ {target.name}"
                    )
            entity_text = f"• {entity.name} ({entity.entity_type})"
            if entity.description:
                entity_text += f": {entity.description[:60]}"
            if rel_texts:
                entity_text += "\n" + "\n".join(rel_texts)
            context_parts.append(entity_text)

        return "\n".join(context_parts)


# ═══════════════════════════════════════════════════════════════════
# GRAF TAKİPÇİSİ
# ═══════════════════════════════════════════════════════════════════

class GraphTracker:
    """Graf operasyonları ve sorgu takibi."""

    def __init__(self):
        self._queries: List[GraphQueryResult] = []
        self._operations: int = 0

    def record_query(self, result: GraphQueryResult):
        self._queries.append(result)
        if len(self._queries) > MAX_GRAPH_HISTORY:
            self._queries = self._queries[-MAX_GRAPH_HISTORY:]
        self._operations += 1

    def get_recent_queries(self, n: int = 20) -> List[dict]:
        return [q.to_dict() for q in self._queries[-n:]]

    def get_statistics(self) -> dict:
        total = len(self._queries)
        return {
            "total_queries": total,
            "total_operations": self._operations,
            "avg_entities_per_query": round(
                sum(len(q.entities_found) for q in self._queries) / max(total, 1), 1
            ),
            "avg_relations_per_query": round(
                sum(len(q.relations_found) for q in self._queries) / max(total, 1), 1
            ),
        }

    def reset(self):
        self._queries.clear()
        self._operations = 0


# ═══════════════════════════════════════════════════════════════════
# ANA ORKESTRATÖR — KnowledgeGraphEngine
# ═══════════════════════════════════════════════════════════════════

class KnowledgeGraphEngine:
    """Knowledge Graph orkestratörü.

    Kullanım:
        engine = knowledge_graph
        # Varlık ekleme
        entity = engine.add_entity("Üretim Planlaması", "Süreç", dept="Üretim")
        # İlişki ekleme
        engine.add_relation(entity.entity_id, other_id, "kullanır")
        # Sorgu
        result = engine.query_neighborhood(entity.entity_id)
        # Bağlam zenginleştirme
        context = engine.enrich(question, dept)
    """

    def __init__(self):
        self.store = KnowledgeStore()
        self.query_engine = GraphQueryEngine(self.store)
        self.clusterer = SemanticClusterer(self.store)
        self.enricher = ContextEnricher(self.store, self.query_engine)
        self.extractor = EntityExtractor()
        self.tracker = GraphTracker()
        self._enabled: bool = True
        self._auto_extract: bool = True
        self._started_at: str = _utcnow_str()

    def should_query(
        self,
        question: str,
        mode: str,
        intent: str,
        force: bool = False,
    ) -> Tuple[bool, str]:
        if not self._enabled and not force:
            return False, "kg_disabled"
        return should_trigger_knowledge_graph(question, mode, intent, force)

    # ─── Varlık & İlişki CRUD (convenience) ───

    def add_entity(
        self,
        name: str,
        entity_type: str = "Kavram",
        description: str = "",
        department: str = "",
        properties: Optional[Dict] = None,
    ) -> Entity:
        entity = Entity(
            name=name,
            entity_type=entity_type,
            description=description,
            department=department,
            properties=properties or {},
        )
        return self.store.add_entity(entity)

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str = "ilişkili",
        description: str = "",
        confidence: float = 0.8,
        bidirectional: bool = False,
    ) -> Optional[Relation]:
        if not self.store.get_entity(source_id) or not self.store.get_entity(target_id):
            return None
        rel = Relation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            description=description,
            confidence=confidence,
            bidirectional=bidirectional,
        )
        return self.store.add_relation(rel)

    def ingest_extracted(
        self,
        raw_entities: List[Dict],
        raw_relations: List[Dict],
        department: str = "",
    ) -> dict:
        """EntityExtractor çıktısını grafa yükle."""
        added_entities = 0
        added_relations = 0
        entity_map: Dict[str, str] = {}

        for ed in raw_entities:
            e = self.add_entity(
                name=ed.get("name", "Unknown"),
                entity_type=ed.get("type", "Kavram"),
                description=ed.get("description", ""),
                department=department,
            )
            entity_map[ed.get("name", "").lower()] = e.entity_id
            added_entities += 1

        for rd in raw_relations:
            src_name = rd.get("source", "").lower()
            tgt_name = rd.get("target", "").lower()
            src_id = entity_map.get(src_name)
            tgt_id = entity_map.get(tgt_name)
            if not src_id:
                src_entity = self.store.find_entity_by_name(rd.get("source", ""))
                src_id = src_entity.entity_id if src_entity else None
            if not tgt_id:
                tgt_entity = self.store.find_entity_by_name(rd.get("target", ""))
                tgt_id = tgt_entity.entity_id if tgt_entity else None
            if src_id and tgt_id:
                self.add_relation(
                    source_id=src_id,
                    target_id=tgt_id,
                    relation_type=rd.get("type", "ilişkili"),
                    confidence=rd.get("confidence", 0.8),
                )
                added_relations += 1

        return {"added_entities": added_entities, "added_relations": added_relations}

    # ─── LLM Prompt Builders ───

    def build_extraction_prompt(
        self, text: str, department: str
    ) -> Tuple[str, str]:
        return self.extractor.build_extraction_prompt(text, department)

    def parse_extraction_response(
        self, raw_text: str
    ) -> Tuple[List[Dict], List[Dict]]:
        return self.extractor.parse_extraction_response(raw_text)

    # ─── Sorgular ───

    def query_neighborhood(
        self,
        entity_name: str,
        depth: int = 2,
        max_nodes: int = 30,
    ) -> GraphQueryResult:
        t0 = time.time()
        entity = self.store.find_entity_by_name(entity_name)
        if not entity:
            return GraphQueryResult(
                query_text=f"neighborhood:{entity_name}",
                total_time_ms=(time.time() - t0) * 1000,
            )
        entities, relations = self.query_engine.get_neighborhood(
            entity.entity_id, depth, max_nodes
        )
        result = GraphQueryResult(
            query_text=f"neighborhood:{entity_name}",
            entities_found=entities,
            relations_found=relations,
            confidence_adjustment=min(len(entities) * 0.5, 5.0),
            total_time_ms=(time.time() - t0) * 1000,
        )
        self.tracker.record_query(result)
        return result

    def query_path(
        self, start_name: str, end_name: str
    ) -> GraphQueryResult:
        t0 = time.time()
        start = self.store.find_entity_by_name(start_name)
        end = self.store.find_entity_by_name(end_name)
        if not start or not end:
            return GraphQueryResult(
                query_text=f"path:{start_name}→{end_name}",
                total_time_ms=(time.time() - t0) * 1000,
            )
        paths = self.query_engine.find_path(start.entity_id, end.entity_id)
        named_paths = []
        for path in paths:
            named = []
            for eid in path:
                e = self.store.get_entity(eid)
                named.append(e.name if e else eid)
            named_paths.append(named)

        result = GraphQueryResult(
            query_text=f"path:{start_name}→{end_name}",
            paths=named_paths,
            confidence_adjustment=min(len(paths) * 1.0, 3.0),
            total_time_ms=(time.time() - t0) * 1000,
        )
        self.tracker.record_query(result)
        return result

    def query_clusters(self) -> GraphQueryResult:
        t0 = time.time()
        clusters = self.clusterer.cluster_by_connectivity()
        result = GraphQueryResult(
            query_text="clusters",
            clusters=clusters,
            total_time_ms=(time.time() - t0) * 1000,
        )
        self.tracker.record_query(result)
        return result

    # ─── Bağlam Zenginleştirme ───

    def enrich(self, question: str, department: str = "") -> str:
        return self.enricher.enrich_context(question, department)

    # ─── Yönetim ───

    def get_dashboard(self) -> dict:
        return {
            "available": True,
            "enabled": self._enabled,
            "auto_extract": self._auto_extract,
            "started_at": self._started_at,
            "graph_stats": self.store.get_stats(),
            "query_stats": self.tracker.get_statistics(),
            "recent_queries": self.tracker.get_recent_queries(10),
            "hub_entities": [
                {"name": e.name, "type": e.entity_type, "degree": d}
                for e, d in self.query_engine.get_most_connected(10)
            ],
            "clusters": [c.to_dict() for c in self.clusterer.cluster_by_connectivity()[:5]],
            "settings": {
                "max_entities": MAX_ENTITIES,
                "max_relations": MAX_RELATIONS,
                "max_query_depth": MAX_QUERY_DEPTH,
                "entity_types": ENTITY_TYPES,
                "relation_types": RELATION_TYPES,
            },
        }

    def set_enabled(self, enabled: bool) -> dict:
        old = self._enabled
        self._enabled = enabled
        logger.info("knowledge_graph_toggled", old=old, new=enabled)
        return {"enabled": enabled, "previous": old}

    def set_auto_extract(self, enabled: bool) -> dict:
        old = self._auto_extract
        self._auto_extract = enabled
        return {"auto_extract": enabled, "previous": old}

    def reset(self):
        self.store.reset()
        self.tracker.reset()
        self._started_at = _utcnow_str()
        logger.info("knowledge_graph_reset")


# ═══════════════════════════════════════════════════════════════════
# GLOBAL SINGLETON
# ═══════════════════════════════════════════════════════════════════

knowledge_graph: KnowledgeGraphEngine = KnowledgeGraphEngine()


def check_kg_trigger(
    question: str, mode: str, intent: str, force: bool = False,
) -> Tuple[bool, str]:
    return knowledge_graph.should_query(question, mode, intent, force)


def get_kg_dashboard() -> dict:
    return knowledge_graph.get_dashboard()
