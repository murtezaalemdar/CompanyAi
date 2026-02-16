"""LLM (Qwen2.5) Fine-Tune Pipeline — LoRA/QLoRA

Tekstil sektörü konuşma geçmişlerinden ve domain verilerinden
QLoRA fine-tune veri seti hazırlar ve Ollama Modelfile oluşturur.

Kullanım:
    python -m app.scripts.finetune_llm --extract      # Konuşmalardan eğitim verisi çıkar
    python -m app.scripts.finetune_llm --prepare       # Sektör eğitim seti hazırla
    python -m app.scripts.finetune_llm --modelfile     # Ollama Modelfile oluştur
    python -m app.scripts.finetune_llm --export-gguf   # Unsloth ile GGUF export script üret

Gereksinimler (eğitim için):
    pip install unsloth datasets transformers trl peft
"""

import os
import json
import argparse
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# ══════════════════════════════════════════════════════════════
# 1. TEKSTİL SEKTÖRÜ EĞİTİM VERİSİ
# ══════════════════════════════════════════════════════════════

TEXTILE_QA_DATASET = [
    # ── Fire / Atık Yönetimi ──
    {
        "instruction": "Fire oranı %4.2 olan bir tekstil fabrikası için analiz yap.",
        "input": "",
        "output": """## Fire Oranı Analizi

**Mevcut Durum**: Fire oranı %4.2 — Kabul Edilebilir seviyede ancak iyileştirme potansiyeli var.

### Benchmark Karşılaştırması
| Seviye | Aralık | Durum |
|--------|--------|-------|
| 🟢 İyi | <%2 | — |
| 🟡 Kabul Edilebilir | %2-5 | ← Sizin konumunuz |
| 🟠 Yüksek | %5-8 | — |
| 🔴 Kritik | >%8 | — |

### Fire Türü Dağılımı (Olası)
- **Kesim firesi**: ~%45 (en büyük kaynak)
- **Dokuma hatası**: ~%25
- **Boyama hatası**: ~%20
- **Diğer**: ~%10

### Maliyet Etkisi
Aylık 100 ton üretimde:
- Fire miktarı: 4.2 ton/ay
- Tahmini kayıp: ~₺210,000/ay (kg başı ₺50)
- Yıllık kayıp: ~₺2,520,000

### Aksiyon Planı
1. **Kısa vade (1 ay)**: Pareto analizi — en büyük fire kaynağını belirle
2. **Orta vade (3 ay)**: Kesim optimizasyonu ve nesting yazılımı
3. **Uzun vade (6 ay)**: AI destekli kalite kontrol sistemi

**Hedef**: %4.2 → %2.5 (6 ayda %40 azalma)
Tahmini tasarruf: ₺850,000/yıl"""
    },
    
    # ── OEE Analizi ──
    {
        "instruction": "Dokuma bölümü OEE değerlendirmesi yap. Kullanılabilirlik %88, performans %75, kalite %96.",
        "input": "",
        "output": """## OEE Analizi — Dokuma Bölümü

### Hesaplama
OEE = Kullanılabilirlik × Performans × Kalite
OEE = %88 × %75 × %96 = **%63.4**

### Seviye: 🟠 Orta
Dünya sınıfı OEE >%85, sektör ortalaması %65-75 arasındadır.

### Darboğaz Analizi
| Faktör | Değer | Benchmark | Durum |
|--------|-------|-----------|-------|
| Kullanılabilirlik | %88 | >%90 | 🟡 Yakın |
| **Performans** | **%75** | >%95 | 🔴 **DARBOĞAZ** |
| Kalite | %96 | >%99 | 🟡 İyi |

### Performans düşüklüğünün olası nedenleri
1. **Hız kayıpları**: Tezgahlar optimum hızın altında çalışıyor
2. **Mikro duruşlar**: Kayıt dışı kısa süreli duraksamalar
3. **Çözgü kopması**: Atkı/çözgü kopma kaynaklı yavaşlama

### İyileştirme Senaryoları
| Senaryo | Performans | OEE | Üretim Artışı |
|---------|-----------|-----|--------------|
| Mevcut | %75 | %63.4 | — |
| Performans %85 | %85 | %71.8 | +%13.3 |
| Performans %90 | %90 | %76.0 | +%19.9 |

### Aksiyon Önerileri
- **Hemen**: Tezgah bazlı hız analizi, yavaş makinelerin bakımı
- **1 ay**: Mikro duruş kayıt sistemi kurulumu
- **3 ay**: Predictive maintenance başlangıcı"""
    },
    
    # ── Maliyet Analizi ──
    {
        "instruction": "Hammadde maliyeti son çeyrekte %18 arttı. Etki analizi yap.",
        "input": "",
        "output": """## Hammadde Maliyet Artışı Etki Analizi

### Mevcut Durum
- Hammadde maliyet artışı: **%18** (son çeyrek)
- Sektör ortalaması artış: %8-12

⚠️ **Risk Seviyesi: YÜKSEK** — Sektör ortalamasının üzerinde maliyet artışı

### Finansal Etki (Aylık ₺10M ciro varsayımı)
| Kalem | Önceki | Güncel | Değişim |
|-------|--------|--------|---------|
| Hammadde maliyeti | ₺4,000,000 | ₺4,720,000 | +₺720,000 |
| Brüt kâr | ₺2,500,000 | ₺1,780,000 | -₺720,000 |
| Brüt kâr marjı | %25.0 | %17.8 | -7.2 puan |

### Risk Faktörleri
- 🔴 **Kâr marjı erimesi**: 7.2 puanlık düşüş sürdürülebilir değil
- 🟡 **Rekabet dezavantajı**: Fiyat artışı yapılamazsa pazar kaybı
- 🟡 **Nakit akışı**: Artan hammadde stok maliyeti

### Strateji Önerileri
1. **Fiyat ayarlaması**: Müşteri fiyatlarına %8-10 zam (kademeli)
2. **Alternatif tedarik**: En az 2 yeni tedarikçi değerlendirmesi
3. **Stok optimizasyonu**: 45 günlük stoktan 30 güne düşür
4. **Ürün karması**: Yüksek marjlı ürünlere yönel
5. **Verimlilik**: Fire oranını %1 düşürerek ₺100K/ay tasarruf

### Senaryo Tablosu
| Senaryo | Kâr Marjı | Aksiyon |
|---------|----------|---------|
| 🟢 Best Case | %22 | Fiyat artışı + verimlilik |
| 🟡 Expected | %19 | Kısmen fiyat artışı |
| 🔴 Worst Case | %15 | Hiçbir aksiyon yok |"""
    },
    
    # ── Risk Değerlendirmesi ──
    {
        "instruction": "Tedarik zinciri risk değerlendirmesi yap.",
        "input": "",
        "output": """## Tedarik Zinciri Risk Değerlendirmesi

### Risk Matrisi
| Risk | Olasılık | Etki | Skor | Seviye |
|------|----------|------|------|--------|
| Tedarikçi iflası | 2 | 5 | 10 | 🟡 Orta |
| Hammadde fiyat şoku | 4 | 4 | 16 | 🟠 Yüksek |
| Lojistik gecikme | 3 | 3 | 9 | 🟡 Orta |
| Kalite sapması | 3 | 4 | 12 | 🟠 Yüksek |
| Döviz kuru dalgalanması | 4 | 3 | 12 | 🟠 Yüksek |

### Kritik Riskler ve Aksiyonlar

**1. Hammadde Fiyat Şoku (Skor: 16)**
- Risk: İplik/kumaş fiyatlarında ani artış
- Azaltma: Vadeli kontratlar, minimum 2 tedarikçi
- Süre: Hemen başla - Sorumlu: Satınalma Müdürü

**2. Kalite Sapması (Skor: 12)**
- Risk: Gelen hammaddede kalite düşüşü
- Azaltma: Giriş kalite kontrol sıkılaştır, tedarikçi audit
- Süre: 2 hafta - Sorumlu: Kalite Müdürü

**3. Döviz Kuru (Skor: 12)**
- Risk: TL değer kaybıyla ithal girdi maliyeti artışı
- Azaltma: Doğal hedge, yerli tedarikçi geliştirme
- Süre: Sürekli - Sorumlu: Finans Müdürü

### Toplam Risk Skoru: **59/125** — Orta-Yüksek
Aksiyon planı uygulanmazsa 3 ay içinde finansal etki: **₺500K-1.2M**"""
    },
    
    # ── Sohbet / Türkçe doğal dil ──
    {
        "instruction": "Merhaba, nasılsın?",
        "input": "",
        "output": "Merhaba! Ben CompanyAI, şirketinizin yapay zeka asistanıyım. İyi bir gün geçiriyorum, size nasıl yardımcı olabilirim? Üretim verileri, maliyet analizi, risk değerlendirmesi veya herhangi bir konuda sorularınızı yanıtlamaya hazırım."
    },
    {
        "instruction": "Beni tanıyor musun?",
        "input": "",
        "output": "Elbette! Sistemdeki kullanıcı profilinizi ve önceki konuşmalarımızı hatırlıyorum. Her konuşmamızda sizin için daha kişiselleştirilmiş yanıtlar üretebiliyorum. Departmanınıza ve ilgi alanlarınıza göre analizlerimi özelleştiriyorum."
    },
    
    # ── KPI Yorumlama ──
    {
        "instruction": "Personel devir hızı %22. Bu ne anlama geliyor?",
        "input": "",
        "output": """## Personel Devir Hızı Analizi

**Mevcut Değer**: %22 — 🟠 **Yüksek**

### Benchmark Karşılaştırması
- Tekstil sektörü ortalaması: %15-20
- İyi seviye: <%12
- Sizin değeriniz sektör ortalamasının üzerinde

### Maliyet Etkisi
Her ayrılan çalışanın ortalama maliyeti = 3-6 aylık maaş
- 100 kişilik fabrikada yılda ~22 kişi ayrılıyor
- Tahmini yıllık maliyet: ₺600,000-1,200,000

### Olası Nedenler
1. Ücret politikası rekabetçi değil
2. Çalışma koşulları (vardiya sistemi, fiziksel ortam)
3. Kariyer gelişim fırsatı eksikliği
4. Yönetim/iletişim sorunları

### Öneriler
- **Hemen**: Çıkış mülakatı analizi — gerçek nedenleri belirle
- **1 ay**: Ücret benchmarking çalışması
- **3 ay**: Çalışan memnuniyet anketi + aksiyon planı
- **Hedef**: %22 → %15 (12 ayda)"""
    },
]


# ══════════════════════════════════════════════════════════════
# 2. KONUŞMA GEÇMİŞİNDEN VERİ ÇIKARMA
# ══════════════════════════════════════════════════════════════

def extract_from_conversations(db_url: str = None) -> List[Dict]:
    """PostgreSQL konuşma geçmişinden eğitim verisi çıkar.
    
    Yüksek kaliteli Q&A çiftlerini seçer:
    - Confidence > 70%
    - Yanıt uzunluğu > 100 karakter
    - İş/analiz intent'li sorular
    """
    dataset = []
    
    try:
        import psycopg2
        conn_url = db_url or os.environ.get(
            "DATABASE_URL", 
            "postgresql://companyai:companyai123@localhost:5432/companyai"
        )
        conn = psycopg2.connect(conn_url)
        cur = conn.cursor()
        
        # Yüksek kaliteli konuşmaları çek
        cur.execute("""
            SELECT question, answer, confidence, mode, intent
            FROM conversations 
            WHERE confidence > 0.70 
            AND length(answer) > 100
            AND intent IN ('iş', 'bilgi')
            ORDER BY created_at DESC
            LIMIT 500
        """)
        
        rows = cur.fetchall()
        for q, a, conf, mode, intent in rows:
            # Temizleme
            clean_q = q.strip()
            clean_a = a.strip()
            
            # Confidence badge'i temizle
            clean_a = re.sub(r'\n---\n[🟢🔵🟡🔴].*$', '', clean_a, flags=re.MULTILINE)
            
            if len(clean_q) > 10 and len(clean_a) > 50:
                dataset.append({
                    "instruction": clean_q,
                    "input": "",
                    "output": clean_a,
                    "metadata": {"confidence": conf, "mode": mode, "intent": intent},
                })
        
        cur.close()
        conn.close()
        print(f"✅ PostgreSQL'den {len(dataset)} konuşma çıkarıldı")
        
    except Exception as e:
        print(f"⚠️ PostgreSQL bağlantı hatası: {e}")
        print("   Sunucuda çalıştırın veya DATABASE_URL env ayarlayın")
    
    return dataset


# ══════════════════════════════════════════════════════════════
# 3. EĞİTİM VERİSİ HAZIRLAMA
# ══════════════════════════════════════════════════════════════

def prepare_training_data(output_dir: str = "data/llm_training") -> str:
    """Tüm kaynaklardan eğitim verisini birleştir ve formatla."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    all_data = []
    
    # 1. Sabit tekstil veri seti
    all_data.extend(TEXTILE_QA_DATASET)
    print(f"  📝 Tekstil veri seti: {len(TEXTILE_QA_DATASET)} örnek")
    
    # 2. Konuşma geçmişi
    conv_data = extract_from_conversations()
    all_data.extend(conv_data)
    print(f"  💬 Konuşma geçmişi: {len(conv_data)} örnek")
    
    # 3. Alpaca formatına çevir (Qwen2.5 uyumlu)
    alpaca_data = []
    for item in all_data:
        alpaca_data.append({
            "instruction": item["instruction"],
            "input": item.get("input", ""),
            "output": item["output"],
        })
    
    # Train/Eval split
    import random
    random.shuffle(alpaca_data)
    split_idx = int(len(alpaca_data) * 0.9)
    train = alpaca_data[:split_idx]
    eval_data = alpaca_data[split_idx:]
    
    # Kaydet
    train_path = os.path.join(output_dir, "train.json")
    eval_path = os.path.join(output_dir, "eval.json")
    
    with open(train_path, "w", encoding="utf-8") as f:
        json.dump(train, f, ensure_ascii=False, indent=2)
    
    with open(eval_path, "w", encoding="utf-8") as f:
        json.dump(eval_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Eğitim verisi hazır:")
    print(f"   Train: {len(train)} örnek → {train_path}")
    print(f"   Eval:  {len(eval_data)} örnek → {eval_path}")
    
    return train_path


# ══════════════════════════════════════════════════════════════
# 4. UNSLOTH QLoRA EĞİTİM SCRİPTİ
# ══════════════════════════════════════════════════════════════

UNSLOTH_TRAINING_SCRIPT = '''#!/usr/bin/env python3
"""Qwen2.5 QLoRA Fine-Tune Script (Unsloth ile)

Bu script'i GPU olan makinede çalıştırın.
Gereksinimler: pip install "unsloth[cu121-torch240]" datasets

Kaynak: data/llm_training/train.json
Çıktı: models/qwen25-textile-lora/
"""

from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments
import torch

# ─── 1. Model Yükle ───
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Qwen2.5-7B-Instruct-bnb-4bit",  # 4bit quantized
    max_seq_length=2048,
    dtype=None,  # Auto-detect
    load_in_4bit=True,
)

# ─── 2. LoRA Adaptör Ekle ───
model = FastLanguageModel.get_peft_model(
    model,
    r=16,        # LoRA rank
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                     "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
)

# ─── 3. Veri Seti ───
alpaca_prompt = """### Instruction:
{instruction}

### Input:
{input}

### Response:
{output}"""

def formatting_prompts_func(examples):
    texts = []
    for i in range(len(examples["instruction"])):
        text = alpaca_prompt.format(
            instruction=examples["instruction"][i],
            input=examples["input"][i],
            output=examples["output"][i],
        )
        texts.append(text + tokenizer.eos_token)
    return {"text": texts}

dataset = load_dataset("json", data_files="data/llm_training/train.json", split="train")
dataset = dataset.map(formatting_prompts_func, batched=True)

# ─── 4. Eğitim ───
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=2048,
    args=TrainingArguments(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_steps=5,
        num_train_epochs=3,
        learning_rate=2e-4,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=1,
        output_dir="models/qwen25-textile-lora",
        save_strategy="epoch",
    ),
)

trainer.train()

# ─── 5. GGUF Export ───
print("\\n📦 GGUF export başlatılıyor...")
model.save_pretrained_gguf(
    "models/qwen25-textile-gguf",
    tokenizer,
    quantization_method="q4_k_m",  # 4-bit quantization
)
print("✅ GGUF model hazır: models/qwen25-textile-gguf/")
print("   Ollama'ya yüklemek için: ollama create companyai-textile -f Modelfile")
'''


# ══════════════════════════════════════════════════════════════
# 5. OLLAMA MODELFILE
# ══════════════════════════════════════════════════════════════

def generate_modelfile(gguf_path: str = "models/qwen25-textile-gguf/unsloth.Q4_K_M.gguf"):
    """Ollama Modelfile oluştur."""
    modelfile = f"""# CompanyAI Tekstil Fine-Tuned Model
# Ollama'ya yükle: ollama create companyai-textile -f Modelfile

FROM {gguf_path}

# Parametreler
PARAMETER temperature 0.4
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER repeat_penalty 1.1
PARAMETER num_ctx 4096

# Sistem prompt'u
SYSTEM \"\"\"Sen CompanyAI, Türk tekstil sektörüne uzmanlaşmış kurumsal yapay zeka asistanısın.

Görevlerin:
- Üretim verisi analizi (OEE, fire, verimlilik)
- Maliyet ve finansal etki hesaplama
- Risk değerlendirmesi ve yönetimi
- KPI yorumlama ve benchmark karşılaştırma
- Stratejik öneriler ve aksiyon planları

Kurallar:
- Her zaman somut sayısal veriler kullan
- Türk Lirası (₺) cinsinden maliyet hesapla
- Sektörel benchmark'larla karşılaştır
- Kısa, orta ve uzun vadeli öneriler sun
- Risk seviyelerini belirt (Düşük/Orta/Yüksek/Kritik)
- Tablo ve liste formatı kullan
- Türkçe yanıt ver
\"\"\"

# Template — Qwen2.5 chat formatı
TEMPLATE \"\"\"{{{{ if .System }}}}<|im_start|>system
{{{{ .System }}}}<|im_end|>
{{{{ end }}}}{{{{ if .Prompt }}}}<|im_start|>user
{{{{ .Prompt }}}}<|im_end|>
{{{{ end }}}}<|im_start|>assistant
{{{{ .Response }}}}<|im_end|>
\"\"\"
"""
    
    modelfile_path = "Modelfile.textile"
    with open(modelfile_path, "w", encoding="utf-8") as f:
        f.write(modelfile)
    
    print(f"✅ Ollama Modelfile oluşturuldu: {modelfile_path}")
    print(f"   Kullanım: ollama create companyai-textile -f {modelfile_path}")
    
    return modelfile_path


# ══════════════════════════════════════════════════════════════
# 6. CLI
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LLM Fine-Tune Pipeline")
    parser.add_argument("--extract", action="store_true", help="Konuşmalardan veri çıkar")
    parser.add_argument("--prepare", action="store_true", help="Eğitim verisi hazırla (sabit + konuşma)")
    parser.add_argument("--modelfile", action="store_true", help="Ollama Modelfile oluştur")
    parser.add_argument("--export-script", action="store_true", help="Unsloth eğitim script'i oluştur")
    parser.add_argument("--full", action="store_true", help="Tüm adımları çalıştır")
    
    args = parser.parse_args()
    
    if args.extract:
        data = extract_from_conversations()
        if data:
            path = "data/llm_training/conversations.json"
            Path("data/llm_training").mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"   Kaydedildi: {path}")
    
    elif args.prepare:
        prepare_training_data()
    
    elif args.modelfile:
        generate_modelfile()
    
    elif args.export_script:
        script_path = "train_qwen_lora.py"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(UNSLOTH_TRAINING_SCRIPT)
        print(f"✅ Eğitim script'i oluşturuldu: {script_path}")
        print(f"   GPU makinede çalıştırın: python {script_path}")
    
    elif args.full:
        print("═══ Tam Pipeline ═══\n")
        print("1️⃣ Eğitim verisi hazırlanıyor...")
        prepare_training_data()
        print("\n2️⃣ Ollama Modelfile oluşturuluyor...")
        generate_modelfile()
        print("\n3️⃣ Eğitim script'i oluşturuluyor...")
        script_path = "train_qwen_lora.py"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(UNSLOTH_TRAINING_SCRIPT)
        print(f"   ✅ {script_path}")
        print("\n═══ Sonraki Adımlar ═══")
        print("1. GPU makinede: python train_qwen_lora.py")
        print("2. GGUF dosyasını sunucuya kopyala")
        print("3. ollama create companyai-textile -f Modelfile.textile")
        print("4. app/config.py'de MODEL_NAME'i güncelle")
    
    else:
        parser.print_help()
