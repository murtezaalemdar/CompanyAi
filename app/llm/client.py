"""Ollama LLM Client - Chat API (Geliştirilmiş Versiyon)

/api/chat endpoint'i kullanır (generate yerine).
Bu, Mistral'in chat template'ini otomatik uygular ve
çok daha iyi talimat takibi sağlar.
"""

import httpx
import json
from typing import AsyncGenerator, Optional
import structlog
from app.config import settings

logger = structlog.get_logger()


class OllamaClient:
    """Ollama Chat API ile iletişim kuran async client"""
    
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.LLM_MODEL  # mistral
        self.vision_model = getattr(settings, "VISION_MODEL", "llava")
        self.timeout = 900.0  # CPU inference — 15 dk

    def _build_messages(
        self,
        prompt: str,
        system_prompt: str = "",
        history: list[dict] | None = None,
    ) -> list[dict]:
        """
        Ollama /api/chat için messages array'i oluştur.
        
        history formatı: [{"q": "soru", "a": "cevap"}, ...]
        """
        messages = []
        
        # System mesajı
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Konuşma geçmişi (varsa)
        if history:
            for h in history[-5:]:  # Son 5 tur
                if h.get("q"):
                    messages.append({"role": "user", "content": h["q"]})
                if h.get("a"):
                    messages.append({"role": "assistant", "content": h["a"]})
        
        # Mevcut soru
        messages.append({"role": "user", "content": prompt})
        
        return messages

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        images: list[str] | None = None,
        history: list[dict] | None = None,
    ) -> str:
        """
        Chat API ile tek seferde yanıt üretir.
        """
        try:
            model = self.model
            if images:
                model = self.vision_model

            messages = self._build_messages(prompt, system_prompt, history)
            
            # Vision: son mesaja images ekle
            if images and messages:
                messages[-1]["images"] = images

            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            }

            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                logger.info("ollama_chat_request", model=model, msg_count=len(messages))
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
                
                # /api/chat yanıt formatı: {"message": {"role": "assistant", "content": "..."}}
                msg = result.get("message", {})
                return msg.get("content", "")
                
        except httpx.TimeoutException:
            logger.error("ollama_timeout", model=model)
            raise Exception("LLM yanıt süresi aşıldı")
        except httpx.HTTPError as e:
            logger.error("ollama_http_error", error=str(e))
            raise Exception(f"LLM bağlantı hatası: {e}")
    
    async def stream(
        self,
        prompt: str,
        system_prompt: str = "",
        history: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Chat API ile streaming yanıt üretir.
        """
        try:
            messages = self._build_messages(prompt, system_prompt, history)
            
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                logger.info("ollama_chat_stream", model=self.model, msg_count=len(messages))
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": True,
                    }
                ) as response:
                    async for line in response.aiter_lines():
                        if line:
                            data = json.loads(line)
                            # /api/chat stream formatı: {"message": {"content": "..."}}
                            msg = data.get("message", {})
                            content = msg.get("content", "")
                            if content:
                                yield content
                                
        except Exception as e:
            logger.error("ollama_stream_error", error=str(e))
            raise
    
    async def is_available(self) -> bool:
        """Ollama servisinin erişilebilir olup olmadığını kontrol eder"""
        try:
            async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False
    
    async def get_models(self) -> list:
        """Mevcut modelleri listeler"""
        try:
            async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []


# Singleton instance
ollama_client = OllamaClient()
