"""Sunucuda web search test — SCP ile yüklenip çalıştırılacak"""
import asyncio
import sys
sys.path.insert(0, "/opt/companyai")

from app.config import settings
print(f"SERPAPI_KEY: {settings.SERPAPI_KEY[:10]}..." if settings.SERPAPI_KEY else "SERPAPI_KEY: BOŞ")

from app.llm.web_search import search_web, search_and_summarize, _serpapi_configured
print(f"SerpAPI configured: {_serpapi_configured()}")

async def main():
    print("\n--- search_web('inegölde hava durumu') ---")
    results, rich_data = await search_web("inegölde hava durumu")
    print(f"Results count: {len(results)}")
    print(f"Rich data: {rich_data is not None}")
    
    if results:
        for i, r in enumerate(results[:3]):
            print(f"  [{i+1}] {r.get('title', '')[:60]} | {r.get('snippet', '')[:80]}")
    
    if rich_data:
        rd_list = rich_data if isinstance(rich_data, list) else [rich_data]
        for rd in rd_list:
            print(f"  Rich type: {rd.get('type')}")
            if rd.get("type") == "weather":
                print(f"  Sıcaklık: {rd.get('temperature')}")
                print(f"  Konum: {rd.get('location')}")
                print(f"  Durum: {rd.get('condition')}")

    print("\n--- search_and_summarize('inegölde bugün hava nasıl') ---")
    text, rich = await search_and_summarize("inegölde bugün hava nasıl")
    if text:
        print(f"Text length: {len(text)}")
        print(text[:500])
    else:
        print("TEXT: None — WEB ARAMA SONUÇ VERMEDİ!")
    
    if rich:
        print(f"Rich data count: {len(rich) if isinstance(rich, list) else 1}")

asyncio.run(main())
