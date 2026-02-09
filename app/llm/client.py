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
        self.vision_model = getattr(settings, "VISION_MODEL", "llava")  # llava / llava-llama3
        self.timeout = 900.0  # GPU yok — CPU inference için 15 dakika timeout
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        images: list[str] | None = None,
    ) -> str:
        """
        Tek seferde yanıt üretir (non-streaming).
        
        Args:
            prompt: Kullanıcı sorusu
            system_prompt: Sistem context'i
            temperature: Yaratıcılık seviyesi (0-1)
            max_tokens: Maksimum token sayısı
            images: Base64 kodlanmış resim listesi (vision modeli için)
        
        Returns:
            LLM yanıtı
        """
        try:
            # Vision modeli gerekiyorsa model adını değiştir
            model = self.model
            if images:
                model = self.vision_model

            payload: dict = {
                "model": model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            }
            if images:
                payload["images"] = images

            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                logger.info("ollama_request", url=f"{self.base_url}/api/generate", model=model, vision=bool(images))
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
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
        
        Args:
            prompt: Kullanıcı sorusu
            system_prompt: Sistem context'i
        
        Yields:
            LLM yanıt parçaları
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                logger.info("ollama_stream_request", url=f"{self.base_url}/api/generate", model=self.model)
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
            async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                logger.debug("ollama_health_check", status=response.status_code, url=f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception as e:
            logger.error("ollama_health_check_failed", error=str(e), url=f"{self.base_url}/api/tags")
            return False
    
    async def get_models(self) -> list:
        """Mevcut modelleri listeler"""
        try:
            async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except:
            return []


# Singleton instance
ollama_client = OllamaClient()
