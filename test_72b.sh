#!/bin/bash
TOKEN=$(curl -sk -X POST https://localhost/api/auth/login -d 'username=admin@company.ai&password=admin123' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "=== TEST 1: merhaba ==="
curl -sk -X POST https://localhost/api/ask/multimodal -H "Authorization: Bearer $TOKEN" -F "question=merhaba"
echo ""
echo "=== TEST 2: ismimi biliyormusun ==="
curl -sk -X POST https://localhost/api/ask/multimodal -H "Authorization: Bearer $TOKEN" -F "question=ismimi biliyormusun"
echo ""
echo "=== TEST 3: bilgi sorusu ==="
curl -sk -X POST https://localhost/api/ask/multimodal -H "Authorization: Bearer $TOKEN" -F "question=Turkiye'nin baskenti neresidir"
echo ""
