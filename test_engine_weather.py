"""End-to-end test: process_question with weather query"""
import asyncio
import sys
sys.path.insert(0, "/opt/companyai")

from app.core.engine import process_question

async def main():
    print("Testing: inegolde bugun hava nasil")
    r = await process_question("inegolde bugun hava nasil")
    print(f"web_searched: {r.get('web_searched')}")
    print(f"rich_data: {r.get('rich_data')}")
    print(f"intent: {r.get('intent')}")
    print(f"sources: {r.get('sources')}")
    answer = r.get("answer", "")
    print(f"answer ({len(answer)} chars): {answer[:300]}")

asyncio.run(main())
