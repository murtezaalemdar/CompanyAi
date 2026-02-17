"""Multimodal AI API Routes - Dosya, Resim, Video ve Ses Destekli Soru-Cevap

v4.5.0: MiniCPM-o 2.6 omni-modal entegrasyonu
  - Video analizi (kare örnekleme + omni model)
  - Ses analizi (base64 encode + omni model)
  - Akıllı model yönlendirme (metin→qwen, görsel→minicpm-v, video/ses→minicpm-o)
"""

import time
import os
import json
import base64
import tempfile
import io
from PIL import Image
from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.database import get_db
from app.db.models import User, Query
from app.api.routes.auth import get_current_user
from app.core.engine import process_question
from app.llm.client import ollama_client
from app.config import settings
from app.core.constants import (
    ALLOWED_AUDIO_TYPES, ALLOWED_VIDEO_TYPES,
    OMNI_MAX_AUDIO_SIZE, OMNI_MAX_VIDEO_SIZE,
    OMNI_VIDEO_SAMPLE_FRAMES,
)
from app.memory.persistent_memory import (
    is_forget_command, forget_everything,
    save_conversation, get_conversation_history,
    extract_and_save_preferences, build_memory_context,
    get_active_session, update_session_title,
    extract_and_save_culture,
)

import structlog

logger = structlog.get_logger()

# Otomatik öğrenme motoru
try:
    from app.core.knowledge_extractor import (
        learn_from_conversation, learn_from_file_context
    )
    KNOWLEDGE_EXTRACTOR_AVAILABLE = True
except ImportError:
    KNOWLEDGE_EXTRACTOR_AVAILABLE = False

router = APIRouter()

# Desteklenen dosya türleri
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp"}
ALLOWED_DOCUMENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
    "text/csv",
    "application/json",
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_FILES = 10


class MultimodalResponse(BaseModel):
    answer: str
    department: str
    mode: str
    risk_level: str
    confidence: float
    processing_time_ms: int
    files_processed: int
    rich_data: Optional[list] = None
    media_type: Optional[str] = None  # v4.5.0: "image", "video", "audio", "document", "mixed"


def get_file_type(content_type: str) -> str:
    """Dosya türünü belirle"""
    if content_type in ALLOWED_IMAGE_TYPES:
        return "image"
    elif content_type in ALLOWED_DOCUMENT_TYPES:
        return "document"
    elif content_type in ALLOWED_AUDIO_TYPES:
        return "audio"
    elif content_type in ALLOWED_VIDEO_TYPES:
        return "video"
    else:
        return "unknown"


async def process_audio_content(file: UploadFile) -> dict:
    """Ses dosyasını işle — MiniCPM-o 2.6 için base64 encode.
    
    Desteklenen formatlar: mp3, wav, ogg, flac, webm, aac, m4a
    Büyük dosyalar otomatik olarak reddedilir (25MB limit).
    """
    content = await file.read()
    
    if len(content) > OMNI_MAX_AUDIO_SIZE:
        return {
            "type": "audio",
            "filename": file.filename,
            "error": f"Ses dosyası çok büyük ({len(content) // (1024*1024)}MB > {OMNI_MAX_AUDIO_SIZE // (1024*1024)}MB)",
        }
    
    try:
        # Süre bilgisini çıkarmayı dene (opsiyonel)
        duration_seconds = None
        try:
            import struct
            # WAV dosyası ise süre hesapla
            if file.content_type in {"audio/wav", "audio/x-wav"} and len(content) > 44:
                # WAV header: byte 24-28=sample_rate, 28-32=byte_rate
                byte_rate = struct.unpack_from("<I", content, 28)[0]
                if byte_rate > 0:
                    data_size = len(content) - 44
                    duration_seconds = round(data_size / byte_rate, 1)
        except Exception:
            pass
        
        base64_content = base64.b64encode(content).decode('utf-8')
        
        result = {
            "type": "audio",
            "filename": file.filename,
            "content_type": file.content_type,
            "size": len(content),
            "base64": base64_content,
        }
        if duration_seconds:
            result["duration_seconds"] = duration_seconds
        
        return result
        
    except Exception as e:
        logger.error("audio_processing_failed", filename=file.filename, error=str(e))
        return {
            "type": "audio",
            "filename": file.filename,
            "error": str(e),
        }


async def process_video_content(file: UploadFile) -> dict:
    """Video dosyasını işle — MiniCPM-o 2.6 için kare örnekleme.
    
    Video'dan eşit aralıklı kareler çıkarılır ve base64 encode edilir.
    Her kare 512px'e küçültülür (VRAM tasarrufu).
    """
    content = await file.read()
    
    if len(content) > OMNI_MAX_VIDEO_SIZE:
        return {
            "type": "video",
            "filename": file.filename,
            "error": f"Video dosyası çok büyük ({len(content) // (1024*1024)}MB > {OMNI_MAX_VIDEO_SIZE // (1024*1024)}MB)",
        }
    
    try:
        # Geçici dosyaya yaz (cv2 dosya yolu gerektirir)
        suffix = os.path.splitext(file.filename)[1] or ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        frames_b64 = []
        duration_seconds = None
        frame_count = 0
        fps = 0
        
        try:
            import cv2
            cap = cv2.VideoCapture(tmp_path)
            
            if not cap.isOpened():
                raise ValueError("Video açılamadı")
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 24
            duration_seconds = round(total_frames / fps, 1) if fps > 0 else None
            frame_count = total_frames
            
            # Eşit aralıklı OMNI_VIDEO_SAMPLE_FRAMES kare seç
            n_samples = min(OMNI_VIDEO_SAMPLE_FRAMES, total_frames)
            if n_samples <= 0:
                raise ValueError("Video'da kare bulunamadı")
                
            indices = [int(i * total_frames / n_samples) for i in range(n_samples)]
            
            for idx in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                if not ret:
                    continue
                
                # BGR → RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)
                
                # 512px'e küçült (VRAM tasarrufu)
                max_dim = 512
                if max(pil_img.size) > max_dim:
                    pil_img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                
                # Base64 encode (WebP)
                buf = io.BytesIO()
                pil_img.save(buf, format="WEBP", quality=75)
                b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                frames_b64.append(b64)
            
            cap.release()
            
        except ImportError:
            logger.warning("opencv_not_installed", msg="cv2 yüklü değil, video kare çıkarma devre dışı")
            # Fallback: Video'yu komple base64 olarak gönder (model destekliyorsa)
            frames_b64 = [base64.b64encode(content).decode('utf-8')]
        
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        
        return {
            "type": "video",
            "filename": file.filename,
            "content_type": file.content_type,
            "size": len(content),
            "frames": frames_b64,
            "frame_count": frame_count,
            "sampled_frames": len(frames_b64),
            "fps": round(fps, 1),
            "duration_seconds": duration_seconds,
        }
        
    except Exception as e:
        logger.error("video_processing_failed", filename=file.filename, error=str(e))
        return {
            "type": "video",
            "filename": file.filename,
            "error": str(e),
        }


async def process_image_content(file: UploadFile) -> dict:
    """Resim dosyasını işle ve optimize et (1024px, WebP, %80 Kalite)"""
    content = await file.read()
    
    try:
        # PIL ile resmi aç
        image = Image.open(io.BytesIO(content))
        
        # RGB'ye çevir (PNG transparan olsa bile arka planı beyaz yapabiliriz veya olduğu gibi bırakabiliriz)
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')
            
        # Boyutlandırma (Max 1024px)
        max_size = 1024
        if max(image.size) > max_size:
            # Aspect ratio koruyarak küçült
            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
        # WebP olarak sıkıştır (Buffer'a kaydet)
        buffer = io.BytesIO()
        image.save(buffer, format="WEBP", quality=80, optimize=True)
        optimized_content = buffer.getvalue()
        
        base64_content = base64.b64encode(optimized_content).decode('utf-8')
        
        return {
            "type": "image",
            "filename": f"{file.filename.rsplit('.', 1)[0]}.webp",
            "content_type": "image/webp",
            "size": len(optimized_content),
            "original_size": len(content),
            "width": image.width,
            "height": image.height,
            "base64": base64_content,
        }
    except Exception as e:
        logger.error("image_optimization_failed", filename=file.filename, error=str(e))
        # Hata durumunda orijinali kullan
        base64_content = base64.b64encode(content).decode('utf-8')
        return {
            "type": "image",
            "filename": file.filename,
            "content_type": file.content_type,
            "size": len(content),
            "base64": base64_content,
            "error": "Optimization failed"
        }


async def process_document_content(file: UploadFile) -> dict:
    """Doküman dosyasını işle ve metin çıkar"""
    content = await file.read()
    text_content = ""
    
    # Basit metin dosyaları
    if file.content_type in {"text/plain", "text/csv", "application/json"}:
        try:
            text_content = content.decode('utf-8')
        except UnicodeDecodeError:
            text_content = content.decode('latin-1', errors='ignore')
    
    # PDF dosyaları için
    elif file.content_type == "application/pdf":
        try:
            import fitz  # PyMuPDF
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            doc = fitz.open(tmp_path)
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())
            text_content = "\n".join(text_parts)
            doc.close()
            os.unlink(tmp_path)
        except ImportError:
            logger.warning("PyMuPDF not installed, PDF text extraction skipped")
            text_content = f"[PDF dosyası: {file.filename}]"
        except Exception as e:
            logger.error("pdf_extraction_error", error=str(e))
            text_content = f"[PDF okuma hatası: {file.filename}]"
    
    # Word dosyaları için
    elif file.content_type in {
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }:
        try:
            from docx import Document
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            doc = Document(tmp_path)
            text_parts = [para.text for para in doc.paragraphs]
            text_content = "\n".join(text_parts)
            os.unlink(tmp_path)
        except ImportError:
            logger.warning("python-docx not installed, Word text extraction skipped")
            text_content = f"[Word dosyası: {file.filename}]"
        except Exception as e:
            logger.error("docx_extraction_error", error=str(e))
            text_content = f"[Word okuma hatası: {file.filename}]"
    
    # Excel dosyaları için (v5.10.1: RAG-optimized row-by-row)
    elif file.content_type in {
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    }:
        try:
            import pandas as pd
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            xls = pd.ExcelFile(tmp_path)
            all_rows_text = []
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                if df.empty:
                    continue
                if len(xls.sheet_names) > 1:
                    all_rows_text.append(f"\n[Sayfa: {sheet_name}]")
                columns = [str(c).strip() for c in df.columns]
                for idx, row in df.iterrows():
                    parts = []
                    for col in columns:
                        val = row[col]
                        if pd.notna(val):
                            val_str = str(val).strip()
                            if val_str:
                                parts.append(f"{col}: {val_str}")
                    if parts:
                        all_rows_text.append(f"{file.filename} | Satır {idx + 1}: {', '.join(parts)}")
            text_content = "\n".join(all_rows_text)
            os.unlink(tmp_path)
        except ImportError:
            logger.warning("pandas/openpyxl not installed, Excel text extraction skipped")
            text_content = f"[Excel dosyası: {file.filename}]"
        except Exception as e:
            logger.error("excel_extraction_error", error=str(e))
            text_content = f"[Excel okuma hatası: {file.filename}]"
    
    return {
        "type": "document",
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(content),
        "text": text_content[:10000] if text_content else "",  # Max 10K karakter
    }


MAX_HISTORY_FOR_LLM = 20


@router.post("/ask/multimodal", response_model=MultimodalResponse)
async def ask_ai_multimodal(
    question: str = Form(...),
    department: Optional[str] = Form(None),
    files: List[UploadFile] = File(default=[]),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Multimodal AI soru-cevap - Dosya ve resim desteği ile.
    Kalıcı hafıza: PostgreSQL'de saklanır, "unut" deyince silinir.
    """
    start_time = time.time()
    
    # ── "Unut" komutu kontrolü ──
    if is_forget_command(question):
        stats = await forget_everything(db, current_user.id)
        await db.commit()
        processing_time = int((time.time() - start_time) * 1000)
        return MultimodalResponse(
            answer=f"Tamam, tüm konuşma geçmişini ve hatırladığım bilgileri sildim. "
                   f"({stats['conversations_deleted']} konuşma, {stats['preferences_deleted']} bilgi silindi) "
                   f"Artık temiz bir sayfa ile başlıyoruz!",
            department="Genel",
            mode="Sohbet",
            risk_level="Düşük",
            confidence=1.0,
            processing_time_ms=processing_time,
            files_processed=0,
        )
    
    # Kullanıcı bilgilerini çıkar ve kaydet
    await extract_and_save_preferences(db, current_user.id, question)
    
    # Aktif oturumu al (yoksa oluştur)
    active_session = await get_active_session(db, current_user.id)
    session_id = active_session["id"] if active_session else None
    
    # Kalıcı hafıza: PostgreSQL'den geçmiş yükle (aktif session bazlı)
    session_history = await get_conversation_history(db, current_user.id, limit=MAX_HISTORY_FOR_LLM, session_id=session_id)
    memory_ctx = await build_memory_context(db, current_user.id)
    
    # Departman yetki kontrolü
    import json
    user_departments = []
    if current_user.department:
        try:
            parsed = json.loads(current_user.department)
            user_departments = parsed if isinstance(parsed, list) else [current_user.department]
        except json.JSONDecodeError:
            user_departments = [current_user.department]
    
    # Eğer user rolü ise departman kontrolü yap
    if current_user.role == 'user':
        if department and department not in user_departments:
            # Yetkisiz departman seçilmiş, ilk yetkili departmanı kullan
            department = user_departments[0] if user_departments else None
        elif not department:
            # Departman belirtilmemişse ilk yetkili departmanı kullan
            department = user_departments[0] if user_departments else None
    
    # Dosya sayısını kontrol et
    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"En fazla {MAX_FILES} dosya yüklenebilir"
        )
    
    processed_files = []
    context_parts = []
    image_base64_list = []
    audio_base64_list = []    # v4.5.0: Ses dosyaları
    video_frames_list = []    # v4.5.0: Video kareleri
    has_audio = False
    has_video = False
    
    # Dosyaları işle
    for file in files:
        # Dosya boyutunu kontrol et
        content = await file.read()
        await file.seek(0)  # Reset file pointer
        
        if len(content) > MAX_FILE_SIZE:
            logger.warning("file_too_large", filename=file.filename, size=len(content))
            continue
        
        file_type = get_file_type(file.content_type)
        
        if file_type == "image":
            processed = await process_image_content(file)
            processed_files.append(processed)
            # Vision LLM için base64 resmi topla
            if processed.get("base64"):
                image_base64_list.append(processed["base64"])
            context_parts.append(f"[Resim eklendi: {file.filename}]")
        
        elif file_type == "audio":
            processed = await process_audio_content(file)
            processed_files.append(processed)
            has_audio = True
            if processed.get("base64"):
                audio_base64_list.append(processed["base64"])
                dur = processed.get("duration_seconds")
                dur_str = f" ({dur}s)" if dur else ""
                context_parts.append(f"[Ses dosyası eklendi: {file.filename}{dur_str}]")
            elif processed.get("error"):
                context_parts.append(f"[Ses hatası: {processed['error']}]")
        
        elif file_type == "video":
            processed = await process_video_content(file)
            processed_files.append(processed)
            has_video = True
            if processed.get("frames"):
                video_frames_list.extend(processed["frames"])
                dur = processed.get("duration_seconds")
                dur_str = f" ({dur}s, {processed.get('sampled_frames', 0)} kare)" if dur else ""
                context_parts.append(f"[Video eklendi: {file.filename}{dur_str}]")
            elif processed.get("error"):
                context_parts.append(f"[Video hatası: {processed['error']}]")
            
        elif file_type == "document":
            processed = await process_document_content(file)
            processed_files.append(processed)
            if processed.get("text"):
                context_parts.append(f"--- İçerik: {file.filename} ---\n{processed['text']}\n---")
            else:
                context_parts.append(f"[Doküman eklendi: {file.filename}]")
        else:
            logger.warning("unsupported_file_type", filename=file.filename, content_type=file.content_type)
    
    # v4.5.0: Medya türünü belirle
    media_types = set()
    if image_base64_list:
        media_types.add("image")
    if has_audio:
        media_types.add("audio")
    if has_video:
        media_types.add("video")
    if any(p["type"] == "document" for p in processed_files):
        media_types.add("document")
    media_type = "mixed" if len(media_types) > 1 else (media_types.pop() if media_types else None)
    
    # Omni-modal gereksinimi: video veya ses dosyası varsa MiniCPM-o 2.6 kullan
    use_omni = has_audio or has_video
    
    # Soru ile bağlamı birleştir
    enhanced_question = question
    if context_parts:
        file_context = "\n\n".join(context_parts)
        
        # v4.5.0: Medya türüne göre prompt oluştur
        if has_video and has_audio:
            enhanced_question = f"""Kullanıcı video ve ses dosyaları paylaştı:

{file_context}

Kullanıcının sorusu: {question}

Lütfen paylaşılan video karelerini ve ses içeriğini analiz ederek soruyu cevapla. Video'dan görsel detayları, ses'ten ise konuşma veya sesli bilgiyi çıkar."""
        elif has_video:
            enhanced_question = f"""Kullanıcı video dosyası paylaştı. Aşağıda video'dan eşit aralıklarla alınmış kareler var:

{file_context}

Kullanıcının sorusu: {question}

Lütfen video karelerini inceleyerek sahneleri, nesneleri ve olayları analiz et."""
        elif has_audio:
            enhanced_question = f"""Kullanıcı ses dosyası paylaştı:

{file_context}

Kullanıcının sorusu: {question}

Lütfen ses içeriğini analiz ederek (konuşma, müzik, ses efektleri vb.) soruyu cevapla."""
        else:
            enhanced_question = f"""Kullanıcı aşağıdaki dosyaları paylaştı:

{file_context}

Kullanıcının sorusu: {question}

Lütfen paylaşılan dosya içeriklerini dikkate alarak soruyu cevapla."""
    
    try:
        # ── v4.5.0: Omni-modal akış (video/ses → MiniCPM-o 2.6) ──
        all_media_b64 = []
        if use_omni:
            # Video kareleri + resimler + ses dosyalarını birleştir
            all_media_b64 = video_frames_list + image_base64_list + audio_base64_list
        
        # Eğer medya varsa (resim, video karesi, ses) → vision/omni LLM'e gönder
        if image_base64_list or all_media_b64:
            media_to_send = all_media_b64 if use_omni else image_base64_list
            try:
                from app.llm.prompts import build_prompt
                from app.router.router import decide
                context = decide(question)
                if department:
                    context["dept"] = department
                system_prompt, user_prompt = build_prompt(enhanced_question, context)
                
                vision_answer = await ollama_client.generate(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    images=media_to_send,
                    use_omni=use_omni,
                )
                
                processing_time = int((time.time() - start_time) * 1000)
                
                # v4.5.0: Kullanılan modeli logla
                model_used = "minicpm-o (omni)" if use_omni else "minicpm-v (vision)"
                logger.info("omni_vision_completed", model=model_used,
                            media_count=len(media_to_send),
                            media_type=media_type,
                            processing_time_ms=processing_time)
                
                result = {
                    "answer": vision_answer,
                    "department": context["dept"],
                    "mode": context["mode"],
                    "risk": context["risk"],
                    "confidence": 0.90 if use_omni else 0.88,
                }
                
                # Sorguyu kaydet
                query_obj = Query(
                    user_id=current_user.id,
                    question=question,
                    answer=result["answer"],
                    department=result["department"],
                    mode=result["mode"],
                    risk_level=result["risk"],
                    confidence=result["confidence"],
                    processing_time_ms=processing_time,
                )
                db.add(query_obj)
                
                # Konuşmayı hafızaya kaydet (vision) — session_id ile
                await save_conversation(
                    db, current_user.id, question, result["answer"],
                    department=result["department"], session_id=session_id,
                )
                if session_id:
                    await update_session_title(db, session_id, question)
                await extract_and_save_culture(db, current_user.id, question, result["answer"])
                await db.commit()
                
                # ── OTOMATİK ÖĞRENME — Vision: arka planda öğren ──
                if KNOWLEDGE_EXTRACTOR_AVAILABLE:
                    import asyncio
                    try:
                        _uname = current_user.full_name or current_user.email.split("@")[0]
                        asyncio.get_event_loop().run_in_executor(
                            None, learn_from_conversation,
                            question, result["answer"], _uname, result["department"], False,
                        )
                    except Exception:
                        pass
                
                return MultimodalResponse(
                    answer=result["answer"],
                    department=result["department"],
                    mode=result["mode"],
                    risk_level=result["risk"],
                    confidence=result["confidence"],
                    processing_time_ms=processing_time,
                    files_processed=len(processed_files),
                    media_type=media_type,
                )
            except Exception as vision_err:
                logger.warning("vision_omni_fallback", error=str(vision_err),
                               use_omni=use_omni, media_type=media_type)
                # Vision/Omni model yoksa normal akışa devam et

        # Normal metin tabanlı akış (resim yoksa veya vision başarısızsa)
        result = await process_question(
            enhanced_question, 
            department_override=department,
            user_name=current_user.full_name or current_user.email.split("@")[0],
            user_department=department,
            session_history=session_history,
            memory_context=memory_ctx,
        )
        
        # Konuşmayı kalıcı hafızaya kaydet (PostgreSQL) — session_id ile
        await save_conversation(
            db, current_user.id, question, result["answer"],
            department=result.get("department"), intent=result.get("intent"),
            session_id=session_id,
        )
        
        # Oturum başlığını ilk sorudan oluştur
        if session_id:
            await update_session_title(db, session_id, question)
        
        # Şirket kültürü sinyallerini çıkar ve kaydet
        await extract_and_save_culture(db, current_user.id, question, result["answer"])
        
        # ── OTOMATİK ÖĞRENME — Multimodal: arka planda öğren ──
        if KNOWLEDGE_EXTRACTOR_AVAILABLE:
            import asyncio
            try:
                _uname = current_user.full_name or current_user.email.split("@")[0]
                # Dosya bağlamını arka planda öğren
                for pf in processed_files:
                    if pf.get("text") and len(pf["text"]) > 30:
                        asyncio.get_event_loop().run_in_executor(
                            None, learn_from_file_context,
                            pf.get("filename", "dosya"), question,
                            pf["text"][:3000], _uname, result.get("department"),
                        )
                # Konuşmayı arka planda öğren
                asyncio.get_event_loop().run_in_executor(
                    None, learn_from_conversation,
                    question, result["answer"], _uname,
                    result.get("department"), bool(result.get("rag_used")),
                )
            except Exception:
                pass  # Öğrenme hatası ana akışı kırmamalı
        
        processing_time = int((time.time() - start_time) * 1000)
        
        # Sorguyu kaydet
        query = Query(
            user_id=current_user.id,
            question=question,
            answer=result["answer"],
            department=result["department"],
            mode=result["mode"],
            risk_level=result["risk"],
            confidence=result["confidence"],
            processing_time_ms=processing_time,
        )
        db.add(query)
        await db.commit()
        
        logger.info(
            "multimodal_query_processed",
            user_id=current_user.id,
            files_count=len(processed_files),
            processing_time_ms=processing_time
        )
        
        return MultimodalResponse(
            answer=result["answer"],
            department=result["department"],
            mode=result["mode"],
            risk_level=result["risk"],
            confidence=result["confidence"],
            processing_time_ms=processing_time,
            files_processed=len(processed_files),
            rich_data=result.get("rich_data"),
            media_type=media_type,
        )
        
    except Exception as e:
        logger.error("multimodal_processing_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"AI işlem hatası: {str(e)}")


@router.post("/upload/image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Tek resim yükleme endpoint'i.
    Yüklenen resmi analiz eder ve açıklama döndürür.
    """
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Desteklenmeyen resim formatı: {file.content_type}"
        )
    
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Dosya çok büyük. Maksimum: {MAX_FILE_SIZE // (1024*1024)}MB"
        )
    
    base64_content = base64.b64encode(content).decode('utf-8')
    
    return {
        "success": True,
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(content),
        "message": "Resim başarıyla yüklendi",
    }


@router.post("/upload/document")
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Tek doküman yükleme endpoint'i.
    Yüklenen dokümanı işler ve metin içeriğini çıkarır.
    """
    if file.content_type not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Desteklenmeyen doküman formatı: {file.content_type}"
        )
    
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Dosya çok büyük. Maksimum: {MAX_FILE_SIZE // (1024*1024)}MB"
        )
    
    await file.seek(0)
    processed = await process_document_content(file)
    
    return {
        "success": True,
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(content),
        "text_extracted": len(processed.get("text", "")) > 0,
        "text_preview": processed.get("text", "")[:500] if processed.get("text") else None,
        "message": "Doküman başarıyla işlendi",
    }


# ── v4.5.0: Ses & Video Upload Endpoint'leri (MiniCPM-o 2.6) ──

@router.post("/upload/audio")
async def upload_audio(
    file: UploadFile = File(...),
    question: str = Form(default="Bu ses dosyasını analiz et ve içeriğini özetle."),
    current_user: User = Depends(get_current_user),
):
    """
    Tek ses dosyası yükleme ve analiz endpoint'i.
    MiniCPM-o 2.6 modeli ile ses analizi yapar.
    Desteklenen formatlar: mp3, wav, ogg, flac, webm, aac, m4a
    """
    if file.content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Desteklenmeyen ses formatı: {file.content_type}. "
                   f"Desteklenen: {', '.join(sorted(ALLOWED_AUDIO_TYPES))}"
        )
    
    content = await file.read()
    if len(content) > OMNI_MAX_AUDIO_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Ses dosyası çok büyük. Maksimum: {OMNI_MAX_AUDIO_SIZE // (1024*1024)}MB"
        )
    
    await file.seek(0)
    processed = await process_audio_content(file)
    
    if processed.get("error"):
        raise HTTPException(status_code=422, detail=processed["error"])
    
    # MiniCPM-o ile analiz et
    try:
        audio_b64 = processed["base64"]
        
        from app.llm.prompts import build_prompt
        from app.router.router import decide
        ctx = decide(question)
        
        system_prompt, user_prompt = build_prompt(
            f"Kullanıcı bir ses dosyası paylaştı ({file.filename}). {question}",
            ctx,
        )
        
        answer = await ollama_client.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            images=[audio_b64],
            use_omni=True,
        )
        
        return {
            "success": True,
            "filename": file.filename,
            "content_type": file.content_type,
            "size": len(content),
            "duration_seconds": processed.get("duration_seconds"),
            "analysis": answer,
            "model": "minicpm-o (omni)",
            "message": "Ses dosyası MiniCPM-o 2.6 ile analiz edildi",
        }
    except Exception as e:
        logger.error("audio_analysis_failed", error=str(e))
        return {
            "success": True,
            "filename": file.filename,
            "size": len(content),
            "analysis": None,
            "error": f"Ses analizi başarısız: {str(e)}",
            "message": "Ses yüklendi fakat analiz yapılamadı",
        }


@router.post("/upload/video")
async def upload_video(
    file: UploadFile = File(...),
    question: str = Form(default="Bu videoyu analiz et ve içeriğini özetle."),
    current_user: User = Depends(get_current_user),
):
    """
    Tek video dosyası yükleme ve analiz endpoint'i.
    MiniCPM-o 2.6 modeli ile video analizi yapar.
    Video'dan eşit aralıklı kareler çıkarılarak analiz edilir.
    Desteklenen formatlar: mp4, webm, avi, mov, mkv
    """
    if file.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Desteklenmeyen video formatı: {file.content_type}. "
                   f"Desteklenen: {', '.join(sorted(ALLOWED_VIDEO_TYPES))}"
        )
    
    content = await file.read()
    if len(content) > OMNI_MAX_VIDEO_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Video dosyası çok büyük. Maksimum: {OMNI_MAX_VIDEO_SIZE // (1024*1024)}MB"
        )
    
    await file.seek(0)
    processed = await process_video_content(file)
    
    if processed.get("error"):
        raise HTTPException(status_code=422, detail=processed["error"])
    
    # MiniCPM-o ile analiz et
    try:
        frames = processed.get("frames", [])
        if not frames:
            raise ValueError("Video'dan kare çıkarılamadı")
        
        from app.llm.prompts import build_prompt
        from app.router.router import decide
        ctx = decide(question)
        
        dur = processed.get("duration_seconds")
        dur_str = f", süre: {dur}s" if dur else ""
        
        system_prompt, user_prompt = build_prompt(
            f"Kullanıcı bir video paylaştı ({file.filename}{dur_str}, "
            f"{processed.get('sampled_frames', len(frames))} kare örneklendi). "
            f"Aşağıdaki kareler video'dan eşit aralıklarla alınmıştır.\n\n{question}",
            ctx,
        )
        
        answer = await ollama_client.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            images=frames,
            use_omni=True,
        )
        
        return {
            "success": True,
            "filename": file.filename,
            "content_type": file.content_type,
            "size": len(content),
            "duration_seconds": processed.get("duration_seconds"),
            "frame_count": processed.get("frame_count"),
            "sampled_frames": processed.get("sampled_frames"),
            "fps": processed.get("fps"),
            "analysis": answer,
            "model": "minicpm-o (omni)",
            "message": "Video MiniCPM-o 2.6 ile analiz edildi",
        }
    except Exception as e:
        logger.error("video_analysis_failed", error=str(e))
        return {
            "success": True,
            "filename": file.filename,
            "size": len(content),
            "duration_seconds": processed.get("duration_seconds"),
            "analysis": None,
            "error": f"Video analizi başarısız: {str(e)}",
            "message": "Video yüklendi fakat analiz yapılamadı",
        }


@router.get("/omni/capabilities")
async def get_omni_capabilities(
    current_user: User = Depends(get_current_user),
):
    """
    MiniCPM-o 2.6 omni-modal model yeteneklerini döndürür.
    Frontend için yetenek keşfi (feature discovery).
    """
    # Model kullanılabilirliğini kontrol et
    available_models = await ollama_client.get_models()
    omni_available = any("minicpm-o" in m for m in available_models)
    vision_available = any("minicpm-v" in m for m in available_models)
    
    return {
        "omni_model": settings.OMNI_MODEL,
        "omni_available": omni_available,
        "vision_model": settings.VISION_MODEL,
        "vision_available": vision_available,
        "supported_media": {
            "image": {
                "types": sorted(ALLOWED_IMAGE_TYPES),
                "max_size_mb": MAX_FILE_SIZE // (1024 * 1024),
                "model": "minicpm-v" if not omni_available else "minicpm-o",
            },
            "audio": {
                "types": sorted(ALLOWED_AUDIO_TYPES),
                "max_size_mb": OMNI_MAX_AUDIO_SIZE // (1024 * 1024),
                "model": "minicpm-o",
                "available": omni_available,
            },
            "video": {
                "types": sorted(ALLOWED_VIDEO_TYPES),
                "max_size_mb": OMNI_MAX_VIDEO_SIZE // (1024 * 1024),
                "sample_frames": OMNI_VIDEO_SAMPLE_FRAMES,
                "model": "minicpm-o",
                "available": omni_available,
            },
        },
        "capabilities": [
            "Görüntü analizi ve OCR",
            "Video sahne analizi",
            "Ses tanıma ve analiz",
            "Çoklu medya birleşik analiz",
            "Türkçe doğal dil desteği",
        ],
    }
