"""Embedding Model Fine-Tune Pipeline — Tekstil Sektörü

Mevcut paraphrase-multilingual-mpnet-base-v2 modelini
tekstil terminolojisi ve şirket dokümanlarıyla fine-tune eder.

Kullanım:
    python -m app.scripts.finetune_embeddings --generate   # Eğitim verisini oluştur
    python -m app.scripts.finetune_embeddings --train       # Fine-tune başlat
    python -m app.scripts.finetune_embeddings --evaluate    # Değerlendir

Gereksinimler:
    pip install sentence-transformers datasets
"""

import os
import json
import argparse
import random
from pathlib import Path
from typing import List, Tuple

# ══════════════════════════════════════════════════════════════
# 1. TEKSTİL TERMİNOLOJİ VERİ SETİ
# ══════════════════════════════════════════════════════════════

# Anchor-Positive çiftleri: Anlam olarak benzer olması gereken cümle çiftleri
# Fine-tune sonrası bu çiftlerin embedding'leri daha yakın olmalı
TEXTILE_PAIRS = [
    # Fire / Atık
    ("Fire oranı nedir?", "Üretim atık yüzdesi nedir?"),
    ("Fire oranımız %3.5", "Atık oranımız yüzde 3.5 seviyesinde"),
    ("Kumaş firesi düşürme yolları", "Tekstil atık azaltma stratejileri"),
    ("Fire maliyeti nasıl hesaplanır?", "Üretim kayıp maliyeti formülü"),
    ("Kesim kayıpları çok yüksek", "Kesim sürecinde fire oranı fazla"),
    
    # OEE / Verimlilik
    ("OEE nasıl hesaplanır?", "Overall Equipment Effectiveness formülü"),
    ("OEE %72 iyi mi?", "Genel Ekipman Verimliliği yüzde 72 yeterli mi?"),
    ("Makine verimliliği düşük", "Ekipman etkinliği yetersiz"),
    ("Üretim hattı performansı", "Hat bazlı çıktı verimliliği"),
    ("Duruş süresi analizi", "Arıza kaynaklı üretim kaybı"),
    
    # Kalite
    ("2. kalite oran artışı", "B-grade ürün oranı yükseldi"),
    ("Kalite kontrol sonuçları", "KK test raporları"),
    ("Kumaş hata tipleri", "Tekstil kusur sınıflandırması"),
    ("Gramaj sapması", "Kumaş ağırlık tolerans aşımı"),
    ("Çekmezlik testi", "Shrinkage test sonuçları"),
    ("Haslık değerleri", "Renk haslık test sonuçları"),
    ("Pilling testi", "Boncuklanma dayanım skoru"),
    
    # Üretim
    ("Üretim planı", "Aylık imalat programı"),
    ("Sipariş teslimat gecikmeleri", "Müşteri siparişi termin aşımı"),
    ("Lot takibi", "Parti izlenebilirlik"),
    ("Makinede duruş", "Üretim hattı durağanlığı"),
    ("Dokuma hızı ayarı", "Tezgah çalışma hızı optimizasyonu"),
    ("Boyahane kapasitesi", "Boya tesisi üretim yeteneği"),
    
    # Maliyet / Finans
    ("Hammadde maliyeti arttı", "İplik fiyatları yükseldi"),
    ("Brüt kâr marjı", "Brüt kar marjı oranı"),
    ("İşçilik maliyeti", "Personel giderleri"),
    ("Enerji giderleri analizi", "Elektrik ve doğalgaz maliyet incelemesi"),
    ("Yatırım geri dönüş süresi", "ROI hesaplaması"),
    
    # Risk / Strateji
    ("Tedarik zinciri riski", "Tedarikçi kaynaklı risk faktörleri"),
    ("Pazar riski analizi", "Piyasa dalgalanma risk değerlendirmesi"),
    ("Rekabet analizi", "Rakip firma kıyaslaması"),
    ("SWOT analizi yapılmalı", "Güçlü/zayıf yönler ve fırsat/tehdit değerlendirmesi"),
    
    # Departman
    ("İK departmanı raporu", "İnsan kaynakları bölüm raporu"),
    ("Satış hedefi tutturma oranı", "Ciro hedef gerçekleştirme yüzdesi"),
    ("Proses mühendisliği", "Süreç iyileştirme mühendisliği"),
    
    # Sektör Spesifik
    ("Ne/dtex değeri", "Numaralama iplik inceliği"),
    ("Lif kompozisyon oranı", "Karışım oranı yüzdesi"),
    ("Merserize sürecinde sorun", "Merserizasyon prosesinde problem"),
    ("Apre işlemi maliyeti", "Terbiye sonlandırma gideri"),
    ("Çözgü kopması", "Warp breakage oranı"),
    ("Atkı sıklığı", "Weft density ayarı"),
]

# Negatif örnekler: Bunlar birbirine benzer OLMAMALI
HARD_NEGATIVES = [
    ("Fire oranı nedir?", "Bugün hava nasıl?"),
    ("OEE hesaplama", "Yemek tarifi önerisi"),
    ("Kumaş kalite kontrolü", "Futbol maçı sonucu"),
    ("Üretim planı", "Tatil rezervasyonu"),
    ("Maliyet analizi", "Film önerisi"),
]


# ══════════════════════════════════════════════════════════════
# 2. EĞİTİM VERİSİ OLUŞTUR
# ══════════════════════════════════════════════════════════════

def generate_training_data(output_dir: str = "data/embedding_training") -> str:
    """Eğitim verisini oluştur ve dosyaya yaz."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Triplet format: (anchor, positive, negative)
    triplets = []
    
    for anchor, positive in TEXTILE_PAIRS:
        # Her pozitif çift için rastgele bir negatif seç
        neg_candidates = [p for a, p in TEXTILE_PAIRS if a != anchor]
        neg_candidates += [n for _, n in HARD_NEGATIVES]
        negative = random.choice(neg_candidates)
        
        triplets.append({
            "anchor": anchor,
            "positive": positive,
            "negative": negative,
        })
        
        # Ters yönü de ekle (positive → anchor, farklı negatif)
        negative2 = random.choice(neg_candidates)
        triplets.append({
            "anchor": positive,
            "positive": anchor,
            "negative": negative2,
        })
    
    # ChromaDB'deki mevcut dokümanlardan ek çiftler
    try:
        from app.rag.vector_store import get_collection
        collection = get_collection()
        if collection and collection.count() > 0:
            all_docs = collection.get(include=["documents", "metadatas"])
            if all_docs and all_docs.get("documents"):
                docs = all_docs["documents"]
                # Aynı source'tan gelen chunk'lar benzer olmalı
                source_groups = {}
                for i, doc in enumerate(docs):
                    meta = all_docs["metadatas"][i] if all_docs.get("metadatas") else {}
                    src = meta.get("source", f"unk_{i}")
                    if src not in source_groups:
                        source_groups[src] = []
                    source_groups[src].append(doc[:200])
                
                for src, chunks in source_groups.items():
                    if len(chunks) >= 2:
                        for j in range(min(3, len(chunks) - 1)):
                            neg_src = random.choice([c for s, cs in source_groups.items() 
                                                    if s != src for c in cs] or ["Alakasız metin."])
                            triplets.append({
                                "anchor": chunks[j][:200],
                                "positive": chunks[j+1][:200],
                                "negative": neg_src[:200],
                            })
                print(f"  ChromaDB'den {len(source_groups)} kaynak grubundan ek çiftler eklendi")
    except Exception as e:
        print(f"  ChromaDB okunamadı (normal — sunucuda çalıştırılmalı): {e}")
    
    # Shuffle
    random.shuffle(triplets)
    
    # Train/Eval split
    split_idx = int(len(triplets) * 0.85)
    train_data = triplets[:split_idx]
    eval_data = triplets[split_idx:]
    
    # Dosyalara yaz
    train_path = os.path.join(output_dir, "train_triplets.json")
    eval_path = os.path.join(output_dir, "eval_triplets.json")
    
    with open(train_path, "w", encoding="utf-8") as f:
        json.dump(train_data, f, ensure_ascii=False, indent=2)
    
    with open(eval_path, "w", encoding="utf-8") as f:
        json.dump(eval_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Eğitim verisi oluşturuldu:")
    print(f"   Train: {len(train_data)} triplet → {train_path}")
    print(f"   Eval:  {len(eval_data)} triplet → {eval_path}")
    
    return train_path


# ══════════════════════════════════════════════════════════════
# 3. FINE-TUNE
# ══════════════════════════════════════════════════════════════

def train_embedding_model(
    train_path: str = "data/embedding_training/train_triplets.json",
    eval_path: str = "data/embedding_training/eval_triplets.json",
    output_model: str = "models/textile-mpnet-v1",
    epochs: int = 3,
    batch_size: int = 16,
):
    """SentenceTransformer fine-tune.
    
    TripletLoss ile eğitir:
    - Pozitif çiftlerin embedding'lerini yakınlaştırır
    - Negatif çiftlerin embedding'lerini uzaklaştırır
    """
    from sentence_transformers import SentenceTransformer, InputExample, losses
    from torch.utils.data import DataLoader
    
    # Base model yükle
    base_model = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    print(f"📦 Base model yükleniyor: {base_model}")
    model = SentenceTransformer(base_model)
    
    # Eğitim verisini yükle
    with open(train_path, "r", encoding="utf-8") as f:
        train_data = json.load(f)
    
    # InputExample formatına çevir
    train_examples = []
    for item in train_data:
        train_examples.append(InputExample(
            texts=[item["anchor"], item["positive"], item["negative"]]
        ))
    
    # DataLoader
    train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=batch_size)
    
    # TripletLoss — margin=0.5 ile benzer ve farklı ifadeleri ayır
    train_loss = losses.TripletLoss(model=model, distance_metric=losses.TripletDistanceMetric.COSINE, triplet_margin=0.5)
    
    # Evaluation (opsiyonel)
    evaluator = None
    if os.path.exists(eval_path):
        from sentence_transformers.evaluation import TripletEvaluator
        with open(eval_path, "r", encoding="utf-8") as f:
            eval_data = json.load(f)
        
        anchors = [d["anchor"] for d in eval_data]
        positives = [d["positive"] for d in eval_data]
        negatives = [d["negative"] for d in eval_data]
        evaluator = TripletEvaluator(anchors, positives, negatives, name="textile_eval")
    
    # Fine-tune
    print(f"🚀 Fine-tune başlatılıyor...")
    print(f"   Epochs: {epochs}, Batch: {batch_size}, Samples: {len(train_examples)}")
    
    model.fit(
        train_objectives=[(train_dataloader, train_loss)],
        epochs=epochs,
        warmup_steps=int(len(train_dataloader) * 0.1),
        evaluator=evaluator,
        evaluation_steps=50,
        output_path=output_model,
        show_progress_bar=True,
    )
    
    print(f"✅ Fine-tuned model kaydedildi: {output_model}")
    print(f"   ⚡ Kullanmak için vector_store.py'deki EMBEDDING_MODEL'i değiştir:")
    print(f'   EMBEDDING_MODEL = "{output_model}"')
    
    return output_model


# ══════════════════════════════════════════════════════════════
# 4. DEĞERLENDİRME
# ══════════════════════════════════════════════════════════════

def evaluate_model(model_path: str = None):
    """Fine-tuned model vs base model karşılaştırması."""
    from sentence_transformers import SentenceTransformer
    import numpy as np
    
    base_model_name = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    fine_tuned_path = model_path or "models/textile-mpnet-v1"
    
    print("📊 Model değerlendirmesi...")
    
    # Her iki modeli de yükle
    base_model = SentenceTransformer(base_model_name)
    fine_model = SentenceTransformer(fine_tuned_path)
    
    # Test çiftleri
    test_pairs = TEXTILE_PAIRS[:15]  # İlk 15 çift
    
    print(f"\n{'Çift':<50} {'Base':>8} {'FT':>8} {'Δ':>8}")
    print("-" * 80)
    
    base_scores = []
    ft_scores = []
    
    for anchor, positive in test_pairs:
        # Base model similarity
        base_emb = base_model.encode([anchor, positive])
        base_sim = float(np.dot(base_emb[0], base_emb[1]) / 
                        (np.linalg.norm(base_emb[0]) * np.linalg.norm(base_emb[1])))
        
        # Fine-tuned model similarity
        ft_emb = fine_model.encode([anchor, positive])
        ft_sim = float(np.dot(ft_emb[0], ft_emb[1]) / 
                       (np.linalg.norm(ft_emb[0]) * np.linalg.norm(ft_emb[1])))
        
        delta = ft_sim - base_sim
        base_scores.append(base_sim)
        ft_scores.append(ft_sim)
        
        arrow = "↑" if delta > 0 else "↓"
        print(f"{anchor[:25]} ↔ {positive[:20]:<20} {base_sim:>7.4f} {ft_sim:>7.4f} {arrow}{abs(delta):>6.4f}")
    
    avg_base = sum(base_scores) / len(base_scores)
    avg_ft = sum(ft_scores) / len(ft_scores)
    improvement = ((avg_ft - avg_base) / avg_base) * 100
    
    print(f"\n{'Ortalama':<50} {avg_base:>7.4f} {avg_ft:>7.4f} {'↑' if improvement > 0 else '↓'}{abs(improvement):.1f}%")
    print(f"\n{'✅ Fine-tuned model daha iyi!' if improvement > 0 else '⚠️ Base model daha iyi — daha fazla veri gerekli.'}")


# ══════════════════════════════════════════════════════════════
# 5. CLI
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Embedding Model Fine-Tune Pipeline")
    parser.add_argument("--generate", action="store_true", help="Eğitim verisini oluştur")
    parser.add_argument("--train", action="store_true", help="Fine-tune başlat")
    parser.add_argument("--evaluate", action="store_true", help="Model değerlendirmesi")
    parser.add_argument("--epochs", type=int, default=3, help="Eğitim epoch sayısı")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch boyutu")
    parser.add_argument("--model-path", type=str, default="models/textile-mpnet-v1", help="Model kayıt yolu")
    
    args = parser.parse_args()
    
    if args.generate:
        generate_training_data()
    elif args.train:
        train_path = "data/embedding_training/train_triplets.json"
        if not os.path.exists(train_path):
            print("⚠️ Eğitim verisi bulunamadı. Önce --generate çalıştırın.")
            generate_training_data()
        train_embedding_model(epochs=args.epochs, batch_size=args.batch_size, 
                            output_model=args.model_path)
    elif args.evaluate:
        evaluate_model(args.model_path)
    else:
        parser.print_help()
