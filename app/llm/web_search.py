"""Web Arama Modülü — SerpAPI (Google) + DuckDuckGo Fallback

Kurumsal AI asistanın bilmediği konularda internetten güncel bilgi
bulmasını sağlar.

Öncelik sırası:
1. SerpAPI — Google sonuçları (SERPAPI_KEY varsa, ücretsiz 100/ay)
2. Google Custom Search API (GOOGLE_API_KEY + GOOGLE_CSE_ID varsa)
3. DuckDuckGo Instant Answer API (ücretsiz fallback)
4. DuckDuckGo HTML scraping (son çare)
"""

import httpx
import structlog
import re
from typing import List, Dict, Optional, Tuple

from app.config import settings

logger = structlog.get_logger()

# SerpAPI (Google sonuçları — ücretsiz 100 arama/ay)
SERPAPI_URL = "https://serpapi.com/search.json"

# Google Custom Search API (yedek)
GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

# DuckDuckGo (fallback)
DDG_API_URL = "https://api.duckduckgo.com/"
DDG_HTML_URL = "https://html.duckduckgo.com/html/"


def _serpapi_configured() -> bool:
    """SerpAPI anahtarı yapılandırılmış mı?"""
    return bool(settings.SERPAPI_KEY)


def _google_configured() -> bool:
    """Google API anahtarları yapılandırılmış mı?"""
    return bool(settings.GOOGLE_API_KEY and settings.GOOGLE_CSE_ID)


# ──────────────────────────────────────────────
# SerpAPI — Google Arama Sonuçları
# ──────────────────────────────────────────────

async def _search_serpapi(query: str, max_results: int = 5) -> Tuple[List[Dict[str, str]], Optional[Dict]]:
    """
    SerpAPI ile Google arama sonuçlarını çeker.
    
    Ücretsiz plan: 250 arama/ay, kredi kartı gerektirmez.
    Döküman: https://serpapi.com/search-api
    
    Returns:
        (results, rich_data) — rich_data hava durumu gibi yapısal veri içerir
    """
    results = []
    rich_data = None
    
    try:
        async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
            response = await client.get(
                SERPAPI_URL,
                params={
                    "api_key": settings.SERPAPI_KEY,
                    "engine": "google",
                    "q": query,
                    "num": min(max_results, 10),
                    "hl": "tr",  # Türkçe arayüz
                    "gl": "tr",  # Türkiye bölgesi
                    "safe": "active",
                    "no_cache": "false",  # Cache kullan (kota tasarrufu)
                },
            )
            response.raise_for_status()
            data = response.json()
        
        # Organik sonuçlar
        for item in data.get("organic_results", [])[:max_results]:
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "url": item.get("link", ""),
                "source": "Google (SerpAPI)",
            })
        
        # Answer box — yapısal veri çıkarma
        answer_box = data.get("answer_box", {})
        if answer_box:
            # Hava durumu sonucu
            ab_type = answer_box.get("type", "")
            if ab_type == "weather_result" or "temperature" in answer_box:
                rich_data = _extract_weather_data(answer_box, data)
                logger.info("serpapi_weather_detected", location=rich_data.get("location", ""))
            
            # Metin answer box
            if answer_box.get("snippet") or answer_box.get("answer"):
                answer_text = answer_box.get("snippet") or answer_box.get("answer", "")
                results.insert(0, {
                    "title": answer_box.get("title", "Google Yanıt"),
                    "snippet": answer_text[:500],
                    "url": answer_box.get("link", ""),
                    "source": "Google Answer Box",
                })
        
        # Knowledge graph varsa ekle
        knowledge = data.get("knowledge_graph", {})
        if knowledge and knowledge.get("description"):
            results.append({
                "title": knowledge.get("title", ""),
                "snippet": knowledge.get("description", "")[:500],
                "url": knowledge.get("source", {}).get("link", ""),
                "source": "Google Knowledge Graph",
            })
        
        logger.info("serpapi_search_ok", query=query[:80], results=len(results),
                    has_rich_data=rich_data is not None)
        
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 429:
            logger.warning("serpapi_quota_exceeded", query=query[:60])
        elif status == 401:
            logger.error("serpapi_key_invalid")
        else:
            logger.error("serpapi_http_error", status=status)
        
    except Exception as e:
        logger.error("serpapi_error", error=str(e))
    
    return results, rich_data


def _extract_weather_data(answer_box: dict, full_data: dict) -> Dict:
    """SerpAPI answer_box'tan hava durumu verisini yapısal olarak çıkar."""
    # Hava durumu koşulunu Türkçeye çevir
    WEATHER_TR = {
        "Sunny": "Güneşli", "Clear": "Açık", "Partly cloudy": "Parçalı Bulutlu",
        "Cloudy": "Bulutlu", "Overcast": "Kapalı", "Rainy": "Yağmurlu",
        "Light rain": "Hafif Yağmur", "Heavy rain": "Şiddetli Yağmur",
        "Thunderstorm": "Gök Gürültülü Fırtına", "Snowy": "Karlı",
        "Light snow": "Hafif Kar", "Heavy snow": "Yoğun Kar",
        "Foggy": "Sisli", "Windy": "Rüzgarlı", "Haze": "Puslu",
        "Mist": "Sisli", "Drizzle": "Çisenti", "Sleet": "Sulu Kar",
        # Türkçe gelen değerler (SerpAPI hl=tr)
        "Güneşli": "Güneşli", "Açık": "Açık", "Parçalı bulutlu": "Parçalı Bulutlu",
        "Bulutlu": "Bulutlu", "Kapalı": "Kapalı", "Yağmurlu": "Yağmurlu",
        "Hafif yağmurlu": "Hafif Yağmurlu", "Çok bulutlu": "Çok Bulutlu",
        "Şiddetli yağmurlu": "Şiddetli Yağmur", "Gök gürültülü fırtına": "Gök Gürültülü Fırtına",
        "Karlı": "Karlı", "Hafif kar": "Hafif Kar", "Yoğun kar": "Yoğun Kar",
        "Sisli": "Sisli", "Rüzgarlı": "Rüzgarlı", "Puslu": "Puslu",
        "Çisenti": "Çisenti", "Sulu kar": "Sulu Kar",
    }
    
    # Hava durumu ikonunu belirle
    WEATHER_ICONS = {
        "Sunny": "☀️", "Clear": "☀️", "Partly cloudy": "⛅",
        "Cloudy": "☁️", "Overcast": "☁️", "Rainy": "🌧️",
        "Light rain": "🌦️", "Heavy rain": "🌧️", "Thunderstorm": "⛈️",
        "Snowy": "🌨️", "Light snow": "🌨️", "Heavy snow": "❄️",
        "Foggy": "🌫️", "Windy": "💨", "Haze": "🌫️",
        "Mist": "🌫️", "Drizzle": "🌦️", "Sleet": "🌨️",
        # Türkçe gelen değerler (SerpAPI hl=tr)
        "Güneşli": "☀️", "Açık": "☀️", "Parçalı bulutlu": "⛅",
        "Bulutlu": "☁️", "Kapalı": "☁️", "Yağmurlu": "🌧️",
        "Hafif yağmurlu": "🌦️", "Çok bulutlu": "☁️",
        "Şiddetli yağmurlu": "🌧️", "Gök gürültülü fırtına": "⛈️",
        "Karlı": "🌨️", "Hafif kar": "🌨️", "Yoğun kar": "❄️",
        "Sisli": "🌫️", "Rüzgarlı": "💨", "Puslu": "🌫️",
        "Çisenti": "🌦️", "Sulu kar": "🌨️",
    }
    
    weather_en = answer_box.get("weather", "")
    condition_tr = WEATHER_TR.get(weather_en, weather_en)
    icon = WEATHER_ICONS.get(weather_en, "🌡️")
    
    # Haftalık tahmin
    forecast = []
    for day in answer_box.get("forecast", []):
        day_weather = day.get("weather", "")
        forecast.append({
            "day": day.get("day", ""),
            "high": day.get("temperature", {}).get("high", day.get("high", "")),
            "low": day.get("temperature", {}).get("low", day.get("low", "")),
            "condition": WEATHER_TR.get(day_weather, day_weather),
            "icon": WEATHER_ICONS.get(day_weather, "🌡️"),
        })
    
    return {
        "type": "weather",
        "location": answer_box.get("location", ""),
        "temperature": answer_box.get("temperature", ""),
        "unit": answer_box.get("unit", "Celsius"),
        "condition": condition_tr,
        "condition_icon": icon,
        "precipitation": answer_box.get("precipitation", ""),
        "humidity": answer_box.get("humidity", ""),
        "wind": answer_box.get("wind", ""),
        "date": answer_box.get("date", ""),
        "forecast": forecast,
        "source": "Google Hava Durumu",
    }


# ──────────────────────────────────────────────
# Google Custom Search API (yedek)
# ──────────────────────────────────────────────

async def _search_google(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Google Custom Search JSON API ile arama yapar.
    Billing hesabı gerektirir.
    """
    results = []
    
    try:
        async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
            response = await client.get(
                GOOGLE_SEARCH_URL,
                params={
                    "key": settings.GOOGLE_API_KEY,
                    "cx": settings.GOOGLE_CSE_ID,
                    "q": query,
                    "num": min(max_results, 10),
                    "lr": "lang_tr",
                    "gl": "tr",
                    "safe": "active",
                },
            )
            response.raise_for_status()
            data = response.json()
        
        for item in data.get("items", []):
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "url": item.get("link", ""),
                "source": "Google",
            })
        
        logger.info("google_search_ok", query=query[:80], results=len(results))
        
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 429:
            logger.warning("google_quota_exceeded", query=query[:60])
        elif status == 403:
            logger.error("google_api_key_invalid")
        else:
            logger.error("google_search_http_error", status=status)
        
    except Exception as e:
        logger.error("google_search_error", error=str(e))
    
    return results


# ──────────────────────────────────────────────
# DuckDuckGo (Fallback)
# ──────────────────────────────────────────────

async def _search_ddg_instant(query: str) -> List[Dict[str, str]]:
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


async def _search_ddg_html(query: str, max_results: int = 3) -> List[Dict[str, str]]:
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
        
        result_blocks = re.findall(
            r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?'
            r'class="result__snippet"[^>]*>(.*?)</(?:a|span|div)',
            html, re.DOTALL
        )
        
        for url, title, snippet in result_blocks[:max_results]:
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


# ──────────────────────────────────────────────
# Ana Arama Fonksiyonu
# ──────────────────────────────────────────────

async def search_web(query: str, max_results: int = 5) -> Tuple[List[Dict[str, str]], Optional[Dict]]:
    """
    Web araması yapar. Öncelik sırasına göre dener:
    
    1. SerpAPI (Google sonuçları — ücretsiz 250/ay)
    2. Google Custom Search API (billing gerektirir)
    3. DuckDuckGo Instant API (ücretsiz fallback)
    4. DuckDuckGo HTML scraping (son çare)
    
    Returns:
        (results, rich_data) — rich_data hava durumu gibi görsel kart verisi
    """
    results = []
    rich_data = None
    search_engine = "none"
    
    # 1) SerpAPI — Google sonuçları (en kaliteli)
    if _serpapi_configured():
        results, rich_data = await _search_serpapi(query, max_results)
        if results:
            search_engine = "serpapi"
    
    # 2) Google Custom Search (yedek — billing gerektiriyor)
    if not results and _google_configured():
        results = await _search_google(query, max_results)
        if results:
            search_engine = "google"
    
    # 3) DuckDuckGo Instant (fallback)
    if not results:
        try:
            results = await _search_ddg_instant(query)
            if results:
                search_engine = "duckduckgo_instant"
        except Exception as e:
            logger.warning("ddg_instant_failed", error=str(e))
    
    # 4) DuckDuckGo HTML (son çare)
    if len(results) < 2:
        try:
            html_results = await _search_ddg_html(query, max_results - len(results))
            results.extend(html_results)
            if html_results and search_engine == "none":
                search_engine = "duckduckgo_html"
        except Exception as e:
            logger.warning("ddg_html_failed", error=str(e))
    
    logger.info("web_search_complete", 
                query=query[:80], 
                engine=search_engine,
                results_count=len(results),
                has_rich_data=rich_data is not None)
    
    return results[:max_results], rich_data


async def search_and_summarize(query: str) -> Tuple[Optional[str], Optional[Dict]]:
    """
    Arama yap ve sonuçları LLM prompt'una eklenecek formatta döndür.
    
    Returns:
        (text_summary, rich_data) — rich_data hava durumu gibi görsel kart verisi
    """
    results, rich_data = await search_web(query, max_results=5)
    
    if not results:
        return None, rich_data
    
    # Hangi motor kullanıldı?
    engine = results[0].get("source", "Web")
    
    text = f"\n## 🌐 İnternet Araması Sonuçları ({engine}):\n"
    for i, r in enumerate(results, 1):
        text += f"**{i}. {r['title']}**\n"
        text += f"{r['snippet']}\n"
        if r.get('url'):
            text += f"Kaynak: {r['url']}\n"
        text += "\n"
    
    text += "Bu bilgileri kullanarak yanıt ver. Kaynağın internetten geldiğini belirt.\n"
    
    return text, rich_data
