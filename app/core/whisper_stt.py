"""Whisper Speech-to-Text Entegrasyonu (v4.4.0)

Sesli girdi desteği — kullanıcılar ses kaydı göndererek soru sorabilir.

Desteklenen modeller (öncelik sırasıyla):
1. faster-whisper (GPU hızlandırmalı, önerilen)  
2. openai-whisper (orijinal model)
3. Fallback: Hata mesajı

Desteklenen formatlar: wav, mp3, m4a, ogg, webm, flac
"""

import os
import io
import tempfile
from typing import Optional, Dict
import structlog

logger = structlog.get_logger()

# ── Model Yükleme ──
WHISPER_ENGINE = None  # "faster-whisper" | "openai-whisper" | None
_whisper_model = None

try:
    from faster_whisper import WhisperModel
    WHISPER_ENGINE = "faster-whisper"
except ImportError:
    try:
        import whisper
        WHISPER_ENGINE = "openai-whisper"
    except ImportError:
        WHISPER_ENGINE = None


# Konfigürasyon
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "medium")  # tiny/base/small/medium/large
WHISPER_LANGUAGE = "tr"  # Varsayılan Türkçe
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")  # cpu/cuda/auto

SUPPORTED_FORMATS = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac", ".mp4"}


def _get_device():
    """GPU varsa cuda, yoksa cpu."""
    if WHISPER_DEVICE != "auto":
        return WHISPER_DEVICE
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def get_whisper_model():
    """Whisper modelini lazy-load et (singleton)."""
    global _whisper_model
    
    if _whisper_model is not None:
        return _whisper_model
    
    if WHISPER_ENGINE == "faster-whisper":
        try:
            device = _get_device()
            compute_type = "float16" if device == "cuda" else "int8"
            _whisper_model = WhisperModel(
                WHISPER_MODEL_SIZE,
                device=device,
                compute_type=compute_type,
            )
            logger.info("whisper_loaded",
                       engine="faster-whisper",
                       model=WHISPER_MODEL_SIZE,
                       device=device)
            return _whisper_model
        except Exception as e:
            logger.error("faster_whisper_load_failed", error=str(e))
    
    elif WHISPER_ENGINE == "openai-whisper":
        try:
            import whisper
            _whisper_model = whisper.load_model(WHISPER_MODEL_SIZE)
            logger.info("whisper_loaded",
                       engine="openai-whisper",
                       model=WHISPER_MODEL_SIZE)
            return _whisper_model
        except Exception as e:
            logger.error("openai_whisper_load_failed", error=str(e))
    
    return None


def transcribe_audio(
    audio_bytes: bytes,
    language: str = None,
    filename: str = "audio.wav",
) -> Dict:
    """Ses dosyasını metne çevir.
    
    Args:
        audio_bytes: Ses dosyası içeriği
        language: Dil kodu ("tr", "en", vb.) — None ise otomatik algıla
        filename: Orijinal dosya adı (format tespiti için)
    
    Returns:
        {
            "success": bool,
            "text": str,              # Transkript
            "language": str,          # Algılanan dil
            "duration_seconds": float,
            "confidence": float,      # 0-1
            "engine": str,
            "segments": list,         # Zaman damgalı segmentler
        }
    """
    if not WHISPER_ENGINE:
        return {
            "success": False,
            "text": "",
            "error": "Whisper yüklü değil. 'pip install faster-whisper' veya 'pip install openai-whisper' çalıştırın.",
            "engine": None,
        }
    
    # Dosya formatı kontrolü
    ext = os.path.splitext(filename)[1].lower()
    if ext and ext not in SUPPORTED_FORMATS:
        return {
            "success": False,
            "text": "",
            "error": f"Desteklenmeyen format: {ext}. Desteklenen: {', '.join(SUPPORTED_FORMATS)}",
        }
    
    lang = language or WHISPER_LANGUAGE
    model = get_whisper_model()
    
    if not model:
        return {
            "success": False,
            "text": "",
            "error": "Whisper modeli yüklenemedi.",
        }
    
    # Geçici dosyaya yaz (Whisper dosya yolu bekler)
    try:
        with tempfile.NamedTemporaryFile(suffix=ext or ".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        
        if WHISPER_ENGINE == "faster-whisper":
            return _transcribe_faster_whisper(model, tmp_path, lang)
        else:
            return _transcribe_openai_whisper(model, tmp_path, lang)
    
    except Exception as e:
        logger.error("transcribe_failed", error=str(e))
        return {
            "success": False,
            "text": "",
            "error": str(e),
        }
    finally:
        # Geçici dosyayı temizle
        try:
            if 'tmp_path' in locals():
                os.unlink(tmp_path)
        except OSError:
            pass


def _transcribe_faster_whisper(model, audio_path: str, language: str) -> Dict:
    """faster-whisper ile transkript."""
    segments, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=5,
        vad_filter=True,  # Sessiz bölümleri atla
    )
    
    text_parts = []
    segment_list = []
    total_confidence = 0.0
    seg_count = 0
    
    for segment in segments:
        text_parts.append(segment.text.strip())
        segment_list.append({
            "start": round(segment.start, 2),
            "end": round(segment.end, 2),
            "text": segment.text.strip(),
        })
        # avg_logprob → confidence dönüşümü
        import math
        conf = math.exp(segment.avg_log_prob) if segment.avg_log_prob else 0.5
        total_confidence += min(conf, 1.0)
        seg_count += 1
    
    full_text = " ".join(text_parts)
    avg_confidence = total_confidence / seg_count if seg_count > 0 else 0
    
    logger.info("whisper_transcribed",
               engine="faster-whisper",
               language=info.language,
               duration=round(info.duration, 1),
               text_len=len(full_text))
    
    return {
        "success": True,
        "text": full_text,
        "language": info.language,
        "duration_seconds": round(info.duration, 2),
        "confidence": round(avg_confidence, 3),
        "engine": "faster-whisper",
        "segments": segment_list,
    }


def _transcribe_openai_whisper(model, audio_path: str, language: str) -> Dict:
    """openai-whisper ile transkript."""
    import whisper
    
    result = whisper.transcribe(
        model,
        audio_path,
        language=language,
        fp16=False,
    )
    
    text = result.get("text", "").strip()
    segments = result.get("segments", [])
    
    segment_list = []
    total_confidence = 0.0
    
    for seg in segments:
        segment_list.append({
            "start": round(seg["start"], 2),
            "end": round(seg["end"], 2),
            "text": seg["text"].strip(),
        })
        # no_speech_prob → confidence
        conf = 1.0 - seg.get("no_speech_prob", 0.5)
        total_confidence += max(0, conf)
    
    avg_confidence = total_confidence / len(segments) if segments else 0
    duration = segments[-1]["end"] if segments else 0
    
    logger.info("whisper_transcribed",
               engine="openai-whisper",
               language=result.get("language", language),
               duration=round(duration, 1),
               text_len=len(text))
    
    return {
        "success": True,
        "text": text,
        "language": result.get("language", language),
        "duration_seconds": round(duration, 2),
        "confidence": round(avg_confidence, 3),
        "engine": "openai-whisper",
        "segments": segment_list,
    }


def get_whisper_status() -> Dict:
    """Whisper motorunun durumunu döndür."""
    return {
        "available": WHISPER_ENGINE is not None,
        "engine": WHISPER_ENGINE,
        "model_size": WHISPER_MODEL_SIZE,
        "default_language": WHISPER_LANGUAGE,
        "device": _get_device() if WHISPER_ENGINE else None,
        "supported_formats": list(SUPPORTED_FORMATS),
        "model_loaded": _whisper_model is not None,
    }
