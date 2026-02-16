"""
CompanyAI — Ollama Client Unit Tests
=======================================
_build_messages saf metod + generate/stream mocklı testleri.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock


# ═══════════════════════════════════════════════════
# 1. _build_messages — Saf fonksiyon testleri
# ═══════════════════════════════════════════════════

class TestBuildMessages:
    """OllamaClient._build_messages metodu testleri."""

    def _get_client(self):
        from app.llm.client import OllamaClient
        return OllamaClient()

    def test_basic_prompt(self):
        client = self._get_client()
        msgs = client._build_messages("Merhaba")
        assert len(msgs) == 1
        assert msgs[0] == {"role": "user", "content": "Merhaba"}

    def test_with_system_prompt(self):
        client = self._get_client()
        msgs = client._build_messages("Soru", system_prompt="Sen bir asistansın.")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == "Sen bir asistansın."
        assert msgs[1]["role"] == "user"

    def test_with_history(self):
        client = self._get_client()
        history = [
            {"q": "Önceki soru", "a": "Önceki cevap"},
        ]
        msgs = client._build_messages("Yeni soru", history=history)
        assert len(msgs) == 3  # history q + history a + current
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Önceki soru"
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["content"] == "Önceki cevap"
        assert msgs[2]["role"] == "user"
        assert msgs[2]["content"] == "Yeni soru"

    def test_history_truncated_to_5(self):
        """Son 5 tur korunmalı, öncekiler atılmalı."""
        client = self._get_client()
        history = [{"q": f"Soru {i}", "a": f"Cevap {i}"} for i in range(10)]
        msgs = client._build_messages("Son soru", history=history)
        # 5 tur × 2 mesaj + 1 current = 11
        assert len(msgs) == 11

    def test_system_prompt_plus_history(self):
        client = self._get_client()
        history = [{"q": "Q1", "a": "A1"}]
        msgs = client._build_messages("Q2", system_prompt="Sys", history=history)
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"      # Q1
        assert msgs[2]["role"] == "assistant"  # A1
        assert msgs[3]["role"] == "user"       # Q2

    def test_empty_history(self):
        client = self._get_client()
        msgs = client._build_messages("Test", history=[])
        assert len(msgs) == 1

    def test_none_history(self):
        client = self._get_client()
        msgs = client._build_messages("Test", history=None)
        assert len(msgs) == 1

    def test_partial_history_entries(self):
        """Sadece soru olan history entry."""
        client = self._get_client()
        history = [{"q": "Soru", "a": ""}]
        msgs = client._build_messages("Test", history=history)
        # Empty string is falsy, so "a" won't be added
        assert any(m["content"] == "Soru" for m in msgs)

    def test_empty_system_prompt_not_added(self):
        client = self._get_client()
        msgs = client._build_messages("Test", system_prompt="")
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"


# ═══════════════════════════════════════════════════
# 2. is_available — Mock HTTP testleri
# ═══════════════════════════════════════════════════

class TestIsAvailable:
    """OllamaClient.is_available mock testleri."""

    @pytest.mark.asyncio
    async def test_available_returns_true(self):
        from app.llm.client import OllamaClient
        client = OllamaClient()

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)
        mock_http.is_closed = False
        client._client = mock_http

        result = await client.is_available()
        assert result is True

        await client.close()

    @pytest.mark.asyncio
    async def test_unavailable_returns_false(self):
        from app.llm.client import OllamaClient
        client = OllamaClient()

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=Exception("connection refused"))
        mock_http.is_closed = False
        client._client = mock_http

        result = await client.is_available()
        assert result is False

        await client.close()


# ═══════════════════════════════════════════════════
# 3. OllamaClient init
# ═══════════════════════════════════════════════════

class TestOllamaClientInit:
    """OllamaClient sınıf başlatma testleri."""

    def test_default_values(self):
        from app.llm.client import OllamaClient
        client = OllamaClient()
        assert client.base_url is not None
        assert client.model is not None
        assert client.timeout == 900.0
        assert client._client is None  # Lazy init

    def test_singleton_instance_exists(self):
        from app.llm.client import ollama_client
        assert ollama_client is not None
