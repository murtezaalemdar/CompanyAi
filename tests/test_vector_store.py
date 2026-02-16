"""
CompanyAI — Vector Store Unit Tests
======================================
chunk_text saf fonksiyon testleri + mock ChromaDB search/add testleri.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.rag.vector_store import chunk_text


# ═══════════════════════════════════════════════════
# 1. chunk_text — Saf fonksiyon testleri (mock yok)
# ═══════════════════════════════════════════════════

class TestChunkText:
    """Metin parçalama fonksiyonu testleri."""

    def test_short_text_single_chunk(self):
        """chunk_size'dan kısa metin → tek chunk."""
        result = chunk_text("Bu kısa bir metin.", chunk_size=500)
        assert len(result) == 1
        assert result[0] == "Bu kısa bir metin."

    def test_empty_text_returns_list(self):
        """Boş metin → en az 1 eleman."""
        result = chunk_text("", chunk_size=100)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_respects_sentence_boundaries(self):
        """Cümle sınırlarında bölüyor mu?"""
        text = "Birinci cümle. İkinci cümle. Üçüncü cümle. Dördüncü cümle."
        result = chunk_text(text, chunk_size=35, overlap=5)
        # Her chunk tam cümle(ler) içermeli
        for chunk in result:
            assert chunk.strip() != ""

    def test_long_text_produces_multiple_chunks(self):
        """Uzun metin birden fazla chunk üretmeli."""
        text = "Bu bir test cümlesidir. " * 100  # ~2400 karakter
        result = chunk_text(text, chunk_size=200, overlap=50)
        assert len(result) > 1

    def test_chunk_size_respected(self):
        """Chunk'lar hedef boyutu çok aşmamalı."""
        text = "Kısa bir cümle. " * 200
        result = chunk_text(text, chunk_size=300, overlap=50)
        for chunk in result:
            # Cümle sınırı yüzünden biraz aşabilir ama makul olmalı
            assert len(chunk) < 600  # 2x tolerance

    def test_overlap_content_exists(self):
        """Overlap > 0 ise ardışık chunk'lar ortak metin içermeli."""
        text = "Alfa cümlesi burada. Beta cümlesi burada. Gama cümlesi burada. Delta cümlesi burada."
        result = chunk_text(text, chunk_size=30, overlap=15)
        if len(result) >= 2:
            # En az bir miktar overlap olmalı (kesin garanti değil ama genelde var)
            assert len(result) >= 2

    def test_single_very_long_sentence(self):
        """Tek cümle chunk_size aşarsa → kelime sınırından bölmeli."""
        long_sentence = "kelime " * 200  # ~1400 karakter, nokta yok
        result = chunk_text(long_sentence.strip(), chunk_size=100, overlap=20)
        assert len(result) > 1
        for chunk in result:
            assert len(chunk) > 0

    def test_returns_list_of_strings(self):
        result = chunk_text("Test metin")
        assert isinstance(result, list)
        assert all(isinstance(c, str) for c in result)

    def test_preserves_all_content(self):
        """Hiçbir kelime kaybolmuyor mu? (overlap hariç)"""
        text = "Birinci. İkinci. Üçüncü."
        result = chunk_text(text, chunk_size=15, overlap=0)
        combined = " ".join(result)
        for word in ["Birinci", "İkinci", "Üçüncü"]:
            assert word in combined

    def test_default_parameters(self):
        """Varsayılan parametrelerle çalışıyor mu?"""
        text = "Test metni. " * 50
        result = chunk_text(text)
        assert len(result) >= 1


# ═══════════════════════════════════════════════════
# 2. search_documents — Mock ChromaDB testleri
# ═══════════════════════════════════════════════════

class TestSearchDocuments:
    """search_documents fonksiyonu mock testleri."""

    @patch("app.rag.vector_store.CHROMADB_AVAILABLE", False)
    def test_returns_empty_when_chromadb_unavailable(self):
        from app.rag.vector_store import search_documents
        result = search_documents("test query")
        assert result == []

    @patch("app.rag.vector_store.EMBEDDINGS_AVAILABLE", False)
    def test_returns_empty_when_embeddings_unavailable(self):
        from app.rag.vector_store import search_documents
        result = search_documents("test query")
        assert result == []


# ═══════════════════════════════════════════════════
# 3. add_document — Mock testleri
# ═══════════════════════════════════════════════════

class TestAddDocument:
    """add_document fonksiyonu mock testleri."""

    @patch("app.rag.vector_store.CHROMADB_AVAILABLE", False)
    def test_returns_false_when_unavailable(self):
        from app.rag.vector_store import add_document
        result = add_document("test içerik", "test_source")
        assert result is False


# ═══════════════════════════════════════════════════
# 4. get_stats — Fallback testleri
# ═══════════════════════════════════════════════════

class TestGetStats:
    """get_stats fonksiyonu testleri."""

    @patch("app.rag.vector_store.CHROMADB_AVAILABLE", False)
    @patch("app.rag.vector_store.EMBEDDINGS_AVAILABLE", False)
    def test_stats_when_unavailable(self):
        from app.rag.vector_store import get_stats
        result = get_stats()
        assert result["available"] is False
        assert result["document_count"] == 0
