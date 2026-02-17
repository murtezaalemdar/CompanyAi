"""RAG (Retrieval Augmented Generation) Modülü

Şirket dokümanlarını vektör veritabanında saklar ve sorulara bağlamsal cevap verir.
"""

import os
import time
from pathlib import Path
from typing import List, Optional
from collections import deque
import structlog

logger = structlog.get_logger()

# ChromaDB ve Embedding modeli
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logger.warning("chromadb_not_installed", message="RAG özellikleri devre dışı")

try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logger.warning("sentence_transformers_not_installed")

# Cross-Encoder Re-Ranking (v4.3.0)
try:
    from sentence_transformers import CrossEncoder
    _cross_encoder = None
    CROSS_ENCODER_AVAILABLE = True
except ImportError:
    CROSS_ENCODER_AVAILABLE = False
    _cross_encoder = None

CROSS_ENCODER_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"  # v4.4.0: Türkçe/çok dilli model

# ── Retrieval Metrikleri (v4.4.0) ──
# Son N aramanın istatistiklerini circular buffer'da sakla
_RETRIEVAL_METRICS_BUFFER = deque(maxlen=200)


def log_retrieval_metrics(query: str, results: list, latency_ms: float):
    """Arama sonuçlarının kalite metriklerini logla ve sakla."""
    if not results:
        _RETRIEVAL_METRICS_BUFFER.append({
            "ts": time.time(), "query": query[:80], "n": 0,
            "latency_ms": round(latency_ms, 1), "avg_score": 0,
            "top_score": 0, "min_score": 0, "zero_result": True,
        })
        return
    
    scores = [r.get("relevance", 0) for r in results]
    avg_score = sum(scores) / len(scores) if scores else 0
    top_score = max(scores) if scores else 0
    min_score = min(scores) if scores else 0
    
    # MRR (Mean Reciprocal Rank) — ilk yüksek skorlu sonucun sırası
    mrr = 0
    for i, s in enumerate(scores, 1):
        if s > 0.3:
            mrr = 1.0 / i
            break
    
    entry = {
        "ts": time.time(),
        "query": query[:80],
        "n": len(results),
        "latency_ms": round(latency_ms, 1),
        "avg_score": round(avg_score, 4),
        "top_score": round(top_score, 4),
        "min_score": round(min_score, 4),
        "mrr": round(mrr, 4),
        "zero_result": False,
    }
    _RETRIEVAL_METRICS_BUFFER.append(entry)
    
    logger.info("retrieval_metrics",
                query=query[:50], n=len(results),
                latency_ms=round(latency_ms, 1),
                avg_score=round(avg_score, 3),
                top_score=round(top_score, 3),
                mrr=round(mrr, 3))


def get_retrieval_metrics_summary() -> dict:
    """Son aramaların özet metriklerini döndür."""
    if not _RETRIEVAL_METRICS_BUFFER:
        return {"total_searches": 0}
    
    entries = list(_RETRIEVAL_METRICS_BUFFER)
    n = len(entries)
    
    avg_latency = sum(e["latency_ms"] for e in entries) / n
    avg_score = sum(e["avg_score"] for e in entries) / n
    avg_mrr = sum(e["mrr"] for e in entries) / n
    zero_results = sum(1 for e in entries if e["zero_result"])
    
    return {
        "total_searches": n,
        "avg_latency_ms": round(avg_latency, 1),
        "avg_relevance_score": round(avg_score, 4),
        "avg_mrr": round(avg_mrr, 4),
        "zero_result_rate": round(zero_results / n * 100, 1),
        "last_10": entries[-10:],
    }


def get_cross_encoder():
    """Cross-encoder modelini lazy-load et (singleton)"""
    global _cross_encoder
    if not CROSS_ENCODER_AVAILABLE:
        return None
    if _cross_encoder is None:
        try:
            _cross_encoder = CrossEncoder(CROSS_ENCODER_MODEL)
            logger.info("cross_encoder_loaded", model=CROSS_ENCODER_MODEL)
        except Exception as e:
            logger.warning("cross_encoder_load_failed", error=str(e))
            return None
    return _cross_encoder


def _cross_encoder_rerank(query: str, documents: list, top_k: int = 5) -> list:
    """Cross-encoder ile adayları yeniden skorla.
    
    Bi-encoder (embedding) hızlıdır ama yaklaşıktır.
    Cross-encoder (query, doc) çiftini birlikte değerlendirir → daha kesin sıralama.
    
    Args:
        query: Kullanıcı sorusu
        documents: Aday doküman listesi (her biri 'content' ve 'relevance' içermeli)
        top_k: Döndürülecek üst sonuç sayısı
    
    Returns:
        Cross-encoder skoru ile yeniden sıralanmış doküman listesi
    """
    encoder = get_cross_encoder()
    if not encoder or not documents:
        return documents[:top_k]
    
    try:
        # Cross-encoder için (query, document) çiftleri oluştur
        pairs = [(query, doc["content"]) for doc in documents]
        
        # Cross-encoder skorları (logits → float)
        ce_scores = encoder.predict(pairs)
        
        # Skorları normalize et (0-1 arası)
        import numpy as np
        ce_min, ce_max = float(np.min(ce_scores)), float(np.max(ce_scores))
        if ce_max > ce_min:
            ce_normalized = [(s - ce_min) / (ce_max - ce_min) for s in ce_scores]
        else:
            ce_normalized = [0.5] * len(ce_scores)
        
        # Final skor: %40 hybrid (bi-encoder + keyword) + %60 cross-encoder
        for i, doc in enumerate(documents):
            original_score = doc.get("relevance", 0)
            ce_score = ce_normalized[i]
            doc["cross_encoder_score"] = round(float(ce_scores[i]), 4)
            doc["relevance"] = round(0.4 * original_score + 0.6 * ce_score, 4)
        
        # Yeniden sırala
        documents.sort(key=lambda x: x["relevance"], reverse=True)
        logger.info("cross_encoder_reranked", candidates=len(documents), top_k=top_k)
        return documents[:top_k]
        
    except Exception as e:
        logger.warning("cross_encoder_rerank_failed", error=str(e))
        return documents[:top_k]


# Vektör veritabanı yolu (env'den okunabilir)
import os
CHROMA_PERSIST_DIR = os.environ.get("CHROMA_PERSIST_DIR", "/opt/companyai/data/chromadb")
COLLECTION_NAME = "company_documents"

# v4.4.0: Koleksiyon ayrımı — 3 farklı amaç için ayrı koleksiyonlar
COLLECTION_LEARNED = "learned_knowledge"   # Konuşmalardan öğrenilen bilgi
COLLECTION_WEB = "web_cache"               # Web aramalarından önbellek

# Embedding modeli (Türkçe destekli, küçük ve hızlı)
# Embedding modeli (Türkçe destekli, PRO seviye)
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

# Singleton instances
_chroma_client = None
_embedding_model = None
_collection = None
_collection_learned = None
_collection_web = None


def get_embedding_model():
    """Embedding modelini yükler (lazy loading)"""
    global _embedding_model
    if _embedding_model is None and EMBEDDINGS_AVAILABLE:
        logger.info("loading_embedding_model", model=EMBEDDING_MODEL)
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        logger.info("embedding_model_loaded")
    return _embedding_model


def get_chroma_client():
    """ChromaDB client'ı döner (lazy loading)"""
    global _chroma_client
    if _chroma_client is None and CHROMADB_AVAILABLE:
        # Dizin yoksa oluştur
        Path(CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
        
        _chroma_client = chromadb.PersistentClient(
            path=CHROMA_PERSIST_DIR
        )
        logger.info("chromadb_initialized", path=CHROMA_PERSIST_DIR)
    return _chroma_client


def get_collection():
    """Doküman koleksiyonunu döner"""
    global _collection
    if _collection is None:
        client = get_chroma_client()
        if client:
            _collection = client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"description": "Şirket dokümanları"}
            )
            logger.info("collection_ready", name=COLLECTION_NAME)
    return _collection


def get_learned_collection():
    """Öğrenilen bilgi koleksiyonunu döner (v4.4.0)"""
    global _collection_learned
    if _collection_learned is None:
        client = get_chroma_client()
        if client:
            _collection_learned = client.get_or_create_collection(
                name=COLLECTION_LEARNED,
                metadata={"description": "Konuşmalardan öğrenilen bilgi"}
            )
            logger.info("collection_ready", name=COLLECTION_LEARNED)
    return _collection_learned


def get_web_collection():
    """Web önbellek koleksiyonunu döner (v4.4.0)"""
    global _collection_web
    if _collection_web is None:
        client = get_chroma_client()
        if client:
            _collection_web = client.get_or_create_collection(
                name=COLLECTION_WEB,
                metadata={"description": "Web araması önbelleği"}
            )
            logger.info("collection_ready", name=COLLECTION_WEB)
    return _collection_web


def add_document(
    content: str,
    source: str,
    doc_type: str = "text",
    metadata: dict = None
) -> bool:
    """
    Dokümanı vektör veritabanına ekler.
    
    Args:
        content: Doküman içeriği
        source: Kaynak dosya adı
        doc_type: Doküman tipi (text, pdf, docx)
        metadata: Ek metadata
    
    Returns:
        Başarılı ise True
    """
    if not CHROMADB_AVAILABLE or not EMBEDDINGS_AVAILABLE:
        logger.error("rag_not_available")
        return False
    
    try:
        # v4.4.0: Koleksiyon ayrımı — öğrenilen bilgi ve web cache ayrı koleksiyona
        _is_learned_type = doc_type in ("chat_learned", "qa_learned", "voice_learned", "file_context")
        _is_web_type = doc_type in ("web_cache", "web_search")
        
        if _is_learned_type:
            collection = get_learned_collection()
        elif _is_web_type:
            collection = get_web_collection()
        else:
            collection = get_collection()
        
        model = get_embedding_model()
        
        if not collection or not model:
            return False
        
        # Timestamp — knowledge decay için
        from datetime import datetime
        created_at = datetime.utcnow().isoformat()
        
        # Dokümanı parçalara böl (chunking)
        # Daha büyük chunk = daha anlamlı bağlam, daha iyi RAG yanıtları
        chunks = chunk_text(content, chunk_size=2000, overlap=300)  # v4.4.0: Daha büyük chunk = daha iyi bağlam
        
        added_count = 0
        for i, chunk in enumerate(chunks):
            doc_id = f"{source}_{i}"
            embedding = model.encode(chunk).tolist()
            
            # ── DUPLİKASYON KORUMASI ──
            # chat_learned / qa_learned / voice_learned tiplerinde
            # zaten çok benzer içerik varsa tekrar kaydetme
            if _is_learned_type:
                try:
                    existing = collection.query(
                        query_embeddings=[embedding],
                        n_results=1,
                    )
                    if (existing and existing['distances'] and existing['distances'][0]
                            and existing['distances'][0][0] < 0.15):
                        logger.debug("skip_duplicate", source=source, chunk=i,
                                    distance=existing['distances'][0][0])
                        continue  # Çok benzer kayıt zaten var → atla
                except Exception:
                    pass  # Duplikasyon kontrolü başarısızsa kaydetmeye devam et
            
            doc_metadata = {
                "source": source,
                "type": doc_type,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "created_at": created_at,
                **(metadata or {})
            }
            
            collection.add(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[doc_metadata]
            )
            added_count += 1
        
        if added_count > 0:
            logger.info("document_added", source=source, chunks=added_count,
                        skipped=len(chunks) - added_count)
        elif chunks:
            logger.info("document_all_duplicates", source=source, chunks=len(chunks))
        return added_count > 0
        
    except Exception as e:
        logger.error("add_document_error", error=str(e))
        return False


def search_documents(
    query: str,
    n_results: int = 5,
    department: str = None,
    doc_type: str = None,
    date_from: str = None,
    date_to: str = None,
) -> List[dict]:
    """
    Sorguya en uygun dokümanları arar.
    
    Args:
        query: Arama sorgusu
        n_results: Döndürülecek sonuç sayısı
        department: Departman filtresi (Opsiyonel)
        doc_type: Doküman tipi filtresi — "pdf", "excel", "learned", vb. (v4.4.0)
        date_from: Başlangıç tarihi filtresi — "2025-01-01" formatı (v4.4.0)
        date_to: Bitiş tarihi filtresi — "2025-06-30" formatı (v4.4.0)
    
    Returns:
        İlgili doküman parçaları listesi
    """
    if not CHROMADB_AVAILABLE or not EMBEDDINGS_AVAILABLE:
        return []
    
    try:
        collection = get_collection()
        model = get_embedding_model()
        
        if not collection or not model:
            return []
        
        _search_start = time.time()
        
        # Sorguyu vektöre çevir
        query_embedding = model.encode(query).tolist()
        
        # Filtreleme (v4.4.0: genişletilmiş metadata filtreleri)
        where_filter = {}
        where_conditions = []
        
        if department and department != "Genel":
            where_conditions.append({"department": department})
        
        if doc_type:
            where_conditions.append({"type": doc_type})
        
        if date_from:
            where_conditions.append({"created_at": {"$gte": date_from}})
        
        if date_to:
            where_conditions.append({"created_at": {"$lte": date_to}})
        
        if len(where_conditions) == 1:
            where_filter = where_conditions[0]
        elif len(where_conditions) > 1:
            where_filter = {"$and": where_conditions}

        # Daha fazla aday getir, sonra re-rank et
        fetch_n = min(n_results * 3, 30)
        
        # Ara — önce department filtresi ile, sonuç yoksa filtresiz dene
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=fetch_n,
            where=where_filter if where_filter else None
        )
        
        # Department filtresi ile sonuç gelmezse, filtresiz tekrar dene
        if where_filter and (not results or not results['documents'] or not results['documents'][0]):
            logger.info("rag_retry_without_dept_filter", department=department)
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=fetch_n
            )
        
        # Sonuçları formatla + hybrid skor hesapla
        documents = []
        if results and results['documents']:
            query_terms = set(query.lower().split())
            
            for i, doc in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                distance = results['distances'][0][i] if results['distances'] else 0
                
                # Semantic skor (ChromaDB L2 distance → similarity)
                # L2 distance 768-dim embeddinglerden tipik 1.0-2.5 aralığında
                semantic_score = max(0, 1 - distance / 2.0)
                
                # Keyword skor (BM25-like basit)
                doc_lower = doc.lower()
                keyword_hits = sum(1 for t in query_terms if t in doc_lower)
                keyword_score = keyword_hits / max(len(query_terms), 1)
                
                # Hybrid skor: %70 semantic + %30 keyword
                hybrid_score = 0.7 * semantic_score + 0.3 * keyword_score
                
                # Otomatik öğrenilmiş içerik → gerçek dokümanları önceliklendir
                source = metadata.get("source", "")
                doc_type = metadata.get("type", "")
                is_web_learned = "web_search" in source or doc_type == "web_learned"
                is_chat_learned = doc_type in ("chat_learned", "qa_learned", "voice_learned")
                if is_web_learned:
                    hybrid_score *= 0.5   # Web cache %50 ceza
                elif is_chat_learned:
                    hybrid_score *= 0.70  # Chat öğrenmeleri gerçek dokümanlardan sonra
                
                # Knowledge Decay — eski bilgilerin skoru düşsün
                created_at_str = metadata.get("created_at", "")
                if created_at_str:
                    try:
                        from datetime import datetime
                        created_dt = datetime.fromisoformat(created_at_str)
                        age_days = (datetime.utcnow() - created_dt).days
                        # Yılda %20 azalma, minimum %50 (çok eski bile tamamen yok olmaz)
                        decay = max(0.50, 1.0 - (age_days / 365) * 0.20)
                        hybrid_score *= decay
                    except (ValueError, TypeError):
                        pass
                
                documents.append({
                    "content": doc,
                    "source": metadata.get("source", "Bilinmeyen"),
                    "type": metadata.get("type", "text"),
                    "department": metadata.get("department", "Genel"),
                    "relevance": round(hybrid_score, 4),
                    "distance": distance,
                    "semantic_score": round(semantic_score, 4),
                    "keyword_score": round(keyword_score, 4),
                })
        
        # ── v5.10.6: Keyword-aware tamamlayıcı arama ──
        # Vector search'in döndüremediği ama sorgu kelimelerini
        # birebir içeren dokümanları yakala (isim, varlık, kısa girişler).
        _existing_contents = {d["content"][:100] for d in documents}
        _kw_words = [w for w in query.lower().split() if len(w) >= 2]
        if len(_kw_words) >= 2 and collection:
            _kw_phrases = []
            for _ki in range(min(len(_kw_words) - 1, 3)):
                _p = f"{_kw_words[_ki]} {_kw_words[_ki + 1]}"
                if len(_p) >= 5:
                    _kw_phrases.append(_p)

            for _phrase in _kw_phrases:
                try:
                    kw_results = collection.query(
                        query_embeddings=[query_embedding],
                        where_document={"$contains": _phrase},
                        n_results=3,
                    )
                    if kw_results and kw_results['documents'] and kw_results['documents'][0]:
                        for _j, _kw_doc in enumerate(kw_results['documents'][0]):
                            if _kw_doc[:100] in _existing_contents:
                                continue
                            _existing_contents.add(_kw_doc[:100])

                            _kw_meta = kw_results['metadatas'][0][_j] if kw_results.get('metadatas') else {}
                            _kw_dist = kw_results['distances'][0][_j] if kw_results.get('distances') else 999

                            _kw_sem = max(0, 1 - _kw_dist / 2.0)
                            _kw_doc_lower = _kw_doc.lower()
                            _kw_hits = sum(1 for t in query_terms if t in _kw_doc_lower)
                            _kw_kw_score = _kw_hits / max(len(query_terms), 1)
                            _kw_hybrid = 0.7 * _kw_sem + 0.3 * _kw_kw_score

                            # Keyword tam eşleşme bonusu (%15)
                            _kw_hybrid *= 1.15

                            # Web/chat cezaları
                            _kw_src = _kw_meta.get("source", "")
                            _kw_type = _kw_meta.get("type", "")
                            if "web_search" in _kw_src or _kw_type == "web_learned":
                                _kw_hybrid *= 0.5
                            elif _kw_type in ("chat_learned", "qa_learned", "voice_learned"):
                                _kw_hybrid *= 0.70

                            documents.append({
                                "content": _kw_doc,
                                "source": _kw_meta.get("source", "Bilinmeyen"),
                                "type": _kw_meta.get("type", "text"),
                                "department": _kw_meta.get("department", "Genel"),
                                "relevance": round(_kw_hybrid, 4),
                                "distance": _kw_dist,
                                "semantic_score": round(_kw_sem, 4),
                                "keyword_score": round(_kw_kw_score, 4),
                                "keyword_match": True,
                            })
                except Exception as _kw_err:
                    logger.debug("keyword_supplement_skip", phrase=_phrase, error=str(_kw_err))

        # Re-rank: önce hybrid skora göre sırala
        documents.sort(key=lambda x: x["relevance"], reverse=True)
        
        # v4.3.0: Cross-Encoder Re-Ranking — daha kesin sıralama
        if CROSS_ENCODER_AVAILABLE and len(documents) > 1:
            documents = _cross_encoder_rerank(query, documents, top_k=n_results)
        else:
            documents = documents[:n_results]
        
        # v4.4.0: Multi-collection arama — öğrenilen bilgiden de sonuç getir
        try:
            learned_coll = get_learned_collection()
            if learned_coll and learned_coll.count() > 0:
                learned_results = learned_coll.query(
                    query_embeddings=[query_embedding],
                    n_results=min(3, n_results),
                )
                if learned_results and learned_results['documents'] and learned_results['documents'][0]:
                    for i, doc in enumerate(learned_results['documents'][0]):
                        l_metadata = learned_results['metadatas'][0][i] if learned_results['metadatas'] else {}
                        l_distance = learned_results['distances'][0][i] if learned_results['distances'] else 999
                        l_semantic = max(0, 1 - l_distance / 2.0)
                        # Öğrenilen bilgi %80 ağırlık (dokümanlardan sonra)
                        l_score = l_semantic * 0.80
                        if l_score > 0.15:  # Minimum eşik
                            documents.append({
                                "content": doc,
                                "source": l_metadata.get("source", "Öğrenilmiş"),
                                "type": l_metadata.get("type", "learned"),
                                "department": l_metadata.get("department", "Genel"),
                                "relevance": round(l_score, 4),
                                "distance": l_distance,
                                "semantic_score": round(l_semantic, 4),
                                "keyword_score": 0,
                                "collection": "learned",
                            })
                    # Tekrar sırala — öğrenilen bilgi de dahil
                    documents.sort(key=lambda x: x["relevance"], reverse=True)
                    documents = documents[:n_results]
        except Exception as learned_err:
            logger.debug("learned_collection_search_skipped", error=str(learned_err))
        
        logger.info("search_completed", query=query[:50], results=len(documents),
                     hybrid_search=True,
                     cross_encoder=CROSS_ENCODER_AVAILABLE)
        
        # v4.4.0: Retrieval metrikleri logla
        _search_latency = (time.time() - _search_start) * 1000
        log_retrieval_metrics(query, documents, _search_latency)
        
        return documents
        
    except Exception as e:
        logger.error("search_error", error=str(e))
        return []


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
    """
    Metni akıllı parçalara böler — cümle sınırlarına saygı gösterir.
    
    Args:
        text: Bölünecek metin
        chunk_size: Hedef parça boyutu (karakter)
        overlap: Parçalar arası örtüşme
    
    Returns:
        Metin parçaları listesi
    """
    import re
    
    # Cümle sınırlarından böl
    sentences = re.split(r'(?<=[.!?。\n])\s+', text)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        # Eğer tek cümle bile chunk_size'ı aşıyorsa, kelime sınırından böl
        if len(sentence) > chunk_size:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            # Uzun cümleyi kelime sınırlarından böl
            words = sentence.split()
            sub_chunk = ""
            for word in words:
                if len(sub_chunk) + len(word) + 1 > chunk_size:
                    if sub_chunk:
                        chunks.append(sub_chunk.strip())
                    sub_chunk = word
                else:
                    sub_chunk = f"{sub_chunk} {word}" if sub_chunk else word
            if sub_chunk:
                current_chunk = sub_chunk
            continue
        
        # Chunk kapasitesi dolduysa yeni chunk başlat
        if len(current_chunk) + len(sentence) + 1 > chunk_size:
            if current_chunk:
                chunks.append(current_chunk.strip())
                # Overlap: son cümlenin bir kısmını sonraki chunk'a taşı
                overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else ""
                current_chunk = overlap_text + " " + sentence if overlap_text else sentence
            else:
                current_chunk = sentence
        else:
            current_chunk = f"{current_chunk} {sentence}" if current_chunk else sentence
    
    # Son kalan chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks if chunks else [text[:chunk_size]]


def agentic_search(query: str, n_results: int = 5, department: str = None) -> List[dict]:
    """Agentic RAG — Sorguyu alt sorulara böl, her birini ara, birleştir.
    
    Basit search_documents'tan farkı:
    - Karmaşık sorular alt parçalara ayrılır
    - Her parça bağımsız aranır
    - Sonuçlar birleştirilir ve tekrarlar elenir
    - Daha geniş bilgi tabanı kapsamı sağlanır
    
    Args:
        query: Kullanıcı sorusu
        n_results: Döndürülecek toplam sonuç sayısı
        department: Departman filtresi
    
    Returns:
        Birleştirilmiş ve sıralanmış doküman listesi
    """
    sub_queries = _decompose_query(query)
    
    if len(sub_queries) <= 1:
        # Basit sorgu — doğrudan klasik arama
        return search_documents(query, n_results=n_results, department=department)
    
    logger.info("agentic_rag_start", original=query[:80], sub_queries=len(sub_queries))
    
    # Her alt sorguyu ara
    all_docs = []
    seen_sources = set()
    
    for sq in sub_queries:
        docs = search_documents(sq, n_results=max(3, n_results // len(sub_queries) + 1),
                                department=department)
        for doc in docs:
            # Duplikasyon kontrolü — aynı source+chunk gelmesin
            doc_key = f"{doc.get('source', '')}:{doc.get('content', '')[:80]}"
            if doc_key not in seen_sources:
                seen_sources.add(doc_key)
                # Hangi alt sorgudan geldiğini kaydet
                doc["sub_query"] = sq
                all_docs.append(doc)
    
    # Reciprocal Rank Fusion — her dokümana birden fazla sorgudan geldiyse bonus
    source_hit_count = {}
    for doc in all_docs:
        src = doc.get("source", "")
        source_hit_count[src] = source_hit_count.get(src, 0) + 1
    
    for doc in all_docs:
        src = doc.get("source", "")
        hits = source_hit_count.get(src, 1)
        if hits > 1:
            # Birden fazla alt sorguda çıkan kaynak → %20 bonus * (hit-1)
            doc["relevance"] = doc.get("relevance", 0) * (1 + 0.20 * (hits - 1))
    
    # En yüksek relevance'a göre sırala
    all_docs.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    result = all_docs[:n_results]
    
    logger.info("agentic_rag_done", sub_queries=len(sub_queries),
                total_found=len(all_docs), returned=len(result))
    return result


def _decompose_query(query: str) -> List[str]:
    """Sorguyu alt parçalara ayır — LLM kullanmadan kural tabanlı.
    
    Türkçe bağlaçları ve çoklu-konu belirteçlerini kullanır.
    """
    import re
    q = query.strip()
    sub_queries = []
    
    # 1. "ve", "ayrıca", "bunun yanında", "hem...hem" ile ayrılmış çoklu sorular
    # Ancak çok kısa parçaları (3 kelimeden az) bölme — bunlar bağlam kaybeder
    split_patterns = [
        r'\s+ve\s+ayrıca\s+',
        r'\s+ayrıca\s+',
        r'\s+bunun\s+yanında\s+',
        r'\s+bir\s+de\s+',
        r'\s+aynı\s+zamanda\s+',
    ]
    
    parts = [q]
    for pattern in split_patterns:
        new_parts = []
        for part in parts:
            splits = re.split(pattern, part, flags=re.IGNORECASE)
            new_parts.extend(splits)
        parts = new_parts
    
    # 2. Soru cümleleri varsa ("mi", "mı", "?") ayrı sorgular
    if '?' in q:
        question_parts = re.split(r'\?\s*', q)
        question_parts = [p.strip() for p in question_parts if p.strip()]
        if len(question_parts) > 1:
            parts = question_parts
    
    # 3. Karşılaştırma sorguları — her iki tarafı da ara
    compare_match = re.search(
        r'(.+?)\s+(?:ile|ve|vs|versus)\s+(.+?)\s+(?:karşılaştır|kıyasla|fark|arasında)',
        q, re.IGNORECASE
    )
    if compare_match:
        parts = [compare_match.group(1).strip(), compare_match.group(2).strip()]
    
    # Çok kısa parçaları (2 kelimeden az) orijinal sorgu ile birleştir
    for p in parts:
        p = p.strip().rstrip('?.!,')
        if len(p.split()) >= 2:
            sub_queries.append(p)
    
    # Alt sorgu bulunamazsa orijinali döndür
    if not sub_queries:
        sub_queries = [q]
    
    # Orijinal sorguyu da ekle (tam bağlam için) — zaten listede değilse
    if len(sub_queries) > 1 and q not in sub_queries:
        sub_queries.insert(0, q)
    
    return sub_queries[:5]  # Max 5 alt sorgu


def get_stats() -> dict:
    """RAG sistemi istatistikleri"""
    try:
        collection = get_collection()
        if collection:
            count = collection.count()
            
            # v4.4.0: Çoklu koleksiyon istatistikleri
            learned_count = 0
            web_count = 0
            try:
                lc = get_learned_collection()
                if lc:
                    learned_count = lc.count()
            except Exception:
                pass
            try:
                wc = get_web_collection()
                if wc:
                    web_count = wc.count()
            except Exception:
                pass
            
            return {
                "available": True,
                "document_count": count,
                "learned_count": learned_count,
                "web_cache_count": web_count,
                "total_count": count + learned_count + web_count,
                "collection": COLLECTION_NAME,
                "collections": [COLLECTION_NAME, COLLECTION_LEARNED, COLLECTION_WEB],
                "embedding_model": EMBEDDING_MODEL
            }
    except:
        pass
    
    return {
        "available": CHROMADB_AVAILABLE and EMBEDDINGS_AVAILABLE,
        "document_count": 0,
        "collection": None,
        "embedding_model": None
    }


def delete_document(source: str) -> bool:
    """Kaynağa göre doküman siler"""
    try:
        collection = get_collection()
        if collection:
            # Bu kaynağa ait tüm chunk'ları bul ve sil
            results = collection.get(
                where={"source": source}
            )
            if results and results['ids']:
                collection.delete(ids=results['ids'])
                logger.info("document_deleted", source=source, chunks=len(results['ids']))
                return True
    except Exception as e:
        logger.error("delete_error", error=str(e))
    return False


def clear_all_documents() -> bool:
    """Tüm dokümanları siler"""
    try:
        client = get_chroma_client()
        if client:
            client.delete_collection(COLLECTION_NAME)
            global _collection
            _collection = None
            logger.info("all_documents_cleared")
            return True
    except Exception as e:
        logger.error("clear_error", error=str(e))
    return False


def list_documents(department: str = None) -> List[dict]:
    """
    Departmana göre dokümanları listeler (benzersiz source'lar).
    
    Args:
        department: Departman filtresi (None ise tümü)
    
    Returns:
        Doküman listesi
    """
    if not CHROMADB_AVAILABLE:
        return []
    
    try:
        collection = get_collection()
        if not collection:
            return []
        
        # Filtreleme
        where_filter = None
        if department and department != "Genel":
            where_filter = {"department": department}
        
        # Tüm dokümanları al
        results = collection.get(
            where=where_filter,
            include=["metadatas"]
        )
        
        if not results or not results['ids']:
            return []
        
        # Benzersiz source'ları grupla
        documents = {}
        for i, doc_id in enumerate(results['ids']):
            metadata = results['metadatas'][i] if results['metadatas'] else {}
            source = metadata.get("source", "Bilinmeyen")
            
            if source not in documents:
                documents[source] = {
                    "source": source,
                    "type": metadata.get("type", "text"),
                    "department": metadata.get("department", "Genel"),
                    "author": metadata.get("author", ""),
                    "created_at": metadata.get("created_at", ""),
                    "chunk_count": 1
                }
            else:
                documents[source]["chunk_count"] += 1
        
        return list(documents.values())
        
    except Exception as e:
        logger.error("list_documents_error", error=str(e))
        return []

