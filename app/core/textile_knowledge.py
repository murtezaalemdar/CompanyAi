"""Tekstil Sektör Bilgi Tabanı — Domain Knowledge

Tekstil sektörüne özel:
- Terminoloji sözlüğü (200+ terim)
- Fire analizi kalıpları
- Verimlilik analizi dili
- Üretim kayıp kategorileri
- Maliyet kırılım şablonları
- Sezonluk kapasite planlama
- Kalite kontrol parametreleri
"""

# ══════════════════════════════════════════════════════════════
# 1. TEKSTİL TERMİNOLOJİ SÖZLÜĞÜ
# ══════════════════════════════════════════════════════════════

TEXTILE_GLOSSARY = {
    # İPLİK
    "ne": {"tr": "Ne Numarası", "en": "Yarn Count", "desc": "İplik incelik ölçüsü. Yüksek = ince, Düşük = kalın. Örn: Ne 30/1 pamuk iplik."},
    "ring": {"tr": "Ring İplik", "en": "Ring Spun Yarn", "desc": "En yaygın iplik eğirme yöntemi. Yüksek mukavemet, geniş numara aralığı."},
    "open_end": {"tr": "Open-End (Rotor)", "en": "Open-End Yarn", "desc": "Hızlı üretim, düşük maliyet, düşük mukavemet. Denim, havlu için ideal."},
    "vortex": {"tr": "Vortex İplik", "en": "Vortex (MVS)", "desc": "Hava jetli eğirme. Düşük tüylülük, yüksek hız. Premium segment."},
    "bukulm": {"tr": "Büküm", "en": "Twist", "desc": "Liflerin birbirine tutunma derecesi. Tur/metre. Z ve S büküm."},
    "mukavemet": {"tr": "Mukavemet", "en": "Tenacity", "desc": "İpliğin kopma dayanımı. cN/tex biriminde ölçülür."},
    "uster": {"tr": "Üster Değeri", "en": "Uster CV%", "desc": "İplik düzgünlüğü ölçüsü. Düşük = düzgün. %12'den az hedef."},
    
    # DOKUMA
    "armur": {"tr": "Armür Dokuma", "en": "Dobby Weave", "desc": "Basit desen tekrarı olan dokuma. Küçük geometrik desenler."},
    "jakarli": {"tr": "Jakarlı Dokuma", "en": "Jacquard Weave", "desc": "Karmaşık desen dokuma. Her atkı teli bağımsız kontrol."},
    "cozgu": {"tr": "Çözgü", "en": "Warp", "desc": "Uzunlamasına iplikler. Boy yönü. Levent üzerinde hazırlanır."},
    "atki": {"tr": "Atkı", "en": "Weft/Filling", "desc": "Enine iplikler. En yönü. Mekik/rapier ile atılır."},
    "gramaj": {"tr": "Gramaj", "en": "GSM (g/m²)", "desc": "Kumaş ağırlığı. g/m² biriminde. Düşük = ince, Yüksek = kalın."},
    "siklik": {"tr": "Sıklık", "en": "Thread Count", "desc": "Birim uzunluktaki iplik sayısı. Çözgü/atkı sıklığı."},
    "endustriyel_bez": {"tr": "Ham Bez", "en": "Greige Fabric", "desc": "İşlem görmemiş kumaş. Boyama/terbiye öncesi."},
    
    # BOYAHANE
    "reaktif": {"tr": "Reaktif Boya", "en": "Reactive Dye", "desc": "Selülozik elyaf için. Yüksek haslık, parlak renkler. Pamuk/viskon."},
    "dispers": {"tr": "Dispers Boya", "en": "Disperse Dye", "desc": "Sentetik elyaf için. Polyester boyama. Yüksek sıcaklık (130°C)."},
    "kup": {"tr": "Küp Boya", "en": "Vat Dye", "desc": "En yüksek haslık. İndigo bu grupta. Pahalı ama dayanıklı."},
    "haslik": {"tr": "Haslık", "en": "Fastness", "desc": "Boyanın dayanıklılığı. Yıkama, ışık, sürtünme haslığı. 1-5 skalası (5=en iyi)."},
    "delta_e": {"tr": "Renk Farkı (ΔE)", "en": "Color Difference", "desc": "Standart ile numune arası renk farkı. <1 = mükemmel, 1-2 = kabul, >2 = ret."},
    "recete": {"tr": "Boya Reçetesi", "en": "Dye Recipe", "desc": "Boya, kimyasal, sıcaklık, süre parametreleri. Renk tutarlılığı için kritik."},
    
    # KONFEKSİYON
    "sam": {"tr": "SAM (Standart Dakika)", "en": "Standard Allowed Minutes", "desc": "Bir operasyonun standart süresi. Verimlilik hesaplamasının temeli."},
    "kesim": {"tr": "Kesim", "en": "Cutting", "desc": "Kumaşın kalıba göre kesilmesi. Otomatik veya elle. Fire kaynağı."},
    "dikim": {"tr": "Dikim", "en": "Sewing", "desc": "Parçaların birleştirilmesi. Overlok, düz dikiş, zincir dikiş."},
    "kalite_kontrol": {"tr": "AQL Kontrolü", "en": "AQL (Acceptable Quality Level)", "desc": "Parti kabul kriteri. AQL 2.5 = %2.5 hata toleransı (yaygın)."},
    
    # TERBİYE/APRE
    "merserizasyon": {"tr": "Merserizasyon", "en": "Mercerization", "desc": "NaOH ile işlem. Parlaklık, mukavemet artışı. Premium pamuk için."},
    "sanfor": {"tr": "Sanfor", "en": "Sanforize", "desc": "Mekanik çekmezlik işlemi. Yıkamada max %1 çekme. Zorunlu kalite standardı."},
    "kalender": {"tr": "Kalender", "en": "Calendering", "desc": "Sıcak silindir ile düzleme/parlatma. Yüzey efektleri."},
    "ram": {"tr": "Ram Kurutma", "en": "Stenter Frame", "desc": "Germe-kurutma. En/boy ayarlama, apre fiksajı. Son işlem."},
    "yakma": {"tr": "Yakma (Gazlama)", "en": "Singeing", "desc": "Kumaş yüzeyindeki tüylerin alev ile yakılması. Düzgün yüzey için ilk terbiye işlemi."},
    "haslama": {"tr": "Haşlama", "en": "Desizing/Scouring", "desc": "Haşıl ve doğal yağların uzaklaştırılması. Boyama öncesi kritik adım."},
    "agartma": {"tr": "Ağartma", "en": "Bleaching", "desc": "H2O2 veya NaClO ile beyazlatma. Renk açma, boya hazırlığı."},
    "su_itici": {"tr": "Su İtici Apre", "en": "Water Repellent", "desc": "Fluorokarbon veya silikon bazlı kaplama. Outdoor kumaş için zorunlu."},
    "anti_statik": {"tr": "Anti-Statik Apre", "en": "Antistatic Finish", "desc": "Statik elektrik önleyici. Sentetik kumaşlar için önemli."},
    "anti_bakteriyel": {"tr": "Anti-Bakteriyel Apre", "en": "Antibacterial Finish", "desc": "Gümüş iyon veya chitosan bazlı. Spor/medikal tekstil."},
    "wrinkle_free": {"tr": "Ütü Gerektirmez", "en": "Wrinkle Free / Non-Iron", "desc": "Reçine ile çapraz bağlama. Gömlek kumaşı için premium özellik."},
    
    # KALİTE
    "defolu": {"tr": "Defolu Kumaş", "en": "Defective Fabric", "desc": "Hatalı kumaş. Düğüm, delik, leke, çizgi gibi hatalar."},
    "parti": {"tr": "Lot/Parti", "en": "Batch/Lot", "desc": "Aynı koşullarda üretilen birim. Renk tutarlılığı için parti takibi kritik."},
    "four_point": {"tr": "4 Puan Sistemi", "en": "Four Point System", "desc": "Kumaş kalite derecelendirme. Hata büyüklüğüne göre 1-4 puan. <40 puan/100m² = kabul."},
    "spc": {"tr": "İstatistiksel Proses Kontrol", "en": "SPC", "desc": "Üretim sürecini kontrol kartlarıyla izleme. X-bar, R kartı, Cp, Cpk."},
    "iso_9001": {"tr": "ISO 9001", "en": "ISO 9001", "desc": "Kalite yönetim sistemi standardı. Tekstilde zorunlu sertifika."},
    "oeko_tex": {"tr": "Oeko-Tex Standard 100", "en": "Oeko-Tex", "desc": "Zararlı madde testi. Bebek/cilde temas sınıflandırması (I-IV)."},
    "gots": {"tr": "GOTS Sertifikası", "en": "Global Organic Textile Standard", "desc": "Organik tekstil standardı. Min %70 organik elyaf. Ekolojik ve sosyal kriterler."},
    
    # PENYE / ÖRME
    "penye": {"tr": "Penye Kumaş", "en": "Jersey/Knit Fabric", "desc": "Tek plakalı yuvarlak örme kumaş. T-shirt, iç giyim, günlük giyim. Esneklik, yumuşaklık."},
    "suprem": {"tr": "Süprem", "en": "Single Jersey", "desc": "Tek yüzlü düz örme. En basit penye yapısı. Gramaj: 120-200 g/m²."},
    "ribana": {"tr": "Ribana", "en": "Rib Knit", "desc": "Çift yüzlü örme. Yaka, manşet, bel bandı. 1x1, 2x2, 2x1 ribana."},
    "interlok": {"tr": "İnterlok", "en": "Interlock", "desc": "Çift plakalı düz örme. Kalın, boyutsal kararlı. İç giyim, bebek."},
    "pike": {"tr": "Pike", "en": "Piqué", "desc": "Kabartmalı yüzeyli örme. Polo tişört kumaşı. Waffle benzeri doku."},
    "orme_tezgah": {"tr": "Yuvarlak Örme Tezgahı", "en": "Circular Knitting Machine", "desc": "Tüp kumaş üretimi. İnç çapı (20-38), iğne sayısı (gauge 18-32). Hız: dev/dk."},
    "triko": {"tr": "Triko Örme", "en": "Warp Knitting", "desc": "Çözgü ipliğiyle örme. Raschel, Tricot makineleri. Dantel, tül, teknik tekstil."},
    "lycra": {"tr": "Likra/Elastan", "en": "Lycra/Elastane/Spandex", "desc": "Elastik elyaf. %2-20 oranında katılır. Fitness, denim, iç giyim. Stretch özelliği."},
    "gauge": {"tr": "Galga (İğne Aralığı)", "en": "Gauge", "desc": "1 İnç'teki iğne sayısı. Yüksek gauge = ince kumaş. E18 kaba, E28 ince."},
    
    # BASKI (TEKSTİL)
    "dijital_baski": {"tr": "Dijital Baskı", "en": "Digital Printing", "desc": "İnkjet baskı. Sınırsız renk, kısa metraj. Reaktif/dispers/pigment mürekkep."},
    "rotasyon_baski": {"tr": "Rotasyon Baskı", "en": "Rotary Screen Printing", "desc": "Silindirik şablonla sürekli baskı. Yüksek hız, uzun metraj. Rapor tekrarı."},
    "flat_baski": {"tr": "Düz Şablon Baskı", "en": "Flat Screen Printing", "desc": "Düz çerçeve şablon. Hassas desen, düşük hız. Premium kumaş."},
    "sublimation": {"tr": "Süblimasyon Baskı", "en": "Sublimation Printing", "desc": "Transfer kağıdından kumaşa ısı ile baskı. Sadece polyester. Foto-gerçekçi."},
    "pigment_baski": {"tr": "Pigment Baskı", "en": "Pigment Printing", "desc": "Binder ile pigment fiksajı. Tüm elyaflara uygun. Sert tuşe, düşük haslık."},
    "flock_baski": {"tr": "Flok Baskı", "en": "Flock Printing", "desc": "Elektrostatik elyaf yapıştırma. Kadife efekti. Dekoratif kullanım."},
    "serigraf": {"tr": "Serigrafi", "en": "Screen Printing", "desc": "T-shirt baskısı. Düz yüzeye şablon baskı. CMYK veya spot renk, katman katman."},
    
    # NAKIŞ
    "nakis": {"tr": "Makine Nakışı", "en": "Machine Embroidery", "desc": "Otomatik nakış makinesi. Tajima, Barudan. Logo, isim, desen. Dikiş sayısı ile fiyatlanır."},
    "pul_nakis": {"tr": "Pul Nakışı", "en": "Sequin Embroidery", "desc": "Pul/payet dizme ile nakış. Dekoratif. Abiye, sahne kıyafeti."},
    "aplike": {"tr": "Aplike", "en": "Appliqué", "desc": "Kumaş parça üzerine dikme dekorasyon. Logo, arma. Spor giyimde yaygın."},
    
    # TEDARİK ZİNCİRİ
    "fason": {"tr": "Fason Üretim", "en": "CMT / Subcontracting", "desc": "Başkasının markası için üretim. CMT (Cut-Make-Trim). Kapasite esnekliği."},
    "oem": {"tr": "OEM Üretim", "en": "Original Equipment Manufacturer", "desc": "Müşteri tasarımıyla üretim. Private label. Büyük markalara tedarik."},
    "odm": {"tr": "ODM Üretim", "en": "Original Design Manufacturing", "desc": "Kendi tasarımını müşteriye satma. Daha yüksek katma değer."},
    "moq": {"tr": "Minimum Sipariş Miktarı", "en": "MOQ", "desc": "Kabul edilen en düşük sipariş adedi. İplik: ton, kumaş: metre, konfeksiyon: adet."},
    "lead_time": {"tr": "Teslim Süresi", "en": "Lead Time", "desc": "Sipariş → teslimat süresi. İplik: 2-4 hafta, kumaş: 3-6 hafta, konfeksiyon: 4-8 hafta."},
    "incoterms": {"tr": "Teslim Şekilleri", "en": "Incoterms", "desc": "FOB, CIF, EXW, DDP. Uluslararası ticaret teslim koşulları. Maliyet/risk paylaşımı."},
    "lc": {"tr": "Akreditif", "en": "Letter of Credit", "desc": "Banka garantili ödeme. İhracatta güvenli tahsilat. Belge karşılığı ödeme."},
    
    # SÜRDÜRÜLEBİLİRLİK
    "grs": {"tr": "GRS Sertifikası", "en": "Global Recycled Standard", "desc": "Geri dönüşüm standardı. Min %20 geri dönüşüm içerik. İzlenebilirlik zinciri."},
    "bci": {"tr": "BCI Pamuk", "en": "Better Cotton Initiative", "desc": "Sürdürülebilir pamuk yetiştiriciliği. Su ve pestisit azaltma. Sosyal uyumluluk."},
    "higg_index": {"tr": "Higg Index", "en": "Higg Index (SAC)", "desc": "Sürdürülebilirlik ölçüm aracı. Çevresel ve sosyal etki skorlaması. Tesis/ürün bazlı."},
    "karbon_ayak_izi": {"tr": "Karbon Ayak İzi", "en": "Carbon Footprint", "desc": "CO2 eşdeğer emisyon. LCA (Yaşam Döngüsü Analizi) ile ölçülür. kgCO2e/kg kumaş."},
    "su_ayak_izi": {"tr": "Su Ayak İzi", "en": "Water Footprint", "desc": "Ürün başına su tüketimi. Pamuk T-shirt: ~2700 litre. Tekstilde en büyük çevresel etki."},
    "zdhc": {"tr": "ZDHC", "en": "Zero Discharge of Hazardous Chemicals", "desc": "Tehlikeli kimyasal sıfır deşarj. MRSL listesi. Büyük markaların tedarikçi şartı."},
    
    # MAKİNE / EKİPMAN
    "rapier": {"tr": "Rapier Tezgah", "en": "Rapier Loom", "desc": "Kancalı atkı atma. En yaygın dokuma tezgahı. Geniş kumaş, çok renkli atkı."},
    "air_jet": {"tr": "Air Jet Tezgah", "en": "Air Jet Loom", "desc": "Hava jetli atkı atma. Çok yüksek hız (800+ atım/dk). Hafif kumaşlar."},
    "water_jet": {"tr": "Water Jet Tezgah", "en": "Water Jet Loom", "desc": "Su jetli atkı atma. Sentetik kumaşlar. Düşük maliyet, yüksek hız."},
    "otoklav": {"tr": "Otoklav", "en": "Autoclave", "desc": "Basınçlı buhar sterilizasyon. Medikal tekstil, boyahane. 121-134°C."},
    "jet_boya": {"tr": "Jet Boya Makinesi", "en": "Jet Dyeing Machine", "desc": "Yüksek basınçlı sıvı jetli boyama. 130°C polyester boyama. Overflow ve softflow tipleri."},
    "jigger": {"tr": "Jigger Boya", "en": "Jigger Dyeing", "desc": "Açık en boyama. Hassas kumaşlar, kısa metraj. Düşük flotte oranı."},
    "pad_batch": {"tr": "Pad-Batch", "en": "Pad-Batch Cold", "desc": "Soğuk emdirme boyama. Reaktif boya + NaOH. Düşük enerji, yüksek tekrarlanabilirlik."},
}


# ══════════════════════════════════════════════════════════════
# 2. FİRE ANALİZİ KALIPLARI
# ══════════════════════════════════════════════════════════════

WASTE_ANALYSIS = {
    "categories": {
        "iplik_fire": {
            "name": "İplik Fire",
            "typical_rate": 2.5,
            "sources": ["Kopuş", "Numune", "Temizlik", "Başlangıç/bitiş"],
            "reduction_actions": [
                "Kopuş nedenlerini Pareto ile analiz et",
                "Otomatik düğüm makinesi bakımı",
                "İplik kalitesi tedarikçi değerlendirmesi",
            ],
        },
        "dokuma_fire": {
            "name": "Dokuma Fire",
            "typical_rate": 3.0,
            "sources": ["Kenar fire", "Desen hatası", "Çözgü kopuşu", "Başlangıç kumaşı"],
            "reduction_actions": [
                "Çözgü hazırlık kalitesini iyileştir",
                "Otomatik duruş sensörleri kalibrasyonu",
                "Operatör eğitim programı",
            ],
        },
        "boya_fire": {
            "name": "Boya Fire",
            "typical_rate": 2.0,
            "sources": ["Renk uyumsuzluk", "Leke", "Kimyasal hata", "Sıcaklık sapması"],
            "reduction_actions": [
                "Reçete standardizasyonu ve dijitalleşme",
                "Otomatik dozajlama sistemi",
                "Spektrofotometre ile hat içi kontrol",
            ],
        },
        "konfeksiyon_fire": {
            "name": "Konfeksiyon Fire",
            "typical_rate": 4.0,
            "sources": ["Kesim fire", "Dikim hatası", "Kumaş hatası", "Pastal planı"],
            "reduction_actions": [
                "CAD/CAM pastal optimizasyonu",
                "Otomatik kesim makinesi kalibrasyonu",
                "Inline kalite kontrol noktaları artır",
            ],
        },
    },
    
    "total_benchmark": {
        "dünya_sınıfı": 4.0,
        "iyi": 6.0,
        "ortalama": 10.0,
        "kötü": 15.0,
    },
}


# ══════════════════════════════════════════════════════════════
# 3. VERİMLİLİK ANALİZİ
# ══════════════════════════════════════════════════════════════

EFFICIENCY_FRAMEWORK = {
    "six_big_losses": {
        "1_ariza": {
            "name": "Arıza Kayıpları",
            "category": "Kullanılabilirlik",
            "description": "Ekipman arızaları nedeniyle plansız duruşlar",
            "measurement": "Duruş süresi (dakika)",
            "reduction": "TPM (Toplam Üretken Bakım), preventive maintenance",
        },
        "2_setup": {
            "name": "Setup/Ayar Kayıpları",
            "category": "Kullanılabilirlik",
            "description": "Ürün değişimi, kalıp değişimi, ayar süreleri",
            "measurement": "Setup süresi (dakika)",
            "reduction": "SMED (Hızlı Kalıp Değişimi), standardizasyon",
        },
        "3_kucuk_durus": {
            "name": "Küçük Duruşlar",
            "category": "Performans",
            "description": "Kısa süreli duruşlar (<5 dk), sensör hataları",
            "measurement": "Toplam küçük duruş (dakika)",
            "reduction": "5S, otonomasyon, sensör kalibrasyonu",
        },
        "4_hiz_kaybi": {
            "name": "Hız Kayıpları",
            "category": "Performans",
            "description": "Tasarım hızının altında çalışma",
            "measurement": "(Standart - Gerçek) / Standart × 100",
            "reduction": "Hız optimizasyonu, darboğaz analizi",
        },
        "5_proses_hatasi": {
            "name": "Proses Hataları (Fire)",
            "category": "Kalite",
            "description": "Üretim sırasında oluşan hatalı ürünler",
            "measurement": "(Hatalı / Toplam) × 100",
            "reduction": "Poka-yoke, SPC (İstatistiksel Proses Kontrol)",
        },
        "6_baslangic_kaybi": {
            "name": "Başlangıç Kayıpları",
            "category": "Kalite",
            "description": "Makine ısınma, deneme, ayar sırasındaki kayıplar",
            "measurement": "Başlangıç fire (birim)",
            "reduction": "Standart başlangıç prosedürü, operatör eğitimi",
        },
    },
    
    "textile_specific_losses": {
        "cozgu_kopusu": {"name": "Çözgü Kopuşu", "typical_loss_min_per_shift": 30},
        "atki_durma": {"name": "Atkı Durma", "typical_loss_min_per_shift": 15},
        "desen_degisimi": {"name": "Desen Değişimi", "typical_loss_min_per_shift": 60},
        "boya_degisimi": {"name": "Renk/Boya Değişimi", "typical_loss_min_per_shift": 45},
        "levent_degisimi": {"name": "Levent Değişimi", "typical_loss_min_per_shift": 20},
    },
}


# ══════════════════════════════════════════════════════════════
# 4. MALİYET KIRILIM ŞABLONU
# ══════════════════════════════════════════════════════════════

COST_BREAKDOWN_TEMPLATE = {
    "iplik": {
        "hammadde": {"share": 55, "description": "Pamuk, polyester, viskon (elyaf)"},
        "enerji": {"share": 12, "description": "Elektrik, buhar, kompresör"},
        "iscilik": {"share": 18, "description": "Direkt + endirekt işçilik"},
        "amortisman": {"share": 8, "description": "Makine, bina amortismanı"},
        "diger_gug": {"share": 7, "description": "Bakım, yardımcı malzeme, genel gider"},
    },
    "dokuma": {
        "hammadde": {"share": 60, "description": "İplik maliyeti"},
        "enerji": {"share": 10, "description": "Elektrik, hava"},
        "iscilik": {"share": 15, "description": "Operatör, teknisyen"},
        "amortisman": {"share": 10, "description": "Tezgah, hazırlık makineleri"},
        "diger_gug": {"share": 5, "description": "Bakım, yedek parça"},
    },
    "boyahane": {
        "hammadde": {"share": 35, "description": "Ham kumaş"},
        "kimyasal": {"share": 25, "description": "Boya, kimyasal, yardımcı"},
        "enerji": {"share": 18, "description": "Buhar, elektrik, su"},
        "iscilik": {"share": 12, "description": "Operatör, laborant"},
        "amortisman": {"share": 5, "description": "Boya makineleri, ram"},
        "su_aritma": {"share": 5, "description": "Atıksu arıtma maliyeti"},
    },
    "konfeksiyon": {
        "hammadde": {"share": 50, "description": "Kumaş + aksesuar (düğme, fermuar, etiket)"},
        "iscilik": {"share": 30, "description": "Kesim, dikim, ütü, paket"},
        "enerji": {"share": 5, "description": "Elektrik, buhar (ütü)"},
        "amortisman": {"share": 5, "description": "Dikiş makinesi, kesim masası"},
        "lojistik": {"share": 5, "description": "Nakliye, depolama"},
        "diger_gug": {"share": 5, "description": "Kalite kontrol, ambalaj"},
    },
}


# ══════════════════════════════════════════════════════════════
# 5. SEZONLUK KAPASİTE PLANLAMA
# ══════════════════════════════════════════════════════════════

SEASONAL_CAPACITY = {
    "Q1_ocak_mart": {
        "demand": "Yüksek",
        "focus": "Yaz koleksiyonu üretimi + İhracat yoğunluğu",
        "capacity_utilization": "85-95%",
        "risk": "Kapasite yetersizliği, fazla mesai maliyeti",
        "action": "Fason desteği planla, hammadde stoku artır",
    },
    "Q2_nisan_haziran": {
        "demand": "Orta",
        "focus": "Geçiş dönemi, kış siparişi toplama",
        "capacity_utilization": "70-80%",
        "risk": "Talep belirsizliği",
        "action": "Numune geliştirme, yeni müşteri kazanımı",
    },
    "Q3_temmuz_eylul": {
        "demand": "Yüksek",
        "focus": "Kış koleksiyonu üretimi + Yurtiçi pik sezon",
        "capacity_utilization": "85-95%",
        "risk": "Hammadde fiyat artışı (pamuk hasadı)",
        "action": "Stok yönetimi, vardiya planlaması",
    },
    "Q4_ekim_aralik": {
        "demand": "Orta-Düşük",
        "focus": "Sezon sonu, stok eritme, yılbaşı siparişleri",
        "capacity_utilization": "60-75%",
        "risk": "Stok birikimi, nakit akış sıkışıklığı",
        "action": "Bakım planlama, eğitim, kaizen projeleri",
    },
}


# ══════════════════════════════════════════════════════════════
# 6. FONKSİYONLAR
# ══════════════════════════════════════════════════════════════

def get_glossary_term(term: str) -> dict:
    """Tekstil terimini sözlükten getir."""
    term_lower = term.lower().replace(" ", "_").replace("ı", "i")
    
    # Direkt eşleşme
    if term_lower in TEXTILE_GLOSSARY:
        return TEXTILE_GLOSSARY[term_lower]
    
    # Fuzzy arama
    matches = []
    for key, value in TEXTILE_GLOSSARY.items():
        if (term_lower in key or 
            term_lower in value.get("tr", "").lower() or
            term_lower in value.get("en", "").lower() or
            term_lower in value.get("desc", "").lower()):
            matches.append({**value, "key": key})
    
    return matches[0] if len(matches) == 1 else {"matches": matches} if matches else {"error": "Terim bulunamadı"}


def analyze_waste(waste_data: dict) -> dict:
    """Fire verisini analiz et ve yorumla.
    
    waste_data: {"iplik_fire": 2.5, "dokuma_fire": 3.0, "boya_fire": 1.8, "konfeksiyon_fire": 4.2}
    """
    analysis = {"categories": [], "total_rate": 0, "recommendations": []}
    
    total_rate = 0
    for cat_id, rate in waste_data.items():
        cat_info = WASTE_ANALYSIS["categories"].get(cat_id, {})
        if not cat_info:
            continue
        
        typical = cat_info.get("typical_rate", 3.0)
        status = "İyi" if rate < typical * 0.8 else "Normal" if rate < typical * 1.2 else "Yüksek"
        
        analysis["categories"].append({
            "category": cat_info["name"],
            "rate": rate,
            "typical_rate": typical,
            "status": status,
            "sources": cat_info.get("sources", []),
        })
        total_rate += rate
        
        if status == "Yüksek":
            analysis["recommendations"].extend(cat_info.get("reduction_actions", []))
    
    analysis["total_rate"] = round(total_rate, 2)
    
    benchmarks = WASTE_ANALYSIS["total_benchmark"]
    if total_rate <= benchmarks["dünya_sınıfı"]:
        analysis["overall_status"] = "Dünya Sınıfı 🟢"
    elif total_rate <= benchmarks["iyi"]:
        analysis["overall_status"] = "İyi 🟢"
    elif total_rate <= benchmarks["ortalama"]:
        analysis["overall_status"] = "Ortalama 🟡"
    else:
        analysis["overall_status"] = "Kötü 🔴"
    
    return analysis


def get_cost_template(department: str) -> dict:
    """Departman için maliyet kırılım şablonunu getir."""
    return COST_BREAKDOWN_TEMPLATE.get(department.lower(), {})


def get_seasonal_plan(quarter: str = None) -> dict:
    """Sezonluk kapasite planını getir."""
    if quarter:
        for key, plan in SEASONAL_CAPACITY.items():
            if quarter.upper() in key.upper():
                return plan
    return SEASONAL_CAPACITY


def get_efficiency_loss_framework() -> dict:
    """6 Büyük Kayıp çerçevesini getir."""
    return EFFICIENCY_FRAMEWORK
