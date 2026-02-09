"""Ollama LLM Client - Debug Version"""

import httpx
import json
from typing import AsyncGenerator, Optional
from app.config import settings
import traceback

class OllamaClient:
    """Ollama API ile iletişim kuran async client"""
    
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.LLM_MODEL
        self.timeout = 120.0
        print(f"DEBUG: OllamaClient init with base_url={self.base_url}, model={self.model}")
    
    async def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 2048) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "system": system_prompt,
                        "stream": False,
                        "options": {"temperature": temperature, "num_predict": max_tokens}
                    }
                )
                response.raise_for_status()
                result = response.json()
                return result.get("response", "")
        except Exception as e:
            print(f"DEBUG: generate error: {e}")
            raise

    async def stream(self, prompt: str, system_prompt: str = "") -> AsyncGenerator[str, None]:
        # implementation omitted for brevity as we debug availability
        pass

    async def is_available(self) -> bool:
        """Ollama servisinin erişilebilir olup olmadığını kontrol eder"""
        print(f"DEBUG: Checking availability at {self.base_url}/api/tags")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                print(f"DEBUG: Response status: {response.status_code}")
                if response.status_code != 200:
                    print(f"DEBUG: Response body: {response.text[:200]}")
                    return False
                return True
        except Exception as e:
            print(f"DEBUG: Connection failed: {e}")
            traceback.print_exc()
            return False
    
    async def get_models(self) -> list:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            print(f"DEBUG: get_models error: {e}")
            return []

ollama_client = OllamaClient()
