"""Export servisi testi — Excel, PDF, PPTX üretimi"""

import sys
sys.path.insert(0, '/opt/companyai')

from app.core.export_service import detect_export_request, generate_export

# Test 1: Format tespiti
test_queries = [
    ("Bana şirket bütçesini excel olarak hazırla", "excel"),
    ("Departman raporunu PDF dosyası olarak ver", "pdf"),
    ("Şirket tanıtım sunumu hazırla", "pptx"),
    ("Word formatında rapor oluştur", "word"),
    ("İnegöl hava durumu", None),
]

print("=== FORMAT TESPİTİ ===")
for q, expected in test_queries:
    result = detect_export_request(q)
    status = "✅" if result == expected else "❌"
    print(f"  {status} '{q[:50]}' → {result} (expected: {expected})")

# Test 2: Excel üretimi
print("\n=== EXCEL ÜRETİMİ ===")
test_content = """## Aylık Satış Raporu

| Ay | Satış (TL) | Hedef (TL) | Gerçekleşme |
|---|---|---|---|
| Ocak | 450.000 | 500.000 | %90 |
| Şubat | 520.000 | 500.000 | %104 |
| Mart | 480.000 | 550.000 | %87 |

### Özet
- Toplam satış: 1.450.000 TL
- Ortalama gerçekleşme: %93.7
"""

result = generate_export(test_content, "excel", "Aylik Satis Raporu")
if result:
    print(f"  ✅ Excel: {result['filename']} (file_id: {result['file_id']})")
else:
    print("  ❌ Excel oluşturulamadı")

# Test 3: PDF üretimi
print("\n=== PDF ÜRETİMİ ===")
result = generate_export(test_content, "pdf", "Satis Raporu PDF")
if result:
    print(f"  ✅ PDF: {result['filename']} (file_id: {result['file_id']})")
else:
    print("  ❌ PDF oluşturulamadı")

# Test 4: PPTX üretimi
print("\n=== PPTX ÜRETİMİ ===")
result = generate_export(test_content, "pptx", "Satis Sunumu")
if result:
    print(f"  ✅ PPTX: {result['filename']} (file_id: {result['file_id']})")
else:
    print("  ❌ PPTX oluşturulamadı")

# Test 5: Word üretimi
print("\n=== WORD ÜRETİMİ ===")
result = generate_export(test_content, "word", "Satis Raporu Word")
if result:
    print(f"  ✅ Word: {result['filename']} (file_id: {result['file_id']})")
else:
    print("  ❌ Word oluşturulamadı")

print("\n✅ Tüm testler tamamlandı")
