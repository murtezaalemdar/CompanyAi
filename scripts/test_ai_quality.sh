#!/bin/bash

echo "=== AI Kalite Testi Başlıyor ==="

# 1. Token Al
echo "Token alınıyor..."
RESP=$(curl -k -s -X POST https://localhost/api/auth/login -d "username=admin@company.ai&password=admin123")
TOKEN=$(echo $RESP | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
    echo "Hata: Token alınamadı!"
    echo "Yanıt: $RESP"
    exit 1
fi
echo "Token başarıyla alındı."

# 2. Soru Sor
QUESTION="Proje Samba ve 2026 enerji hedeflerimiz nelerdir?"
echo "Soru soruluyor: $QUESTION"
echo "----------------------------------------"

RESPONSE=$(curl -k -s -X POST https://localhost/api/ask \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"$QUESTION\"}")

# Yanıtı parse et (jq varsa)
if command -v jq &> /dev/null; then
    echo $RESPONSE | jq .answer
else
    echo $RESPONSE
fi

echo ""
echo "----------------------------------------"
echo "test tamamlandı."
