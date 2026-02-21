// Versiyon — app/config.py ile eşleşmeli
// Format: MAJOR.MINOR.PATCH (her segment 2 hane, ör. 6.01.00)
// ÖNEMLİ KURAL:
//   MAJOR (baş)  → Major değişiklik (mimari, geriye uyumsuz)
//   MINOR (orta) → Önemli değişiklik (yeni özellik, önemli iyileştirme)
//   PATCH (son)  → Küçük işlem (bugfix, ufak düzeltme)
//   MINOR artınca PATCH=00, MAJOR artınca MINOR=00 ve PATCH=00 olur.
export const APP_VERSION = '7.17.00'

export const DEPARTMENTS = [
    "Yönetim",
    "Yönetim Asistanı",
    "Boyahane Planlama",
    "Dokuma Planlama",
    "Bilgi İşlem",
    "Maliyet",
    "Muhasebe",
    "Finans",
    "Desen Dairesi",
    "Varyant Dairesi",
    "Kartela",
    "Personel (İK)",
    "Pazarlama",
    "Boyahane Baskı",
    "Boyahane Yıkama",
    "Boyahane Düzboya",
    "Sevkiyat",
    "Apre",
    "Çiğdepo",
    "Makina Enerji",
    "Satınalma",
    "Kalite Kontrol",
    "Laboratuvar",
    "Dokuma Kalite Kontrol",
    "Şardon",
    "Şablon",
    "Örme"
].sort(); // Alfabetik sıra
