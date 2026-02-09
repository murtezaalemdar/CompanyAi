import os

# Fabrika Bölümleri ve Profesyonel İçerikleri
DEPARTMENTS = {
    "01_Iplik_ve_Hazirlik": """# İplik ve Çözgü Hazırlık Standartları - PROFESYONEL REHBER

## 1. İplik Kabul ve Giriş Kalite Kontrol
İplik kalitesi kumaşın %70'ini belirler. Giriş kontrolde şunlara dikkat edilmeli:
- **Uster Değerleri (H, CVm)**: Örme için düşük tüylülük (H), dokuma çözgü için yüksek mukavemet esastır.
- **Numara Kontrolü (Ne/Nm)**: Her partiden en az 5 bobin numara kontrolüne girmeli. Tolerans ±%1.5.
- **Büküm (TPI/TPM)**: 
    - *Örme İpliği:* Düşük büküm (Yumuşak tuşe için). αe (Büküm katsayısı) 3.2 - 3.5 arası.
    - *Dokuma Çözgü:* Yüksek büküm (Mukavemet için). αe 4.0 - 4.5 arası.
- **Yabancı Elyaf (Foreign Matter)**: Polipropilen (PP) kontaminasyonu boyada çıkmaz leke yapar (Kritik).

## 2. Depolama Koşulları (Klimatizasyon)
- **Sıcaklık**: 20-22°C sabit.
- **Bağıl Nem (%RH)**: 
    - Pamuk: %60-65 (Nem aldıkça mukavemet artar).
    - Viskos: %60-65.
    - Polyester: Neme duyarlı değildir ama statik elektrik için %50-55.
- **Kondisyonlama**: İplikler üretime girmeden en az 24 saat işletme ortamında bekletilmeli.

## 3. Bobinleme ve Çözgü (Warping)
- **Cağlık Dizilimi**: Parti (Lot) karışıklığı abraj nedenidir. Asla farklı lotları karıştırma.
- **Gerginlik (Tension)**: Tüm bobinlerde eşit olmalı. Gevşek iplik = Potluk, Gergin iplik = Kopuş.
""",

    "02_Orme_Uretim": """# Yuvarlak ve Düz Örme Üretim Standartları

## 1. Makine Ayarları ve Kalite Parametreleri
- **Fein (Gauge) & İplik İlişkisi**:
    - 20 Fein: Ne 20/1 - 24/1
    - 24 Fein: Ne 24/1 - 30/1
    - 28 Fein: Ne 30/1 - 40/1
    - *Hata*: Yanlış seçim iğne kırığına veya kumaşın "zırh" gibi sert olmasına neden olur.
- **May Dönmesi (Spirality)**:
    - *Nedenleri*: İplik büküm yönünün (S/Z) sistem sayısıyla uyumsuzluğu, yüksek büküm, makine ayarsızlığı.
    - *Çözüm*: Çift kat iplik kullanımı, S/Z karışık dizilim (1S-1Z), Lycra kullanımı.
- **Gramaj (GSM) Ayarı**: Kasnak (Kas) ayarı ve iplik besleme uzunluğu (Loop Length) ile kontrol edilir.

## 2. Yaygın Örme Hataları
- **Biyeli (Barré)**: Yatay çizgiler. Nedenleri: İplik lot farkı, sistemler arası gerginlik farkı, mekik ayarsızlığı.
- **İğne Çizgisi (Needle Line)**: Dikey çizgi. Kırık veya bozuk dilli iğne.
- **Patlak/Delik**: İplik mukavemetsizliği veya yüksek gerginlik. 
- **Yağ Lekesi**: Makine yağlama sisteminin fazlalığı veya iğne yatağı kirliliği.

## 3. Üretim Takip (KPI)
- **Makine Randımanı**: Hedef > %85.
- **Fire Oranı**: Hedef < %2.
- **Devir (RPM)**: Lycra'lı mallarda devir %10-15 düşürülmeli (Isınma ve kopuşu önlemek için).
""",

    "03_Dokuma_Uretim": """# Dokuma Üretim, Planlama ve Maliyet

## 1. Dokuma Teknolojileri ve Ayarlar
- **Air-Jet**: Yüksek hız, E tipi (Kolay) kumaşlar için. Hava basıncı maliyet kalemidir (Kompresör).
- **Rapier**: Desenli, fantezi ve ağır gramajlı kumaşlar için. Hız düşüktür ama esnektir.
- **Atkı Sıklığı (Picks/cm)**: Kumaş gramajını ve maliyeti direkt etkiler.
- **Çözgü Gerginliği**: Kumaş enine göre Newton cinsinden ayarlanmalı (Örn: 3.5 kN).

## 2. Dokuma Hataları
- **Cımbar İzi**: Kenarlarda delik veya yırtık. Cımbar ayarı veya bilezikleri kontrol edilmeli.
- **Atkı Kaçığı/Yarım Atkı**: Sensör hassasiyeti veya bobin bitimi.
- **Tarak İzi**: Tarak dişlerinde bozukluk veya yanlış tarak numarası seçimi.

## 3. Maliyet Hesaplama (Basit Formül)
- **İplik Maliyeti**: (Çözgü Ağırlığı + Atkı Ağırlığı) x İplik Fiyatı
- **İşçilik**: (Ülke/Bölge Dakika Ücreti) x (Metre Başına Dokuma Süresi)
- **Enerji**: Makine kW x Çalışma Saati + Hava Tüketimi (Airjet için)
- **Genel Gider**: Amortisman, Kira, Yedek Parça payı.
""",

    "04_Boyahane_Islem": """# Boyahane: Ön İşlem, Boyama, Yıkama ve Baskı

## 1. Ön İşlem (Pre-treatment)
Boyamanın %80'i ön işlemdir. Kötü ön işlem = Kötü Boya (Abraj).
- **Kasar (Bleaching)**: Hidrofiliteyi sağlar. Damla testi < 3 sn olmalı.
- **Yıkama pH**: Pamuk için pH 10.5-11, Yün için 4.5-5.5, Polyester (Yıkama değil ama banyo) 4.5-5.0.
- **Tüy Yakma (Gaze)**: Pürüzsüz yüzey için (Özellikle baskı altı kumaşlarda).

## 2. Boyama Süreçleri
- **Reaktif Boyama (Selülozik)**:
    - *Kritik*: Tuz/Soda dozajlama zamanlaması. Hızlı verilirse boya çöker (Abraj).
    - *Yıkama*: Haslık için sabunlama çok iyi yapılmalı (Hidrolize olmuş boyanın atılması).
- **Dispers Boyama (Polyester)**:
    - *Kritik*: HT (Yüksek Sıcaklık) 130°C. pH 4.5-5.0 sabit kalmalı (Tampon/Buffer kullanımı).
    - *Oligomer*: Soğutma kontrollü yapılmalı yoksa oligomer çökmesi toz yapar.

## 3. Baskı (Rotasyon & Dijital)
- **Kıvam (Pat)**: Düşük vizkozite = Desen yayılır. Yüksek vizkozite = Boya kumaşa işlemez.
- **Şablon (Screen)**: Mesh numarası desen detayına göre seçilmeli (İnce desen = Yüksek Mesh).
- **Fikse**: Buharlı fikse sıcaklığı ve süresi renk verimini (Color Yield) belirler.
""",

    "05_Terbiye_Bitim": """# Terbiye: Ram, Şardon, Sanfor, Kalite Kontrol

## 1. Ramöz (Stenter) İşlemleri
Tekstil terbiyesinin kalbidir.
- **En ve Gramaj Fiksesi**: İstenen en/gramaj burada ayarlanır. (Çekmezlik için besleme verilmeli).
- **Isı Profili**: 
    - Kurutma Kamaraları: 110-130°C (Nemi uçurur).
    - Fikse Kamaraları: 180-200°C (Polyester molekül yapısını sabitler).
- **Apreler**: Yumuşatıcı, Su itici, Yanmazlık kimyasalları burada fular (Padder) ile verilir.

## 2. Mekanik Bitim İşlemleri
- **Şardon (Raising)**: Tellerle tüy çıkarma. *Dikkat*: Kumaş mukavemetini düşürür. Pasaj sayısı kontrollü olmalı.
- **Sanfor**: Mekanik çekmezlik (Rubber Belt). Yıkama sonrası çekmeyi önler.
- **Traş (Shearing)**: Yüzeydeki tüyleri keserek pürüzsüzlük sağlar.

## 3. Kalite Kontrol (4 Puan Sistemi)
Endüstri standardı. 100 metrekaredeki toplam ceza puanı.
- < 20 Puan: 1. Kalite (A)
- 20-30 Puan: 2. Kalite (B) (Anlaşmaya bağlı)
- > 30 Puan: Iskonto veya Red (C)
""",
    
    "06_Yonetim_Destek": """# Pazarlama, İK, Muhasebe, IT (Tekstil Odaklı)

## 1. Pazarlama ve Desen (Design)
- **Kartela**: Müşteriye giden ayna. Renk haslıkları, çekmezlik değerleri kartelada mutlaka test edilmiş olmalı.
- **Termin (Lead Time)**: Lab-dip (3-5 gün) + İplik Temin (7-10 gün) + Üretim (15 gün). Doğru termin verilmezse hava kargo maliyeti çıkar.
- **Varyant**: Ana desenin farklı renk kombinasyonları. Maliyet düşürmek için ortak zemin (ground) kullanılabilir.

## 2. Maliyet ve Muhasebe
- **Birim Maliyet**: (Hammadde + İşçilik + Enerji + Amortisman) / Randıman.
- **Stok Maliyeti**: Tekstilde moda hızlı değişir, ölü stok (Deadstock) riski yüksektir. FIFO (First In First Out) uygulanmalı.

## 3. Bilgi İşlem (IT)
- **Barkod/RFID**: Top takibi için zorunlu. Hangi top hangi makineden çıktı?
- **ERP**: Reçete gizliliği (Boya formülleri) en kritik güvenlik noktasıdır.
- **Yedekleme**: Desen arşivleri (Terabaytlarca veri) en değerli varlıktır.
""",
}

def create_knowledge_base():
    base_dir = "textile_knowledge_base"
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
    
    print(f"🏭 Factory 'Brain' building in: {base_dir}")
    
    for folder, content in DEPARTMENTS.items():
        # Klasör oluştur
        dir_path = os.path.join(base_dir, folder)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            
        # Dosya yaz
        file_path = os.path.join(dir_path, "Pro_Rehber.md")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        print(f"✅ Created: {folder}/Pro_Rehber.md")

if __name__ == "__main__":
    create_knowledge_base()
