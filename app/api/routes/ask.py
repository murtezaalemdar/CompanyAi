"""AI Soru-Cevap API Routes"""

import time
import json as _json
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.db.database import get_db
from app.db.models import User, Query
from app.api.routes.auth import get_current_user
from app.core.engine import process_question
from app.core.audit import log_action
from app.router.router import decide
from app.llm.client import ollama_client
from app.llm.prompts import build_prompt

router = APIRouter()


class AskRequest(BaseModel):
    question: str
    department: Optional[str] = None  # Opsiyonel departman override


class AskResponse(BaseModel):
    answer: str
    department: str
    mode: str
    risk_level: str
    confidence: float
    processing_time_ms: int


@router.post("/ask", response_model=AskResponse)
async def ask_ai(
    request: AskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    http_request: Request = None,
):
    """
    AI asistana soru sor.
    
    - JWT authentication gerektirir
    - Sorguları veritabanına kaydeder
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
        if request.department and request.department not in user_departments:
            # Yetkisiz departman seçilmiş, ilk yetkili departmanı kullan
            request.department = user_departments[0] if user_departments else None
        elif not request.department:
            # Departman belirtilmemişse ilk yetkili departmanı kullan
            request.department = user_departments[0] if user_departments else None
    
    try:
        # Soruyu işle
        result = await process_question(request.question, request.department)
        
        processing_time = int((time.time() - start_time) * 1000)
        
        # Sorguyu kaydet
        query = Query(
            user_id=current_user.id,
            question=request.question,
            answer=result["answer"],
            department=result["department"],
            mode=result["mode"],
            risk_level=result["risk"],
            confidence=result["confidence"],
            processing_time_ms=processing_time,
        )
        db.add(query)

        # Audit log
        import json as _json
        await log_action(
            db, user=current_user, action="query",
            resource="ask",
            details=_json.dumps({
                "department": result["department"],
                "risk": result["risk"],
                "processing_ms": processing_time,
            }),
            ip_address=(http_request.client.host if http_request and http_request.client else None),
        )
        await db.commit()
        
        return AskResponse(
            answer=result["answer"],
            department=result["department"],
            mode=result["mode"],
            risk_level=result["risk"],
            confidence=result["confidence"],
            processing_time_ms=processing_time,
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI işlem hatası: {str(e)}")


@router.get("/health")
async def health_check():
    """Servis sağlık kontrolü"""
    return {"status": "healthy", "service": "Kurumsal AI Asistanı"}


@router.get("/llm/status")
async def llm_status():
    """LLM servis durumu"""
    is_available = await ollama_client.is_available()
    models = await ollama_client.get_models() if is_available else []
    
    return {
        "available": is_available,
        "models": models,
        "current_model": ollama_client.model,
    }


# ── Streaming SSE Endpoint ─────────────────────────────────────

@router.post("/ask/stream")
async def ask_ai_stream(
    request: AskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    http_request: Request = None,
):
    """
    AI asistana soru sor — Server-Sent Events (SSE) streaming yanıt.

    Frontend'de EventSource veya fetch + ReadableStream ile tüketilebilir.
    Her SSE mesajı: data: {"token": "..."}\n\n
    Son mesaj:       data: {"done": true, "department": ..., "processing_time_ms": ...}\n\n
    """
    start_time = time.time()

    # Departman yetki kontrolü (ask ile aynı mantık)
    user_departments = []
    if current_user.department:
        try:
            parsed = _json.loads(current_user.department)
            user_departments = parsed if isinstance(parsed, list) else [current_user.department]
        except _json.JSONDecodeError:
            user_departments = [current_user.department]

    department = request.department
    if current_user.role == "user":
        if department and department not in user_departments:
            department = user_departments[0] if user_departments else None
        elif not department:
            department = user_departments[0] if user_departments else None

    # Router kararı
    routing = await decide(request.question, department)
    dept = routing.get("department", department or "genel")
    mode = routing.get("mode", "genel")
    risk = routing.get("risk", "low")
    confidence = routing.get("confidence", 0.8)

    # Prompt oluştur
    system_prompt, user_prompt = build_prompt(
        question=request.question,
        context={"dept": dept, "mode": mode, "risk": risk},
    )

    async def _event_generator():
        collected = []
        try:
            async for token in ollama_client.stream(user_prompt, system_prompt=system_prompt):
                collected.append(token)
                yield f"data: {_json.dumps({'token': token})}\n\n"
        except Exception as exc:
            yield f"data: {_json.dumps({'error': str(exc)})}\n\n"
            return

        processing_ms = int((time.time() - start_time) * 1000)
        full_answer = "".join(collected)

        # DB kaydet (fire & forget değil, await ediyoruz)
        try:
            query = Query(
                user_id=current_user.id,
                question=request.question,
                answer=full_answer,
                department=dept,
                mode=mode,
                risk_level=risk,
                confidence=confidence,
                processing_time_ms=processing_ms,
            )
            db.add(query)
            await log_action(
                db, user=current_user, action="query_stream",
                resource="ask/stream",
                details=_json.dumps({"department": dept, "risk": risk, "processing_ms": processing_ms}),
                ip_address=(http_request.client.host if http_request and http_request.client else None),
            )
            await db.commit()
        except Exception:
            pass  # Kayıt hatası streaming'i kırmamalı

        yield f"data: {_json.dumps({'done': True, 'department': dept, 'mode': mode, 'risk_level': risk, 'confidence': confidence, 'processing_time_ms': processing_ms})}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # nginx proxy buffering'i kapat
        },
    )
