"""Ollama LLM Client - Mistral Entegrasyonu"""

import httpx
import json
from typing import AsyncGenerator, Optional
import structlog
from app.config import settings

logger = structlog.get_logger()


class OllamaClient:
    """Ollama API ile iletişim kuran async client"""
    
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.LLM_MODEL  # mistral
        self.timeout = 120.0  # LLM yanıt süresi için uzun timeout
        logger.info("ollama_client_init", base_url=self.base_url, model=self.model)
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """
        Tek seferde yanıt üretir (non-streaming).
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "system": system_prompt,
                        "stream": False,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        }
                    }
                )
                response.raise_for_status()
                result = response.json()
                return result.get("response", "")
                
        except httpx.TimeoutException:
            logger.error("ollama_timeout", model=self.model)
            raise Exception("LLM yanıt süresi aşıldı")
        except httpx.HTTPError as e:
            logger.error("ollama_http_error", error=str(e))
            raise Exception(f"LLM bağlantı hatası: {e}")
    
    async def stream(
        self,
        prompt: str,
        system_prompt: str = "",
    ) -> AsyncGenerator[str, None]:
        """
        Streaming yanıt üretir.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "system": system_prompt,
                        "stream": True,
                    }
                ) as response:
                    async for line in response.aiter_lines():
                        if line:
                            data = json.loads(line)
                            if "response" in data:
                                yield data["response"]
                                
        except Exception as e:
            logger.error("ollama_stream_error", error=str(e))
            raise
    
    async def is_available(self) -> bool:
        """Ollama servisinin erişilebilir olup olmadığını kontrol eder"""
        try:
            # logger.info("checking_ollama_availability", url=self.base_url)
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code != 200:
                    logger.error("ollama_health_status_error", code=response.status_code, body=response.text[:200])
                    return False
                return True
        except Exception as e:
            logger.error("ollama_connection_failed", error=str(e), url=self.base_url, type=str(type(e)))
            return False
    
    async def get_models(self) -> list:
        """Mevcut modelleri listeler"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.error("ollama_get_models_failed", error=str(e))
            return []


# Singleton instance
ollama_client = OllamaClient()
