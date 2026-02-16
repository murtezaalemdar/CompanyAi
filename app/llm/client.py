"""Ollama LLM Client - Chat API (GPU Auto-Config Destekli)

/api/chat endpoint'i kullanır (generate yerine).
Bu, Mistral'in chat template'ini otomatik uygular ve
çok daha iyi talimat takibi sağlar.

╔═══════════════════════════════════════════════════════════════════╗
║  ÖNEMLİ NOTLAR — Performans Parametreleri (v4.1.0)               ║
║                                                                   ║
║  • GPU OTOMATİK ALGILAMA: gpu_config.probe() startup'ta çalışır. ║
║    Tüm parametreler (timeout, num_gpu, num_ctx, num_batch,       ║
║    num_thread) GPU durumuna göre dinamik ayarlanır.               ║
║  • GPU yok → CPU-only: timeout=900s, num_gpu=0                   ║
║  • GPU var ama model sığmaz → CPU-only: timeout=900s, num_gpu=0  ║
║  • Tek GPU → timeout=120s, num_gpu=99 (tüm katmanlar GPU'da)    ║
║  • Multi-GPU → timeout=60s, num_gpu=99 (Ollama dağıtır)         ║
║  • GPU eklenince/çıkarılınca: restart'ta otomatik algılanır.     ║
║  • connection_pooling: Tek persistent client (max 10 conn).       ║
║  • retry: Ollama 500 hatalarında 1 kez yeniden dener.            ║
╚═══════════════════════════════════════════════════════════════════╝
"""

import asyncio
import httpx
import json
import os
from typing import AsyncGenerator, Optional
import structlog
from app.config import settings
from app.llm.gpu_config import gpu_config

logger = structlog.get_logger()


class OllamaClient:
    """Ollama Chat API ile iletişim kuran async client — connection pooling destekli"""
    
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.LLM_MODEL
        self.vision_model = getattr(settings, "VISION_MODEL", "minicpm-v")  # v4.4.0: llava → minicpm-v
        self.omni_model = getattr(settings, "OMNI_MODEL", "minicpm-o")    # v4.5.0: omni-modal (görüntü+video+ses)
        # Timeout artık gpu_config tarafından dinamik belirleniyor
        # GPU varsa kısa (120s), yoksa uzun (900s)
        self._client: httpx.AsyncClient | None = None

    @property
    def timeout(self) -> float:
        """GPU durumuna göre dinamik timeout."""
        return gpu_config.timeout

    async def _get_client(self) -> httpx.AsyncClient:
        """Persistent HTTP client döner (connection pooling) — timeout gpu_config'dan"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                trust_env=False,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def _refresh_client_if_needed(self):
        """GPU probe sonrası timeout değiştiyse client'ı yenile."""
        if self._client and not self._client.is_closed:
            current_timeout = self._client.timeout.read
            if current_timeout != self.timeout:
                logger.info("ollama_client_timeout_updated",
                            old=current_timeout, new=self.timeout)
                await self.close()
                # Sonraki _get_client çağrısında yeni timeout ile oluşturulacak

    async def close(self):
        """Client'ı kapat (shutdown'da çağrılır)"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

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
        max_tokens: int = 512,
        images: list[str] | None = None,
        history: list[dict] | None = None,
        tools: list[dict] | None = None,
        use_omni: bool = False,
    ) -> str | dict:
        """
        Chat API ile tek seferde yanıt üretir.
        Ollama 500 hatalarında 1 kez yeniden dener (model yükleme gecikmeleri için).
        
        v4.3.0: tools parametresi eklendi — Ollama native function calling.
        v4.5.0: use_omni parametresi — MiniCPM-o 2.6 omni-modal model için.
        tools varsa ve model tool_calls döndürüyorsa dict döner:
            {"content": str, "tool_calls": list[dict]}
        """
        max_retries = 1
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                model = self.model
                if use_omni and images:
                    model = self.omni_model   # MiniCPM-o 2.6 (video/ses/görüntü)
                elif images:
                    model = self.vision_model  # MiniCPM-V (görüntü)

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
                        **gpu_config.options,              # GPU auto-config: num_gpu, num_ctx, num_batch, num_thread
                    },
                }
                
                # v4.3.0: Ollama native function calling
                if tools:
                    payload["tools"] = tools

                client = await self._get_client()
                logger.info("ollama_chat_request", model=model, msg_count=len(messages),
                            has_tools=bool(tools),
                            attempt=attempt + 1 if attempt > 0 else None)
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()

                # /api/chat yanıt formatı: {"message": {"role": "assistant", "content": "..."}}
                msg = result.get("message", {})
                
                # v4.3.0: tool_calls varsa dict döndür
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    return {
                        "content": msg.get("content", ""),
                        "tool_calls": tool_calls,
                    }
                
                return msg.get("content", "")

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 500 and attempt < max_retries:
                    # Ollama 500: model yükleme sorunu olabilir → kısa bekle ve tekrar dene
                    wait_secs = 5 * (attempt + 1)
                    logger.warning(
                        "ollama_500_retry",
                        attempt=attempt + 1,
                        wait_secs=wait_secs,
                        error=str(e),
                    )
                    await asyncio.sleep(wait_secs)
                    continue
                logger.error("ollama_http_error", error=str(e))
                raise Exception(f"LLM bağlantı hatası: {e}")
            except httpx.TimeoutException:
                logger.error("ollama_timeout", model=model)
                raise Exception("LLM yanıt süresi aşıldı")
            except httpx.HTTPError as e:
                logger.error("ollama_http_error", error=str(e))
                raise Exception(f"LLM bağlantı hatası: {e}")
        
        # max_retries aşıldıysa
        logger.error("ollama_http_error", error=str(last_error), retries_exhausted=True)
        raise Exception(f"LLM bağlantı hatası: {last_error}")
    
    async def stream(
        self,
        prompt: str,
        system_prompt: str = "",
        history: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """
        Chat API ile streaming yanıt üretir.
        """
        try:
            messages = self._build_messages(prompt, system_prompt, history)
            
            client = await self._get_client()
            logger.info("ollama_chat_stream", model=self.model, msg_count=len(messages))
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                        **gpu_config.options,           # GPU auto-config
                    },
                }
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
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
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except Exception:
            return False
    
    async def get_models(self) -> list:
        """Mevcut modelleri listeler"""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []


# Singleton instance
ollama_client = OllamaClient()
