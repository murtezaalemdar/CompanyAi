#!/usr/bin/env python3
"""Server 2'de RAG testi - dogrudan sunucuda calistirilacak"""
import sys, os
sys.path.insert(0, '/opt/companyai')
os.chdir('/opt/companyai')

import json

# 1) ChromaDB durumu
print("=" * 60)
print("1) CHROMADB DURUMU")
print("=" * 60)
try:
    import chromadb
    client = chromadb.PersistentClient(path='/opt/companyai/data/chromadb')
    cols = client.list_collections()
    print(f"Koleksiyon sayisi: {len(cols)}")
    for c in cols:
        col = client.get_collection(c.name)
        cnt = col.count()
        print(f"  {c.name}: {cnt} dokuman")
        if cnt > 0:
            peek = col.peek(3)
            docs = peek.get('documents', [])
            metas = peek.get('metadatas', [])
            for i, doc in enumerate(docs):
                meta = metas[i] if i < len(metas) else {}
                print(f"    [{i}] {doc[:120]}...")
                print(f"        meta: {meta}")
except Exception as e:
    print(f"HATA: {e}")

# 2) RAG arama testi
print("\n" + "=" * 60)
print("2) RAG ARAMA TESTI")
print("=" * 60)
try:
    from app.rag.vector_store import search_documents, get_stats
    stats = get_stats()
    print(f"RAG Stats: {json.dumps(stats, ensure_ascii=False)}")
    
    queries = [
        "sirket hakkinda bilgi ver",
        "katalog",
        "urunler nelerdir",
        "firma ne is yapar",
    ]
    for q in queries:
        print(f"\n  Sorgu: '{q}'")
        results = search_documents(q, n_results=5)
        print(f"  Sonuc sayisi: {len(results)}")
        for r in results:
            dist = r.get('distance', '?')
            rel = r.get('relevance', '?')
            src = r.get('source', '?')
            content = r.get('content', '')[:80]
            print(f"    dist={dist:.3f} rel={rel:.3f} src={src} | {content}...")
except Exception as e:
    print(f"HATA: {e}")
    import traceback
    traceback.print_exc()

# 3) Router testi
print("\n" + "=" * 60)
print("3) ROUTER INTENT TESTI")
print("=" * 60)
try:
    from app.router.router import SmartRouter
    router = SmartRouter()
    test_questions = [
        "sirket hakkinda bilgi ver",
        "katalogumuzdaki urunler neler",
        "firmamiz ne zaman kuruldu",
        "yukludigim dokumanlar hakkinda bilgi ver",
        "kumas cesitlerimiz nelerdir",
        "merhabalar nasilsiniz",
    ]
    for q in test_questions:
        result = router.route(q, department="Genel")
        intent = result.get('intent', '?')
        conf = result.get('confidence', '?')
        print(f"  '{q}' => intent={intent}, confidence={conf}")
except Exception as e:
    print(f"HATA: {e}")
    import traceback
    traceback.print_exc()

# 4) is_statement testi
print("\n" + "=" * 60)
print("4) IS_STATEMENT TESTI")
print("=" * 60)
test_qs = [
    "sirket hakkinda bilgi ver",
    "katalogumuzdaki urunler neler",
    "firmamiz ne zaman kuruldu?",
    "merhabalar nasilsiniz",
    "uretim plani hakkinda detay ver",
    "nedir bu sirketin amaci",
]
for q in test_qs:
    is_stmt = not any(c in q for c in "??") and len(q.split()) < 10
    print(f"  '{q}' ({len(q.split())} kelime, '?' var mi: {'?' in q}) => is_statement={is_stmt}")

print("\n" + "=" * 60)
print("TAMAMLANDI")
print("=" * 60)
