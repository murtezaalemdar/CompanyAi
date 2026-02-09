"""Geliştirilmiş Vektör Hafıza Sistemi - ChromaDB Entegrasyonu"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import structlog
import os

logger = structlog.get_logger()

# ChromaDB entegrasyonu
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logger.warning("chromadb_not_installed", message="ChromaDB is not installed. Using in-memory fallback.")

# Sentence Transformers for embeddings
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logger.warning("sentence_transformers_not_installed", message="SentenceTransformers not installed. Using ChromaDB's default.")


class VectorMemory:
    """ChromaDB tabanlı vektör hafıza sistemi"""
    
    def __init__(self, persist_directory: str = "./data/chromadb"):
        self.persist_directory = persist_directory
        self._fallback_memory: List[Dict[str, Any]] = []
        self._client = None
        self._collection = None
        self._embedding_model = None
        
        self._initialize()
    
    def _initialize(self):
        """ChromaDB bağlantısını başlat"""
        if not CHROMADB_AVAILABLE:
            logger.info("using_fallback_memory", reason="ChromaDB not available")
            return
        
        try:
            # Persist directory oluştur
            os.makedirs(self.persist_directory, exist_ok=True)
            
            # ChromaDB client
            self._client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Collection oluştur veya getir
            self._collection = self._client.get_or_create_collection(
                name="company_memory",
                metadata={"description": "Kurumsal AI Asistanı Hafıza Koleksiyonu"}
            )
            
            # Embedding model — RAG ile aynı modeli kullan (Türkçe destekli)
            if EMBEDDINGS_AVAILABLE:
                try:
                    self._embedding_model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-mpnet-base-v2')
                    logger.info("embedding_model_loaded", model="paraphrase-multilingual-mpnet-base-v2")
                except Exception as e:
                    logger.warning("embedding_model_failed", error=str(e))
                    self._embedding_model = None
            
            logger.info(
                "chromadb_initialized",
                persist_directory=self.persist_directory,
                collection_count=self._collection.count()
            )
            
        except Exception as e:
            logger.error("chromadb_init_failed", error=str(e))
            self._client = None
            self._collection = None
    
    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Metin için embedding vektörü oluştur"""
        if self._embedding_model:
            try:
                return self._embedding_model.encode(text).tolist()
            except Exception as e:
                logger.warning("embedding_failed", error=str(e))
        return None
    
    def remember(self, question: str, answer: str, metadata: Dict[str, Any]) -> str:
        """
        Soru-cevap çiftini hafızaya kaydeder.
        
        Args:
            question: Kullanıcı sorusu
            answer: AI yanıtı
            metadata: Ek bilgiler (departman, risk vb.)
            
        Returns:
            Kayıt ID'si
        """
        timestamp = datetime.utcnow().isoformat()
        doc_id = f"mem_{int(datetime.utcnow().timestamp() * 1000)}"
        
        # Full text for embedding
        full_text = f"Soru: {question}\nCevap: {answer}"
        
        # ChromaDB kullan
        if self._collection is not None:
            try:
                # Metadata'yı ChromaDB formatına dönüştür
                chroma_metadata = {
                    "question": question[:500],  # ChromaDB has metadata size limits
                    "department": str(metadata.get("dept", "Bilinmeyen")),
                    "mode": str(metadata.get("mode", "Analiz")),
                    "risk": str(metadata.get("risk", "Düşük")),
                    "confidence": float(metadata.get("confidence", 0.0)),
                    "timestamp": timestamp,
                }
                
                # Custom embedding veya ChromaDB default
                embedding = self._get_embedding(full_text)
                
                if embedding:
                    self._collection.add(
                        ids=[doc_id],
                        documents=[full_text],
                        metadatas=[chroma_metadata],
                        embeddings=[embedding]
                    )
                else:
                    self._collection.add(
                        ids=[doc_id],
                        documents=[full_text],
                        metadatas=[chroma_metadata]
                    )
                
                logger.debug(
                    "memory_stored_chromadb",
                    doc_id=doc_id,
                    total_entries=self._collection.count()
                )
                return doc_id
                
            except Exception as e:
                logger.error("chromadb_add_failed", error=str(e))
        
        # Fallback: in-memory storage
        entry = {
            "id": doc_id,
            "q": question,
            "a": answer,
            "meta": metadata,
            "timestamp": timestamp,
        }
        self._fallback_memory.append(entry)
        
        # Hafıza boyutunu sınırla (son 1000 kayıt)
        if len(self._fallback_memory) > 1000:
            self._fallback_memory.pop(0)
        
        logger.debug("memory_stored_fallback", total_entries=len(self._fallback_memory))
        return doc_id
    
    def recall(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Son kayıtları getirir.
        
        Args:
            limit: Maksimum kayıt sayısı
        
        Returns:
            Son N kayıt
        """
        if self._collection is not None:
            try:
                # ChromaDB'den tüm kayıtları al ve timestamp'e göre sırala
                results = self._collection.get(
                    include=["documents", "metadatas"]
                )
                
                if results and results.get("documents"):
                    entries = []
                    for i, doc in enumerate(results["documents"]):
                        meta = results["metadatas"][i] if results.get("metadatas") else {}
                        entries.append({
                            "id": results["ids"][i],
                            "q": meta.get("question", ""),
                            "a": doc.split("\nCevap: ")[-1] if "\nCevap: " in doc else doc,
                            "meta": {
                                "dept": meta.get("department"),
                                "mode": meta.get("mode"),
                                "risk": meta.get("risk"),
                                "confidence": meta.get("confidence"),
                            },
                            "timestamp": meta.get("timestamp"),
                        })
                    
                    # Timestamp'e göre sırala ve son N'i al
                    entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
                    return entries[:limit]
            except Exception as e:
                logger.error("chromadb_recall_failed", error=str(e))
        
        return self._fallback_memory[-limit:]
    
    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Vektör benzerlik araması yapar.
        
        Args:
            query: Arama sorgusu
            limit: Maksimum sonuç sayısı
        
        Returns:
            Benzer kayıtlar (skor ile birlikte)
        """
        if self._collection is not None and self._collection.count() > 0:
            try:
                # Custom embedding veya ChromaDB default
                query_embedding = self._get_embedding(query)
                
                if query_embedding:
                    results = self._collection.query(
                        query_embeddings=[query_embedding],
                        n_results=min(limit, self._collection.count()),
                        include=["documents", "metadatas", "distances"]
                    )
                else:
                    results = self._collection.query(
                        query_texts=[query],
                        n_results=min(limit, self._collection.count()),
                        include=["documents", "metadatas", "distances"]
                    )
                
                if results and results.get("documents") and results["documents"][0]:
                    entries = []
                    for i, doc in enumerate(results["documents"][0]):
                        meta = results["metadatas"][0][i] if results.get("metadatas") else {}
                        distance = results["distances"][0][i] if results.get("distances") else 0
                        
                        # Distance'ı similarity score'a çevir (L2 distance için)
                        similarity = 1 / (1 + distance)
                        
                        entries.append({
                            "id": results["ids"][0][i],
                            "q": meta.get("question", ""),
                            "a": doc.split("\nCevap: ")[-1] if "\nCevap: " in doc else doc,
                            "meta": {
                                "dept": meta.get("department"),
                                "mode": meta.get("mode"),
                                "risk": meta.get("risk"),
                                "confidence": meta.get("confidence"),
                            },
                            "timestamp": meta.get("timestamp"),
                            "similarity_score": round(similarity, 4),
                        })
                    
                    return entries
            except Exception as e:
                logger.error("chromadb_search_failed", error=str(e))
        
        # Fallback: basit keyword araması
        return self._keyword_search(query, limit)
    
    def _keyword_search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Basit anahtar kelime araması (fallback)"""
        query_lower = query.lower()
        results = []
        
        for entry in reversed(self._fallback_memory):
            if query_lower in entry["q"].lower() or query_lower in entry["a"].lower():
                results.append(entry)
                if len(results) >= limit:
                    break
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Hafıza istatistikleri"""
        if self._collection is not None:
            try:
                count = self._collection.count()
                results = self._collection.get(include=["metadatas"])
                
                departments = {}
                if results and results.get("metadatas"):
                    for meta in results["metadatas"]:
                        dept = meta.get("department", "Bilinmeyen")
                        departments[dept] = departments.get(dept, 0) + 1
                
                return {
                    "storage_type": "chromadb",
                    "total_entries": count,
                    "by_department": departments,
                    "persist_directory": self.persist_directory,
                    "embedding_model": "all-MiniLM-L6-v2" if self._embedding_model else "chromadb_default",
                }
            except Exception as e:
                logger.error("chromadb_stats_failed", error=str(e))
        
        # Fallback stats
        if not self._fallback_memory:
            return {"storage_type": "in_memory", "total_entries": 0}
        
        departments = {}
        for entry in self._fallback_memory:
            dept = entry.get("meta", {}).get("dept", "Bilinmeyen")
            departments[dept] = departments.get(dept, 0) + 1
        
        return {
            "storage_type": "in_memory",
            "total_entries": len(self._fallback_memory),
            "by_department": departments,
            "oldest_entry": self._fallback_memory[0].get("timestamp") if self._fallback_memory else None,
            "newest_entry": self._fallback_memory[-1].get("timestamp") if self._fallback_memory else None,
        }
    
    def clear(self) -> int:
        """Tüm hafızayı temizler (dikkatli kullanın)"""
        count = 0
        
        if self._collection is not None:
            try:
                count = self._collection.count()
                # Collection'ı sil ve yeniden oluştur
                self._client.delete_collection("company_memory")
                self._collection = self._client.get_or_create_collection(
                    name="company_memory",
                    metadata={"description": "Kurumsal AI Asistanı Hafıza Koleksiyonu"}
                )
                logger.warning("chromadb_cleared", cleared_entries=count)
            except Exception as e:
                logger.error("chromadb_clear_failed", error=str(e))
        
        # Fallback memory'yi de temizle
        fallback_count = len(self._fallback_memory)
        self._fallback_memory.clear()
        
        return count + fallback_count


# Singleton instance
_vector_memory: Optional[VectorMemory] = None


def get_vector_memory() -> VectorMemory:
    """VectorMemory singleton instance'ını döndürür"""
    global _vector_memory
    if _vector_memory is None:
        _vector_memory = VectorMemory()
    return _vector_memory


# Backward compatibility functions
def remember(question: str, answer: str, metadata: Dict[str, Any]) -> None:
    """Legacy function - VectorMemory.remember wrapper"""
    get_vector_memory().remember(question, answer, metadata)


def recall(limit: int = 10) -> List[Dict[str, Any]]:
    """Legacy function - VectorMemory.recall wrapper"""
    return get_vector_memory().recall(limit)


def search_memory(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Legacy function - VectorMemory.search wrapper"""
    return get_vector_memory().search(query, limit)


def get_stats() -> Dict[str, Any]:
    """Legacy function - VectorMemory.get_stats wrapper"""
    return get_vector_memory().get_stats()


def clear_memory() -> int:
    """Legacy function - VectorMemory.clear wrapper"""
    return get_vector_memory().clear()