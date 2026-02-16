"""
CompanyAI — Redis Cache Layer
================================
Embedding hesaplaması ve LLM yanıtları için Redis cache.
Aynı prompt/sorgu tekrar geldiğinde anında yanıt verir.

Kullanım:
  from app.cache.redis_cache import cache_get, cache_set, cached_embedding

Cache Categories:
  - emb:<hash>     → Embedding vektörleri (7 gün TTL)
  - llm:<hash>     → LLM yanıtları (1 saat TTL)
  - rag:<hash>     → RAG search sonuçları (30 dakika TTL)
"""

import hashlib
import json
from typing import Optional, Any

import structlog

logger = structlog.get_logger()

# ── Redis bağlantısı ──
_redis_client = None
REDIS_AVAILABLE = False

try:
    import redis.asyncio as aioredis

    async def get_redis():
        """Lazy Redis client (async)."""
        global _redis_client, REDIS_AVAILABLE
        if _redis_client is None:
            try:
                from app.config import settings
                _redis_client = aioredis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=3,
                    socket_timeout=5,
                )
                # Bağlantıyı test et
                await _redis_client.ping()
                REDIS_AVAILABLE = True
                logger.info("redis_connected", url=settings.REDIS_URL)
            except Exception as e:
                logger.warning("redis_unavailable", error=str(e))
                _redis_client = None
                REDIS_AVAILABLE = False
        return _redis_client

except ImportError:
    logger.warning("redis_not_installed", message="Redis cache devre dışı")

    async def get_redis():
        return None


# ── Cache Key Helper ──
def _cache_key(prefix: str, data: str) -> str:
    """Tekrarlanabilir, kısa cache key üret."""
    h = hashlib.md5(data.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{h}"


# ── Genel Cache Get/Set ──
async def cache_get(key: str) -> Optional[str]:
    """Cache'den değer oku. Redis yoksa None döner."""
    try:
        client = await get_redis()
        if client:
            return await client.get(key)
    except Exception:
        pass
    return None


async def cache_set(key: str, value: str, ttl: int = 3600) -> bool:
    """Cache'e yaz. TTL saniye cinsinden."""
    try:
        client = await get_redis()
        if client:
            await client.set(key, value, ex=ttl)
            return True
    except Exception:
        pass
    return False


async def cache_delete(key: str) -> bool:
    """Cache'den sil."""
    try:
        client = await get_redis()
        if client:
            await client.delete(key)
            return True
    except Exception:
        pass
    return False


# ── Embedding Cache ──
async def cached_embedding(text: str) -> Optional[list]:
    """
    Embedding vektörünü cache'den oku.
    Cache yoksa None → arayanın hesaplaması gerekir.
    """
    key = _cache_key("emb", text)
    raw = await cache_get(key)
    if raw:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass
    return None


async def save_embedding(text: str, vector: list, ttl: int = 604800) -> bool:
    """Embedding vektörünü cache'e kaydet (7 gün TTL)."""
    key = _cache_key("emb", text)
    try:
        return await cache_set(key, json.dumps(vector), ttl=ttl)
    except Exception:
        return False


# ── LLM Yanıt Cache ──
async def cached_llm_response(prompt_hash: str) -> Optional[str]:
    """LLM yanıtını cache'den oku."""
    key = _cache_key("llm", prompt_hash)
    return await cache_get(key)


async def save_llm_response(prompt_hash: str, response: str, ttl: int = 3600) -> bool:
    """LLM yanıtını cache'e kaydet (1 saat TTL)."""
    key = _cache_key("llm", prompt_hash)
    return await cache_set(key, response, ttl=ttl)


# ── RAG Search Cache ──
async def cached_rag_results(query: str) -> Optional[list]:
    """RAG search sonuçlarını cache'den oku."""
    key = _cache_key("rag", query)
    raw = await cache_get(key)
    if raw:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass
    return None


async def save_rag_results(query: str, results: list, ttl: int = 1800) -> bool:
    """RAG search sonuçlarını cache'e kaydet (30 dk TTL)."""
    key = _cache_key("rag", query)
    try:
        return await cache_set(key, json.dumps(results), ttl=ttl)
    except Exception:
        return False


# ── Cache İstatistikleri ──
async def get_cache_stats() -> dict:
    """Redis cache istatistikleri."""
    try:
        client = await get_redis()
        if client:
            info = await client.info("memory")
            keys = await client.dbsize()
            return {
                "available": True,
                "total_keys": keys,
                "used_memory": info.get("used_memory_human", "unknown"),
                "max_memory": info.get("maxmemory_human", "0"),
            }
    except Exception:
        pass
    return {"available": False, "total_keys": 0}
