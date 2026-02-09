"""Legacy LLM Wrapper — Geriye dönük uyumluluk için korunuyor.

Gerçek LLM işlemleri artık app.llm.client.OllamaClient tarafından yürütülmektedir.
Bu modül, eski import'ları kırmamak için client.py'a yönlendirme yapar.
"""

import asyncio
from app.llm.client import ollama_client


async def ask_local_llm(question: str, context: dict) -> dict:
    """
    Eski API ile uyumlu LLM çağrısı — OllamaClient.generate() wrapper'ı.

    Args:
        question: Kullanıcı sorusu
        context: Router'dan gelen bağlam {dept, mode, risk}

    Returns:
        Yapılandırılmış yanıt dict
    """
    from app.llm.prompts import build_prompt

    system_prompt, user_prompt = build_prompt(question, context)

    try:
        if await ollama_client.is_available():
            answer = await ollama_client.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
            )
        else:
            answer = f"[LLM Erişilemez] Soru alındı: {question}"
    except Exception as e:
        answer = f"[Hata] LLM yanıt üretemedi: {e}"

    return {
        "department": context.get("dept", "Genel"),
        "mode": context.get("mode", "Analiz"),
        "answer": answer,
        "risk": context.get("risk", "Düşük"),
        "confidence": 0.85,
    }