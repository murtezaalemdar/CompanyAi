"""Sesli Saha Asistanı — STT / TTS Entegrasyon Modülü

Saha çalışanlarının sesli komutlarla AI asistanı kullanmasını sağlar.

Desteklenen Teknolojiler:
  - STT (Speech-to-Text): Whisper (OpenAI) lokal model
  - TTS (Text-to-Speech): pyttsx3 (offline) / gTTS (online fallback)
"""

import io
import asyncio
import tempfile
import os
from typing import Optional
import structlog

logger = structlog.get_logger()

# ── STT Motor ──────────────────────────────────────────────────────

_whisper_model = None


def _get_whisper_model():
    """Whisper modelini lazy-load eder (ilk çağrıda yüklenir)."""
    global _whisper_model
    if _whisper_model is None:
        try:
            import whisper
            _whisper_model = whisper.load_model("base")  # tiny / base / small
            logger.info("whisper_model_loaded", model="base")
        except ImportError:
            logger.error("whisper_not_installed",
                         hint="pip install openai-whisper")
            raise RuntimeError(
                "Whisper yüklü değil. Kurmak için: pip install openai-whisper"
            )
    return _whisper_model


async def speech_to_text(
    audio_bytes: bytes,
    language: str = "tr",
) -> dict:
    """
    Ses verisini metne çevirir (Whisper lokal).

    Args:
        audio_bytes: WAV/MP3/OGG formatında ses verisi
        language: Dil kodu (varsayılan: Türkçe)

    Returns:
        {"text": str, "language": str, "duration": float}
    """
    try:
        model = _get_whisper_model()

        # Geçici dosyaya yaz (Whisper dosya yolu istiyor)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        # Async → sync bridge (Whisper sync çalışır)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: model.transcribe(tmp_path, language=language),
        )

        os.unlink(tmp_path)

        text = result.get("text", "").strip()
        duration = result.get("segments", [{}])[-1].get("end", 0) if result.get("segments") else 0

        logger.info("stt_success", text_length=len(text), language=language)

        return {
            "text": text,
            "language": language,
            "duration": round(duration, 2),
        }

    except RuntimeError:
        raise
    except Exception as e:
        logger.error("stt_error", error=str(e))
        return {"text": "", "language": language, "duration": 0, "error": str(e)}


# ── TTS Motor ──────────────────────────────────────────────────────

async def text_to_speech(
    text: str,
    language: str = "tr",
    engine: str = "pyttsx3",
) -> Optional[bytes]:
    """
    Metni sese çevirir.

    Args:
        text: Okunacak metin
        language: Dil kodu
        engine: "pyttsx3" (offline) veya "gtts" (online)

    Returns:
        WAV/MP3 formatında ses verisi (bytes) veya None
    """
    if engine == "pyttsx3":
        return await _tts_pyttsx3(text)
    elif engine == "gtts":
        return await _tts_gtts(text, language)
    else:
        logger.error("tts_unknown_engine", engine=engine)
        return None


async def _tts_pyttsx3(text: str) -> Optional[bytes]:
    """Offline TTS — pyttsx3 kullanarak ses üretir."""
    try:
        import pyttsx3

        loop = asyncio.get_event_loop()

        def _generate():
            eng = pyttsx3.init()
            eng.setProperty("rate", 150)

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            tmp.close()
            eng.save_to_file(text, tmp.name)
            eng.runAndWait()

            with open(tmp.name, "rb") as f:
                data = f.read()
            os.unlink(tmp.name)
            return data

        audio = await loop.run_in_executor(None, _generate)
        logger.info("tts_pyttsx3_success", text_length=len(text))
        return audio

    except ImportError:
        logger.warning("pyttsx3_not_installed", hint="pip install pyttsx3")
        return None
    except Exception as e:
        logger.error("tts_pyttsx3_error", error=str(e))
        return None


async def _tts_gtts(text: str, language: str = "tr") -> Optional[bytes]:
    """Online TTS fallback — gTTS kullanarak ses üretir."""
    try:
        from gtts import gTTS

        loop = asyncio.get_event_loop()

        def _generate():
            tts = gTTS(text=text, lang=language)
            buf = io.BytesIO()
            tts.write_to_fp(buf)
            return buf.getvalue()

        audio = await loop.run_in_executor(None, _generate)
        logger.info("tts_gtts_success", text_length=len(text))
        return audio

    except ImportError:
        logger.warning("gtts_not_installed", hint="pip install gtts")
        return None
    except Exception as e:
        logger.error("tts_gtts_error", error=str(e))
        return None


# ── Durum Kontrolü ─────────────────────────────────────────────────

def get_voice_status() -> dict:
    """Sesli asistan bileşenlerinin durumunu döner."""
    status = {
        "stt_engine": "whisper",
        "tts_engine": "pyttsx3",
        "stt_available": False,
        "tts_available": False,
    }

    try:
        import whisper  # noqa: F401
        status["stt_available"] = True
    except ImportError:
        pass

    try:
        import pyttsx3  # noqa: F401
        status["tts_available"] = True
        status["tts_engine"] = "pyttsx3"
    except ImportError:
        try:
            from gtts import gTTS  # noqa: F401
            status["tts_available"] = True
            status["tts_engine"] = "gtts"
        except ImportError:
            pass

    return status