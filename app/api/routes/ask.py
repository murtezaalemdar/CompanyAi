"""AI Soru-Cevap API Routes"""

import time
import json as _json
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List

from app.db.database import get_db
from app.db.models import User, Query
from app.api.routes.auth import get_current_user
from app.core.engine import process_question
from app.core.audit import log_action
from app.router.router import decide
from app.llm.client import ollama_client
from app.llm.prompts import build_prompt

# Few-shot sohbet örnekleri
try:
    from app.llm.chat_examples import get_pattern_response, get_few_shot_examples
    CHAT_EXAMPLES_AVAILABLE = True
except ImportError:
    CHAT_EXAMPLES_AVAILABLE = False
    get_pattern_response = lambda q: None
    get_few_shot_examples = lambda q, c=2: ""

router = APIRouter()

# ── Basit oturum hafızası (sunucu tarafı, kullanıcı bazlı) ────
# Her kullanıcının son N mesajını tutar
_user_sessions: dict[int, list] = {}
MAX_SESSION_MESSAGES = 10


def _get_session(user_id: int) -> list:
    """Kullanıcının oturum geçmişini getir"""
    return _user_sessions.get(user_id, [])


def _add_to_session(user_id: int, question: str, answer: str):
    """Konuşmayı oturuma ekle"""
    if user_id not in _user_sessions:
        _user_sessions[user_id] = []
    _user_sessions[user_id].append({"q": question, "a": answer})
    # Son N mesajı tut
    if len(_user_sessions[user_id]) > MAX_SESSION_MESSAGES:
        _user_sessions[user_id] = _user_sessions[user_id][-MAX_SESSION_MESSAGES:]


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
        # Oturum geçmişini al
        session_history = _get_session(current_user.id)
        
        # Soruyu işle — kullanıcı bilgisi + oturum geçmişi ile
        result = await process_question(
            question=request.question, 
            department_override=request.department,
            user_name=current_user.full_name or current_user.email.split("@")[0],
            user_department=request.department,
            session_history=session_history,
        )
        
        # Oturuma kaydet
        _add_to_session(current_user.id, request.question, result["answer"])
        
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

    # Router kararı (sync fonksiyon)
    routing = decide(request.question)
    dept = routing.get("dept", department or "Genel")
    mode = routing.get("mode", "Sohbet")
    risk = routing.get("risk", "Düşük")
    intent = routing.get("intent", "sohbet")
    confidence = 0.85

    if department:
        dept = department

    # ── HIZLI SOHBET YOLU ── Kalıp eşleşmesi varsa anında yanıt ver
    if intent == "sohbet" and CHAT_EXAMPLES_AVAILABLE:
        pattern_answer = get_pattern_response(request.question)
        if pattern_answer:
            user_name = current_user.full_name or current_user.email.split("@")[0]
            # Kişiselleştirme
            import random as _rnd
            if user_name and _rnd.random() < 0.4:
                first_name = user_name.split()[0]
                if first_name:
                    pattern_answer = f"{first_name}, {pattern_answer[0].lower()}{pattern_answer[1:]}"
            
            _add_to_session(current_user.id, request.question, pattern_answer)

            async def _fast_event():
                # Tüm cevabı tek token olarak gönder (anlık)
                yield f"data: {_json.dumps({'token': pattern_answer})}\n\n"
                processing_ms = int((time.time() - start_time) * 1000)
                try:
                    query = Query(
                        user_id=current_user.id, question=request.question,
                        answer=pattern_answer, department=dept, mode="Sohbet",
                        risk_level=risk, confidence=0.95, processing_time_ms=processing_ms,
                    )
                    db.add(query)
                    await db.commit()
                except Exception:
                    pass
                yield f"data: {_json.dumps({'done': True, 'department': dept, 'mode': 'Sohbet', 'risk_level': risk, 'confidence': 0.95, 'processing_time_ms': processing_ms})}\n\n"

            return StreamingResponse(
                _fast_event(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            )

    # Prompt oluştur
    system_prompt, user_prompt = build_prompt(
        question=request.question,
        context={"dept": dept, "mode": mode},
    )
    
    # Kişiselleştirme
    user_name = current_user.full_name or current_user.email.split("@")[0]
    if user_name:
        system_prompt += f"\nKullanıcının adı: {user_name}. Gerekirse adıyla hitap et.\n"
    
    # Few-shot sohbet örnekleri (sadece uzun sohbet mesajlarında)
    if CHAT_EXAMPLES_AVAILABLE and intent == "sohbet":
        word_count = len(request.question.strip().split())
        if word_count > 5:
            few_shot = get_few_shot_examples(request.question, count=1)
            if few_shot:
                system_prompt += few_shot

    # Chat history — stream de history desteklesin
    session_history = _get_session(current_user.id)
    chat_history = session_history[-5:] if session_history and intent != "sohbet" else None

    async def _event_generator():
        collected = []
        try:
            async for token in ollama_client.stream(user_prompt, system_prompt=system_prompt, history=chat_history):
                collected.append(token)
                yield f"data: {_json.dumps({'token': token})}\n\n"
        except Exception as exc:
            yield f"data: {_json.dumps({'error': str(exc)})}\n\n"
            return

        processing_ms = int((time.time() - start_time) * 1000)
        full_answer = "".join(collected)
        
        # Oturuma kaydet
        _add_to_session(current_user.id, request.question, full_answer)

        # DB kaydet
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
