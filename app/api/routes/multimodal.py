"""Multimodal AI API Routes - Dosya ve Resim Destekli Soru-Cevap"""

import time
import os
import base64
import tempfile
import io
from PIL import Image
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.database import get_db
from app.db.models import User, Query
from app.api.routes.auth import get_current_user
from app.core.engine import process_question
from app.llm.client import ollama_client
from app.config import settings

import structlog

logger = structlog.get_logger()

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


def get_file_type(content_type: str) -> str:
    """Dosya türünü belirle"""
    if content_type in ALLOWED_IMAGE_TYPES:
        return "image"
    elif content_type in ALLOWED_DOCUMENT_TYPES:
        return "document"
    else:
        return "unknown"


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
    
    # Excel dosyaları için
    elif file.content_type in {
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    }:
        try:
            import pandas as pd
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            df = pd.read_excel(tmp_path)
            text_content = df.to_string()
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
    
    - Resim dosyaları: JPEG, PNG, GIF, WEBP, BMP
    - Doküman dosyaları: PDF, DOCX, XLSX, TXT, CSV, JSON
    - Maksimum 10 dosya, her biri maksimum 50MB
    """
    start_time = time.time()
    
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
            
        elif file_type == "document":
            processed = await process_document_content(file)
            processed_files.append(processed)
            if processed.get("text"):
                context_parts.append(f"--- İçerik: {file.filename} ---\n{processed['text']}\n---")
            else:
                context_parts.append(f"[Doküman eklendi: {file.filename}]")
        else:
            logger.warning("unsupported_file_type", filename=file.filename, content_type=file.content_type)
    
    # Soru ile bağlamı birleştir
    enhanced_question = question
    if context_parts:
        file_context = "\n\n".join(context_parts)
        enhanced_question = f"""Kullanıcı aşağıdaki dosyaları paylaştı:

{file_context}

Kullanıcının sorusu: {question}

Lütfen paylaşılan dosya içeriklerini dikkate alarak soruyu cevapla."""
    
    try:
        # Eğer resim varsa ve vision model kullanılabilirse, doğrudan vision LLM'e gönder
        if image_base64_list:
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
                    images=image_base64_list,
                )
                
                processing_time = int((time.time() - start_time) * 1000)
                
                result = {
                    "answer": vision_answer,
                    "department": context["dept"],
                    "mode": context["mode"],
                    "risk": context["risk"],
                    "confidence": 0.88,
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
                await db.commit()
                
                return MultimodalResponse(
                    answer=result["answer"],
                    department=result["department"],
                    mode=result["mode"],
                    risk_level=result["risk"],
                    confidence=result["confidence"],
                    processing_time_ms=processing_time,
                    files_processed=len(processed_files),
                )
            except Exception as vision_err:
                logger.warning("vision_llm_fallback", error=str(vision_err))
                # Vision model yoksa normal akışa devam et

        # Normal metin tabanlı akış (resim yoksa veya vision başarısızsa)
        result = await process_question(enhanced_question, department)
        
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
