"""
Türkçe sohbet dataset'ini RAG vektör veritabanına yükle.
Bu sayede AI, semantic search ile en uygun sohbet örneklerini bulur.

Kullanım:
    python scripts/load_dataset_to_rag.py [--max 500]
"""

import sys
import os

# Proje köküne path ekle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.llm.chat_examples import load_dataset_to_rag, get_dataset_stats


def main():
    max_entries = 500
    
    # Komut satırı argümanı
    if "--max" in sys.argv:
        idx = sys.argv.index("--max")
        if idx + 1 < len(sys.argv):
            max_entries = int(sys.argv[idx + 1])
    
    print("=" * 50)
    print("🗃️  Türkçe Sohbet Dataset → RAG Yükleme")
    print("=" * 50)
    
    # Mevcut durum
    stats = get_dataset_stats()
    print(f"\n📊 Mevcut Durum:")
    print(f"  Kalıp kategorileri: {stats['pattern_categories']}")
    print(f"  Kalıp örnekleri: {stats['pattern_examples']}")
    print(f"  Dataset kayıtları: {stats['dataset_entries']}")
    
    print(f"\n🔄 RAG'a yükleniyor (max {max_entries} kayıt)...")
    
    result = load_dataset_to_rag(max_entries=max_entries)
    
    if result["success"]:
        print(f"\n✅ Başarılı!")
        print(f"  Toplam dataset: {result['total_dataset']}")
        print(f"  Kalite filtrelemesi: {result['quality_filtered']}")
        print(f"  RAG'a yüklenen: {result['loaded_to_rag']}")
        print(f"  Hatalar: {result['errors']}")
    else:
        print(f"\n❌ Hata: {result.get('error', 'Bilinmeyen')}")


if __name__ == "__main__":
    main()
