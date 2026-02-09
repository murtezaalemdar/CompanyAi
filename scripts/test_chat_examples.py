"""Sohbet örnekleri test scripti"""
import sys
sys.path.insert(0, "/opt/companyai")

from app.llm.chat_examples import get_pattern_response, get_few_shot_examples, get_dataset_stats
import json

# İstatistikler
stats = get_dataset_stats()
print("=== DATASET İSTATİSTİKLERİ ===")
print(json.dumps(stats, ensure_ascii=False, indent=2))

# Kalıp eşleşme testleri
print("\n=== KALIP EŞLEŞMESİ TESTLERİ ===")
tests = ["Merhaba", "Nasılsın?", "Teşekkürler", "Sen kimsin?", "Canım sıkılıyor"]
for t in tests:
    resp = get_pattern_response(t)
    display = resp[:80] if resp else "(eşleşme yok)"
    print(f"  {t} -> {display}")

# Few-shot test
print("\n=== FEW-SHOT ÖRNEKLER ===")
ex = get_few_shot_examples("Bugün hava nasıl?", count=2)
print(ex[:400] if ex else "(örnek bulunamadı)")
