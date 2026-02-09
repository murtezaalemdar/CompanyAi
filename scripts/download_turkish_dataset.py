"""
HuggingFace'den Türkçe sohbet dataset'i indir ve data/ klasörüne kaydet.
Dataset: nihat4141/chatbot-turkish-dataset-sixfinger-2b
Format: {input, output} - ~2,200 Türkçe sohbet çifti
Lisans: Apache-2.0
"""
import json
import os
import sys
import urllib.request
import urllib.error

DATASET_URL = "https://datasets-server.huggingface.co/rows?dataset=nihat4141%2Fchatbot-turkish-dataset-sixfinger-2b&config=default&split=train&offset=0&length=100"
PARQUET_URL = "https://huggingface.co/api/datasets/nihat4141/chatbot-turkish-dataset-sixfinger-2b/parquet/default/train"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "turkish_chat_dataset.json")

def download_via_api():
    """HuggingFace API ile dataset'i sayfa sayfa indir."""
    all_rows = []
    offset = 0
    batch_size = 100
    
    print("HuggingFace API üzerinden dataset indiriliyor...")
    
    while True:
        url = (
            f"https://datasets-server.huggingface.co/rows?"
            f"dataset=nihat4141%2Fchatbot-turkish-dataset-sixfinger-2b"
            f"&config=default&split=train&offset={offset}&length={batch_size}"
        )
        
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CompanyAI/1.0"})
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as e:
            print(f"  Sayfa {offset} indirilemedi: {e}")
            break
        
        rows = data.get("rows", [])
        if not rows:
            break
        
        for row in rows:
            r = row.get("row", {})
            inp = r.get("input", "").strip()
            out = r.get("output", "").strip()
            if inp and out and len(out) > 10:
                all_rows.append({"input": inp, "output": out})
        
        print(f"  İndirildi: {offset + len(rows)} satır (toplam {len(all_rows)} geçerli)")
        offset += batch_size
        
        if len(rows) < batch_size:
            break
    
    return all_rows


def download_via_direct():
    """Doğrudan parquet info API'den dosya bilgilerini al."""
    print("Alternatif yöntem deneniyor (direct API)...")
    
    url = "https://datasets-server.huggingface.co/first-rows?dataset=nihat4141%2Fchatbot-turkish-dataset-sixfinger-2b&config=default&split=train"
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CompanyAI/1.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"  Direct API hatası: {e}")
        return []
    
    rows = data.get("rows", [])
    result = []
    for row in rows:
        r = row.get("row", {})
        inp = r.get("input", "").strip()
        out = r.get("output", "").strip()
        if inp and out:
            result.append({"input": inp, "output": out})
    
    print(f"  İlk batch: {len(result)} satır")
    return result


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Eğer zaten varsa
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f)
        print(f"Dataset zaten mevcut: {len(existing)} kayıt ({OUTPUT_FILE})")
        resp = input("Yeniden indirmek ister misiniz? (e/h): ").strip().lower()
        if resp != "e":
            return
    
    # API ile indir
    rows = download_via_api()
    
    if not rows:
        rows = download_via_direct()
    
    if not rows:
        print("Dataset indirilemedi! Manuel olarak indirmeniz gerekebilir.")
        print(f"URL: https://huggingface.co/datasets/nihat4141/chatbot-turkish-dataset-sixfinger-2b")
        sys.exit(1)
    
    # Kaydet
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    
    print(f"\nToplam {len(rows)} sohbet çifti kaydedildi: {OUTPUT_FILE}")
    print(f"Dosya boyutu: {os.path.getsize(OUTPUT_FILE) / 1024:.1f} KB")
    
    # Örnek göster
    print("\nÖrnek kayıtlar:")
    for i, row in enumerate(rows[:3]):
        print(f"\n--- Örnek {i+1} ---")
        print(f"Kullanıcı: {row['input'][:100]}...")
        print(f"AI: {row['output'][:100]}...")


if __name__ == "__main__":
    main()
