#!/bin/bash
# ─────────────────────────────────────────────────────────
# Ollama Model Otomatik Güncelleme Script'i
# Her gece çalışır, yeni versiyon varsa modeli günceller.
# Cron: 0 3 * * * /opt/companyai/scripts/ollama_auto_update.sh
# ─────────────────────────────────────────────────────────

LOG_FILE="/var/log/ollama-auto-update.log"
MODEL="gpt-oss:20b"
SERVICE="companyai-backend"
LOCK_FILE="/tmp/ollama_update.lock"

# Aynı anda birden fazla çalışmasın
if [ -f "$LOCK_FILE" ]; then
    echo "$(date) | SKIP: Güncelleme zaten çalışıyor." >> "$LOG_FILE"
    exit 0
fi
touch "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

echo "$(date) | Güncelleme kontrolü başlıyor: $MODEL" >> "$LOG_FILE"

# Mevcut model digest'ini kaydet
OLD_DIGEST=$(ollama list | grep "$MODEL" | awk '{print $2}')

# Modeli güncelle (yeni varsa indirir, yoksa "up to date" der)
UPDATE_OUTPUT=$(ollama pull "$MODEL" 2>&1)
echo "$(date) | Pull çıktısı: $UPDATE_OUTPUT" >> "$LOG_FILE"

# Yeni digest kontrolü
NEW_DIGEST=$(ollama list | grep "$MODEL" | awk '{print $2}')

if [ "$OLD_DIGEST" != "$NEW_DIGEST" ] && [ -n "$NEW_DIGEST" ]; then
    echo "$(date) | YENİ VERSİYON TESPİT EDİLDİ!" >> "$LOG_FILE"
    echo "$(date) | Eski: $OLD_DIGEST → Yeni: $NEW_DIGEST" >> "$LOG_FILE"
    
    # Backend'i yeniden başlat (yeni modeli yüklemesi için)
    systemctl restart "$SERVICE"
    echo "$(date) | $SERVICE yeniden başlatıldı." >> "$LOG_FILE"
else
    echo "$(date) | Model güncel, değişiklik yok." >> "$LOG_FILE"
fi

# Ollama'yı da güncelle (varsa yeni versiyon)
OLLAMA_UPDATE=$(ollama --version 2>&1)
echo "$(date) | Ollama versiyonu: $OLLAMA_UPDATE" >> "$LOG_FILE"

# Eski modelleri temizle (opsiyonel — disk tasarrufu)
# ollama rm mistral:latest 2>/dev/null
# ollama rm qwen2.5:7b 2>/dev/null

echo "$(date) | Güncelleme kontrolü tamamlandı." >> "$LOG_FILE"
echo "---" >> "$LOG_FILE"
