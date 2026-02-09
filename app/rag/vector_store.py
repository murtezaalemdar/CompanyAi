"""RAG (Retrieval Augmented Generation) Modülü

Şirket dokümanlarını vektör veritabanında saklar ve sorulara bağlamsal cevap verir.
"""

import os
from pathlib import Path
from typing import List, Optional
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


# Vektör veritabanı yolu
CHROMA_PERSIST_DIR = "/opt/companyai/data/chromadb"
COLLECTION_NAME = "company_documents"

# Embedding modeli (Türkçe destekli, küçük ve hızlı)
# Embedding modeli (Türkçe destekli, PRO seviye)
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

# Singleton instances
_chroma_client = None
_embedding_model = None
_collection = None


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
        collection = get_collection()
        model = get_embedding_model()
        
        if not collection or not model:
            return False
        
        # Dokümanı parçalara böl (chunking)
        chunks = chunk_text(content, chunk_size=500, overlap=50)
        
        for i, chunk in enumerate(chunks):
            doc_id = f"{source}_{i}"
            embedding = model.encode(chunk).tolist()
            
            doc_metadata = {
                "source": source,
                "type": doc_type,
                "chunk_index": i,
                "total_chunks": len(chunks),
                **(metadata or {})
            }
            
            collection.add(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[doc_metadata]
            )
        
        logger.info("document_added", source=source, chunks=len(chunks))
        return True
        
    except Exception as e:
        logger.error("add_document_error", error=str(e))
        return False


def search_documents(query: str, n_results: int = 3, department: str = None) -> List[dict]:
    """
    Sorguya en uygun dokümanları arar.
    
    Args:
        query: Arama sorgusu
        n_results: Döndürülecek sonuç sayısı
        department: Departman filtresi (Opsiyonel)
    
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
        
        # Sorguyu vektöre çevir
        query_embedding = model.encode(query).tolist()
        
        # Filtreleme
        where_filter = {}
        if department and department != "Genel":
            where_filter = {"department": department}

        # Ara
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter if where_filter else None
        )
        
        # Sonuçları formatla
        documents = []
        if results and results['documents']:
            for i, doc in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                distance = results['distances'][0][i] if results['distances'] else 0
                
                documents.append({
                    "content": doc,
                    "source": metadata.get("source", "Bilinmeyen"),
                    "type": metadata.get("type", "text"),
                    "department": metadata.get("department", "Genel"),
                    "relevance": 1 - distance,  # Mesafeyi benzerliğe çevir
                })
        
        logger.info("search_completed", query=query[:50], results=len(documents))
        return documents
        
    except Exception as e:
        logger.error("search_error", error=str(e))
        return []


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """
    Metni parçalara böler.
    
    Args:
        text: Bölünecek metin
        chunk_size: Parça boyutu (karakter)
        overlap: Parçalar arası örtüşme
    
    Returns:
        Metin parçaları listesi
    """
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + chunk_size
        
        # Kelime ortasında bölmemeye çalış
        if end < text_len:
            # Son boşluğu bul (fakat start + overlap'ten ileride olmalı)
            last_space = text.rfind(' ', start + overlap, end)
            if last_space > start:
                end = last_space
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        start = end - overlap
    
    return chunks


def get_stats() -> dict:
    """RAG sistemi istatistikleri"""
    try:
        collection = get_collection()
        if collection:
            count = collection.count()
            return {
                "available": True,
                "document_count": count,
                "collection": COLLECTION_NAME,
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

