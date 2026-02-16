"""Sunucuda RAG diagnostic testi"""
import paramiko
import sys

HOST = "88.246.13.23"
PORT = 2013
USER = "root"
PASS = "Kc435102mn"

REMOTE_SCRIPT = r'''
import sys, json
sys.path.insert(0, "/opt/companyai")
from app.rag.vector_store import get_stats, search_documents, get_collection
from app.router.router import decide

# 1) RAG istatistikleri
stats = get_stats()
print("=== RAG STATS ===")
print(json.dumps(stats, ensure_ascii=False, indent=2))

# 2) Koleksiyonda ne var?
col = get_collection()
if col:
    count = col.count()
    print(f"\nKoleksiyon document sayisi: {count}")
    if count > 0:
        peek = col.peek(5)
        print("\n=== ORNEK DOKUMANLAR ===")
        for i in range(min(5, len(peek["documents"]))):
            doc = peek["documents"][i][:150]
            meta = peek["metadatas"][i] if peek["metadatas"] else {}
            print(f"Doc {i}: [{meta}] {doc}...")

# 3) Cesitli arama testleri
TEST_QUERIES = [
    "sirket hakkinda bilgi ver",
    "firmamiz ne is yapiyor",
    "katalog",
    "urunlerimiz nelerdir",
    "sirket katalogu",
]

print("\n=== ARAMA TESTLERI ===")
for q in TEST_QUERIES:
    results = search_documents(q, n_results=5)
    # Router testi
    ctx = decide(q)
    print(f"\nSorgu: '{q}'")
    print(f"  Router: intent={ctx['intent']}, mode={ctx['mode']}, dept={ctx['dept']}")
    print(f"  RAG sonuc: {len(results)} dokuman")
    for r in results:
        print(f"    dist={r.get('distance','?'):.4f} rel={r.get('relevance','?'):.4f} src={r.get('source','?')} => {r.get('content','')[:80]}...")

# 4) is_statement testi
import re
for q in TEST_QUERIES:
    is_statement = not any(c in q for c in "??") and len(q.split()) < 10
    ctx = decide(q)
    skip_rag = ctx["intent"] == "sohbet" or is_statement
    print(f"\n  '{q}' => is_statement={is_statement}, intent={ctx['intent']}, RAG_SKIP={skip_rag}")
'''

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

cmd = f'/opt/companyai/venv/bin/python -c "{REMOTE_SCRIPT}"'
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
print(stdout.read().decode("utf-8", errors="replace"))
err = stderr.read().decode("utf-8", errors="replace")
if err:
    print("STDERR:", err[:2000])
ssh.close()
