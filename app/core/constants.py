"""
CompanyAI — Merkezi Sabitler (Constants)
==========================================
Tüm magic number'lar, eşik değerleri ve yapılandırma sabitleri.
Kod içinde dağınık sayılar yerine buradan import edin.
"""

# ═══════════════════════════════════════════════════
# Departman Listesi
# ═══════════════════════════════════════════════════

DEPARTMENTS = [
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
    "Personel",
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
    "Örme",
    "Genel"
]

# ═══════════════════════════════════════════════════
# RAG — Retrieval Augmented Generation
# ═══════════════════════════════════════════════════

RAG_CHUNK_SIZE = 2000          # Karakter — v4.4.0'da 2000'e yükseltildi
RAG_CHUNK_OVERLAP = 300        # Karakter overlap

# Hybrid search ağırlıkları
RAG_SEMANTIC_WEIGHT = 0.70
RAG_KEYWORD_WEIGHT = 0.30

# Aday çarpanı
RAG_CANDIDATE_MULTIPLIER = 3
RAG_MAX_CANDIDATES = 20

# Eşik değerleri
RAG_HYBRID_THRESHOLD = 0.12   # Minimum hybrid skor
RAG_DISTANCE_THRESHOLD = 1.4  # Maksimum ChromaDB distance

# RAG prompt limitleri
RAG_CONTENT_MAX_CHARS = 1500

# ═══════════════════════════════════════════════════
# Duplikasyon & Skor Ayarları
# ═══════════════════════════════════════════════════

DEDUP_DISTANCE_THRESHOLD = 0.15

# Kaynak tipi skor cezaları
PENALTY_WEB_LEARNED = 0.50
PENALTY_CHAT_LEARNED = 0.70

# Knowledge decay
DECAY_RATE_PER_YEAR = 0.20
DECAY_MIN_SCORE = 0.50

# ═══════════════════════════════════════════════════
# LLM — Ollama Parametreleri
# ═══════════════════════════════════════════════════

LLM_DEFAULT_TEMPERATURE = 0.7
LLM_MAX_TOKENS = 1024
LLM_STREAM_MAX_TOKENS = 1024
LLM_NUM_CTX = 8192
LLM_TIMEOUT_SECONDS = 900.0
LLM_MAX_CONNECTIONS = 10
LLM_MAX_KEEPALIVE = 5
LLM_HISTORY_TURNS = 5

# ═══════════════════════════════════════════════════
# Knowledge Extractor
# ═══════════════════════════════════════════════════

KE_MIN_TEXT_LENGTH = 20
KE_GENERAL_MIN_LENGTH = 50
KE_PURE_QUESTION_MAX_LENGTH = 80
KE_AI_RESPONSE_MIN_LENGTH = 80

# ═══════════════════════════════════════════════════
# Veritabanı
# ═══════════════════════════════════════════════════

DB_POOL_SIZE = 5
DB_MAX_OVERFLOW = 10

# ═══════════════════════════════════════════════════
# Deploy
# ═══════════════════════════════════════════════════

DEPLOY_HEALTH_CHECK_RETRIES = 4
DEPLOY_HEALTH_CHECK_INTERVAL = 4  # saniye

# ═══════════════════════════════════════════════════
# Embedding
# ═══════════════════════════════════════════════════

EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
EMBEDDING_DIMENSION = 768

# ═══════════════════════════════════════════════════
# Omni-Modal (MiniCPM-o 2.6)
# ═══════════════════════════════════════════════════

# Desteklenen medya türleri
ALLOWED_AUDIO_TYPES = {
    "audio/mpeg",          # .mp3
    "audio/wav",           # .wav
    "audio/x-wav",         # .wav (alternatif)
    "audio/ogg",           # .ogg
    "audio/flac",          # .flac
    "audio/webm",          # .webm audio
    "audio/aac",           # .aac
    "audio/mp4",           # .m4a
    "audio/x-m4a",         # .m4a (alternatif)
}

ALLOWED_VIDEO_TYPES = {
    "video/mp4",           # .mp4
    "video/webm",          # .webm
    "video/x-msvideo",     # .avi
    "video/quicktime",     # .mov
    "video/x-matroska",    # .mkv
}

# İşleme limitleri
OMNI_MAX_AUDIO_SIZE = 25 * 1024 * 1024     # 25 MB
OMNI_MAX_VIDEO_SIZE = 100 * 1024 * 1024    # 100 MB
OMNI_MAX_VIDEO_DURATION = 120              # saniye
OMNI_VIDEO_SAMPLE_FRAMES = 8              # Video'dan çıkarılacak kare sayısı
OMNI_AUDIO_SAMPLE_RATE = 16000            # Ses downsample Hz
