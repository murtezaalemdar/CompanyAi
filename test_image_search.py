import asyncio, json
from app.llm.web_search import search_web

async def test():
    results, rich_data = await search_web("ronjan baskı örneği")
    print("=== Results count:", len(results))
    if rich_data:
        for card in rich_data:
            print("=== Card type:", card.get("type"))
            if card.get("type") == "images":
                print("=== Image count:", len(card.get("images", [])))
                for img in card.get("images", [])[:3]:
                    print("  -", img.get("title", "")[:60])
                    print("    thumb:", img.get("thumbnail", "")[:80])
            elif card.get("type") == "weather":
                print("=== Weather:", card.get("location"), card.get("temperature"))
    else:
        print("=== Rich data: None")

asyncio.run(test())
