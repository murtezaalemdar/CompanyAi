import asyncio, json, httpx
from app.config import settings

async def test():
    async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
        response = await client.get(
            "https://serpapi.com/search.json",
            params={
                "api_key": settings.SERPAPI_KEY,
                "engine": "google",
                "q": "ronjan baskı örneği",
                "num": 5,
                "hl": "tr",
                "gl": "tr",
                "safe": "active",
                "no_cache": "false",
            },
        )
        data = response.json()
    
    print("=== Top-level keys:", list(data.keys()))
    
    if "inline_images" in data:
        print("=== inline_images count:", len(data["inline_images"]))
        print(json.dumps(data["inline_images"][:2], ensure_ascii=False, indent=2))
    else:
        print("=== NO inline_images in response")
    
    if "images_results" in data:
        print("=== images_results count:", len(data["images_results"]))
    
    if "answer_box" in data:
        print("=== answer_box keys:", list(data["answer_box"].keys()))

asyncio.run(test())
