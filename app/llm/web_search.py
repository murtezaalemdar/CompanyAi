"""Web Arama Modülü — İnternetten bilgi çekme yeteneği

DuckDuckGo arama API'si kullanarak, AI asistanın bilmediği konularda
internetten güncel bilgi bulmasını sağlar.
"""

import httpx
import structlog
from typing import List, Dict, Optional

logger = structlog.get_logger()

# DuckDuckGo Instant Answer API (ücretsiz, API key gereksiz)
DDG_API_URL = "https://api.duckduckgo.com/"

# DuckDuckGo HTML arama (daha zengin sonuçlar)
DDG_HTML_URL = "https://html.duckduckgo.com/html/"


async def search_web(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    """
    DuckDuckGo ile web araması yapar.
    
    Args:
        query: Aranacak metin
        max_results: Maksimum sonuç sayısı
    
    Returns:
        [{"title": str, "snippet": str, "url": str}, ...]
    """
    results = []
    
    # Yöntem 1: DuckDuckGo Instant Answer API
    try:
        instant = await _search_instant(query)
        if instant:
            results.extend(instant[:max_results])
    except Exception as e:
        logger.warning("ddg_instant_failed", error=str(e))
    
    # Yöntem 2: DuckDuckGo HTML arama (daha çok sonuç)
    if len(results) < max_results:
        try:
            html_results = await _search_html(query, max_results - len(results))
            results.extend(html_results)
        except Exception as e:
            logger.warning("ddg_html_failed", error=str(e))
    
    logger.info("web_search_complete", query=query[:80], results_count=len(results))
    return results[:max_results]


async def _search_instant(query: str) -> List[Dict[str, str]]:
    """DuckDuckGo Instant Answer API ile arama"""
    results = []
    
    async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
        response = await client.get(
            DDG_API_URL,
            params={
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1,
            },
            headers={"User-Agent": "CompanyAI/1.0"}
        )
        response.raise_for_status()
        data = response.json()
    
    # Abstract (Wikipedia vb.)
    if data.get("Abstract"):
        results.append({
            "title": data.get("Heading", "Sonuç"),
            "snippet": data["Abstract"][:500],
            "url": data.get("AbstractURL", ""),
            "source": data.get("AbstractSource", "Web"),
        })
    
    # Related Topics
    for topic in data.get("RelatedTopics", [])[:3]:
        if isinstance(topic, dict) and topic.get("Text"):
            results.append({
                "title": topic.get("Text", "")[:80],
                "snippet": topic.get("Text", "")[:300],
                "url": topic.get("FirstURL", ""),
                "source": "DuckDuckGo",
            })
    
    return results


async def _search_html(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    """DuckDuckGo HTML araması ile sonuç çekme"""
    results = []
    
    try:
        async with httpx.AsyncClient(timeout=10.0, trust_env=False, follow_redirects=True) as client:
            response = await client.post(
                DDG_HTML_URL,
                data={"q": query},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                }
            )
            response.raise_for_status()
            html = response.text
        
        # Basit HTML parsing (beautifulsoup olmadan da çalışır)
        # DuckDuckGo HTML sayfasındaki sonuçları yakala
        import re
        
        # Sonuç bloklarını bul
        result_blocks = re.findall(
            r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?'
            r'class="result__snippet"[^>]*>(.*?)</(?:a|span|div)',
            html, re.DOTALL
        )
        
        for url, title, snippet in result_blocks[:max_results]:
            # HTML etiketlerini temizle
            title_clean = re.sub(r'<[^>]+>', '', title).strip()
            snippet_clean = re.sub(r'<[^>]+>', '', snippet).strip()
            
            if title_clean and snippet_clean:
                results.append({
                    "title": title_clean[:100],
                    "snippet": snippet_clean[:300],
                    "url": url,
                    "source": "Web",
                })
    
    except Exception as e:
        logger.warning("ddg_html_parse_error", error=str(e))
    
    return results


async def search_and_summarize(query: str) -> Optional[str]:
    """
    Arama yap ve sonuçları tek bir metin olarak özetle.
    Prompt'a eklenecek formatta döner.
    
    Args:
        query: Aranacak metin
    
    Returns:
        Formatlanmış arama sonuçları veya None
    """
    results = await search_web(query, max_results=3)
    
    if not results:
        return None
    
    text = "\n## 🌐 İnternet Araması Sonuçları:\n"
    for i, r in enumerate(results, 1):
        text += f"**{i}. {r['title']}**\n"
        text += f"{r['snippet']}\n"
        if r.get('url'):
            text += f"Kaynak: {r['url']}\n"
        text += "\n"
    
    text += "Bu bilgileri kullanarak yanıt ver, ama kaynağın internetten geldiğini belirt.\n"
    
    return text
