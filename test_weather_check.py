import asyncio, json
from app.llm.web_search import search_web

async def test():
    results, rich_data = await search_web("İnegöl hava durumu")
    print("=== Results count:", len(results))
    if rich_data:
        for card in rich_data:
            print("=== Card type:", card.get("type"))
            if card.get("type") == "weather":
                print("  Location:", card.get("location"))
                print("  Temp:", card.get("temperature"), card.get("unit"))
                print("  Condition:", card.get("condition"), card.get("condition_icon"))
            elif card.get("type") == "images":
                print("  Image count:", len(card.get("images", [])))
    else:
        print("=== Rich data: None")

asyncio.run(test())
