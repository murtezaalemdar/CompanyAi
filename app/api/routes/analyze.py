"""
Gelişmiş Doküman Analiz API Routes

Yüklenen dosyalarda:
- Pivot tablo
- İstatistiksel analiz
- Trend analizi
- Karşılaştırma
- Rapor oluşturma
- Yorum ve tavsiye
- Doğal dil ile veri sorgulama
"""

import io
import time
import json as _json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional, List

from app.db.database import get_db
from app.db.models import User, Query
from app.api.routes.auth import get_current_user
from app.core.audit import log_action
from app.llm.client import ollama_client

import structlog

logger = structlog.get_logger()

# Analiz motoru
try:
    from app.core.document_analyzer import (
        parse_file_to_dataframe,
        discover_data,
        create_pivot,
        smart_pivot,
        statistical_analysis,
        trend_analysis,
        top_n_analysis,
        comparison_analysis,
        natural_language_query,
        format_analysis_for_llm,
        anomaly_detection,
        correlation_analysis,
        distribution_analysis,
        forecast_analysis,
        pareto_analysis,
        data_quality_analysis,
    )
    ANALYZER_AVAILABLE = True
except ImportError as e:
    ANALYZER_AVAILABLE = False
    logger.warning("document_analyzer_not_available", error=str(e))

# Insight Engine (v3.9.0)
try:
    from app.core.insight_engine import extract_insights, insights_to_dict
    INSIGHT_AVAILABLE = True
except ImportError:
    INSIGHT_AVAILABLE = False

# Dosya çıkarıcı (documents.py'den)
try:
    from app.api.routes.documents import extract_text_from_file
    EXTRACTOR_AVAILABLE = True
except ImportError:
    EXTRACTOR_AVAILABLE = False

router = APIRouter()

# ── Tip-spesifik sistem prompt'ları ──
def _get_analysis_system_prompt(analysis_type: str) -> str:
    """Analiz tipine göre optimize edilmiş sistem prompt'u döndür"""
    base = "Sen deneyimli bir veri analisti ve iş zekası uzmanısın. Türkçe yanıt ver. Sayısal değerleri daima belirt."
    
    type_prompts = {
        "full": f"{base} Kapsamlı analiz yap. Tablolar, karşılaştırmalar, trendler ve somut tavsiyeler sun. Her bölümü detaylı ele al.",
        "pivot": f"{base} Pivot tablo uzmanısın. Çapraz tabloları, kategori kıyaslamalarını ve yüzdeleri detaylı analiz et.",
        "trend": f"{base} Zaman serisi ve trend analizi uzmanısın. Hareketli ortalamaları, momentum sinyallerini ve döngüsel paternleri yorumla. Gelecek öngörülerini sun.",
        "compare": f"{base} Karşılaştırmalı analiz uzmanısın. Gruplar arası performans farklarını, medyan/ortalama ayrışmasını ve tutarlılığı değerlendir.",
        "summary": f"{base} Veriden çarpıcı bir yönetici özeti çıkar. Kısa, yoğun ve bilgi dolu yaz. En önemli 3-4 bulguya odaklan.",
        "recommend": f"{base} Stratejik danışman gibi düşün. Her tavsiyeyi verilerle destekle, önceliklendirr ve risk-fayda analizi yap.",
        "report": f"{base} Profesyonel rapor yaz. Yönetici özeti, KPI tablosu, detaylı bulgular ve aksiyon planı içersin. Resmi ve yapılandırılmış format kullan.",
        "anomaly": f"{base} Anomali tespiti uzmanısın. IQR ve Z-Score bulgularını iş süreçleri perspektifinden yorumla. Kök neden analizi yap.",
        "correlation": f"{base} İstatistiksel ilişki analizi uzmanısın. Korelasyonları neden-sonuç bağlamında yorumla. Çoklu bağımlılık paternlerini bul.",
        "distribution": f"{base} İstatistiksel dağılım uzmanısın. Çarpıklık, basıklık, yüzdelik dilimleri anlaşılır iş diline çevir.",
        "forecast": f"{base} Tahminleme uzmanısın. Modellerin güven aralığını, varsayımlarını belirt. İyimser/kötümser senaryoları sun.",
        "pareto": f"{base} Pareto ve ABC analizi uzmanısın. 80/20 kuralını iş stratejisiyle birleştir. Kaynak optimizasyonu öner.",
        "quality": f"{base} Veri kalitesi denetçisisin. Eksiklik, tutarsızlık, tekrar sorunlarını tespit et. Veri mühendisliği ekibine teslim edilecek bir temizlik planı sun.",
        # ── CEO-TIER ANALİZ TİPLERİ (v3.8.0) ──
        "profitability": f"{base} Karlılık analizi uzmanısın. CEO'ya hitap ediyorsun. Ürün bazlı, müşteri bazlı ve kanal bazlı NET KÂRLILIĞI analiz et. Contribution margin, gizli zarar eden segmentler, çapraz sübvansiyon ve fiyatlama fırsatlarını ortaya çıkar. Patron '​para nerede kayboluyor?' sorusuna net cevap ver. Her bulguyu TL/₺ etkisiyle ifade et.",
        "bottleneck": f"{base} Operasyonel darboğaz analisti ve endüstri mühendisisin. CEO'ya hitap ediyorsun. Verideki en yavaş süreç, en pahalı adım, en düşük verimlilik noktasını tespit et. Kuyruk analizi, kaynak kullanım haritası ve kapasite darboğazlarını belirle. Patron '​operasyon nerede tıkanıyor?' sorusuna net cevap ver. Her darboğazın maliyet etkisini ve çözüm önerisini ROI ile sun.",
        "executive": f"{base} Üst düzey yönetim danışmanısın. CEO/CFO'ya hitap ediyorsun. Veriden Şirket Sağlık Skoru (0-100) türet. 4 boyutta değerlendir: Finansal Sağlamlık, Operasyonel Verimlilik, Büyüme İvmesi, Risk Maruziyet. Her boyuta harf notu (A-F) ve renk kodu ver. Patron 'şirketin durumu nasıl?' sorusuna tek bakışta cevap verecek bir dashboard üret. Aksiyon önceliklerini stratejik önemle sırala.",
        "benchmark": f"{base} Sektörel kıyaslama ve rekabet analizi uzmanısın. CEO'ya hitap ediyorsun. Verideki metrikleri tekstil sektörü ortalamalarıyla kıyasla. Her KPI'da şirketin sektöre göre konumunu belirle (üstün/ortalama/altında). Rakiplere göre güçlü/zayıf yönleri tespit et. Patron 'rakiplere göre neredeyiz?' sorusuna net cevap ver. Benchmark gaplerini kapatmak için somut hedefler belirle.",
    }
    
    return type_prompts.get(analysis_type, type_prompts["full"])

# ── Aktif analiz dosyaları cache (kullanıcı bazlı) ──
_analysis_cache: dict[int, dict] = {}
MAX_CACHE_PER_USER = 3


def _cache_analysis(user_id: int, filename: str, data: dict):
    """Analiz verisini cache'e al"""
    if user_id not in _analysis_cache:
        _analysis_cache[user_id] = {}
    
    # Eski verileri temizle
    if len(_analysis_cache[user_id]) >= MAX_CACHE_PER_USER:
        oldest = next(iter(_analysis_cache[user_id]))
        del _analysis_cache[user_id][oldest]
    
    _analysis_cache[user_id][filename] = data


def _get_cached(user_id: int, filename: str = None) -> Optional[dict]:
    """Cache'ten analiz verisini al"""
    if user_id not in _analysis_cache:
        return None
    if filename:
        return _analysis_cache[user_id].get(filename)
    # Son yüklenen dosyayı döndür
    if _analysis_cache[user_id]:
        last_key = list(_analysis_cache[user_id].keys())[-1]
        return _analysis_cache[user_id][last_key]
    return None


# ══════════════════════════════════════════════════════════════
# REQUEST / RESPONSE MODELLERİ
# ══════════════════════════════════════════════════════════════

class AnalyzeRequest(BaseModel):
    """Analiz talebi (dosya zaten yüklenmişse)"""
    analysis_type: str = Field("full", description="full, pivot, trend, compare, summary, recommend, report")
    question: Optional[str] = Field(None, description="Ek soru veya talep")
    filename: Optional[str] = Field(None, description="Cache'teki dosya adı (None=son yüklenen)")

class PivotRequest(BaseModel):
    """Pivot tablo talebi"""
    rows: Optional[List[str]] = None
    columns: Optional[List[str]] = None
    values: Optional[List[str]] = None
    aggfunc: str = "sum"
    filename: Optional[str] = None

class QueryRequest(BaseModel):
    """Doğal dil sorgusu"""
    question: str
    filename: Optional[str] = None


# ══════════════════════════════════════════════════════════════
# ENDPOINT'LER
# ══════════════════════════════════════════════════════════════

@router.post("/upload-analyze")
async def upload_and_analyze(
    file: UploadFile = File(...),
    analysis_type: str = Form("full"),
    question: Optional[str] = Form(None),
    department: str = Form("Genel"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Dosya yükle + otomatik kapsamlı analiz.
    
    Desteklenen analiz tipleri:
    - **full**: Tam analiz (pivot + trend + istatistik + tavsiye)
    - **pivot**: Pivot tablo odaklı
    - **trend**: Zaman bazlı trend analizi
    - **compare**: Kategori karşılaştırması
    - **summary**: Hızlı özet
    - **recommend**: Tavsiye odaklı
    - **report**: Profesyonel rapor formatı
    """
    if not ANALYZER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Analiz modülü kullanılamıyor")
    
    start_time = time.time()
    
    try:
        file_content = await file.read()
        if not file_content:
            raise HTTPException(status_code=400, detail="Dosya boş")
        
        filename = file.filename or "unknown"
        logger.info("analyze_upload", file=filename, type=analysis_type, user=current_user.email)
        
        # 1. DataFrame'e çevirmeyi dene
        df = parse_file_to_dataframe(filename, file_content)
        
        # 2. DataFrame başarılıysa tablolu analiz
        if df is not None and not df.empty:
            # Cache'e al
            discovery = discover_data(df)
            _cache_analysis(current_user.id, filename, {
                "df": df,
                "discovery": discovery,
                "filename": filename,
                "uploaded_at": time.time(),
            })
            
            # LLM için analiz prompt'u oluştur
            analysis_prompt = format_analysis_for_llm(
                df=df,
                analysis_type=analysis_type,
                question=question,
                filename=filename,
            )
            
            # LLM'den analiz al
            system_prompt = _get_analysis_system_prompt(analysis_type)

            llm_answer = ""
            if await ollama_client.is_available():
                llm_answer = await ollama_client.generate(
                    prompt=analysis_prompt,
                    system_prompt=system_prompt,
                    temperature=0.3,
                )
            else:
                llm_answer = f"[LLM erişilemez - Ham analiz verisi]\n\n{analysis_prompt}"
            
            processing_ms = int((time.time() - start_time) * 1000)
            
            # DB kaydet
            try:
                query = Query(
                    user_id=current_user.id,
                    question=f"[Dosya Analizi: {filename}] {question or analysis_type}",
                    answer=llm_answer[:5000],
                    department=department,
                    mode="Analiz",
                    risk_level="Düşük",
                    confidence=0.9,
                    processing_time_ms=processing_ms,
                )
                db.add(query)
                await db.commit()
            except Exception:
                pass
            
            return {
                "success": True,
                "answer": llm_answer,
                "analysis_type": analysis_type,
                "filename": filename,
                "data_info": {
                    "rows": discovery["row_count"],
                    "cols": discovery["col_count"],
                    "numeric_columns": discovery["numeric_columns"],
                    "categorical_columns": discovery["categorical_columns"],
                    "date_columns": discovery["date_columns"],
                    "has_missing": discovery["has_missing"],
                },
                "processing_time_ms": processing_ms,
                "cached": True,
            }
        
        # 3. DataFrame değilse, metin olarak analiz et
        if EXTRACTOR_AVAILABLE:
            text_content, doc_type = extract_text_from_file(filename, file_content)
        else:
            try:
                text_content = file_content.decode('utf-8')
                doc_type = "text"
            except Exception:
                raise HTTPException(status_code=400, detail="Dosya okunamadı")
        
        if not text_content or not text_content.strip():
            raise HTTPException(status_code=400, detail="Dosyadan içerik çıkarılamadı")
        
        # Metin analiz prompt'u
        analysis_prompt = format_analysis_for_llm(
            text=text_content,
            analysis_type=analysis_type,
            question=question,
            filename=filename,
        )
        
        system_prompt = """Sen bir doküman analisti ve iş zekası uzmanısın. Türkçe yanıt ver.
Verilen dokümanı detaylı analiz et. Net bulgular, yorumlar ve öneriler sun.
Profesyonel ama anlaşılır bir dil kullan. Tavsiyelerini somut yap."""
        
        llm_answer = ""
        if await ollama_client.is_available():
            llm_answer = await ollama_client.generate(
                prompt=analysis_prompt,
                system_prompt=system_prompt,
                temperature=0.3,
            )
        else:
            llm_answer = f"[LLM erişilemez]\n\n{analysis_prompt}"
        
        processing_ms = int((time.time() - start_time) * 1000)
        
        return {
            "success": True,
            "answer": llm_answer,
            "analysis_type": analysis_type,
            "filename": filename,
            "data_info": {
                "type": doc_type,
                "chars": len(text_content),
                "words": len(text_content.split()),
            },
            "processing_time_ms": processing_ms,
            "cached": False,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("analyze_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Analiz hatası: {str(e)}")


@router.post("/upload-analyze/stream")
async def upload_and_analyze_stream(
    file: UploadFile = File(...),
    analysis_type: str = Form("full"),
    question: Optional[str] = Form(None),
    department: str = Form("Genel"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dosya yükle + streaming analiz (SSE)"""
    if not ANALYZER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Analiz modülü kullanılamıyor")
    
    start_time = time.time()
    
    file_content = await file.read()
    if not file_content:
        raise HTTPException(status_code=400, detail="Dosya boş")
    
    filename = file.filename or "unknown"
    
    # 1. DataFrame dene
    df = parse_file_to_dataframe(filename, file_content)
    
    if df is not None and not df.empty:
        discovery = discover_data(df)
        _cache_analysis(current_user.id, filename, {
            "df": df, "discovery": discovery, "filename": filename, "uploaded_at": time.time(),
        })
        
        analysis_prompt = format_analysis_for_llm(
            df=df, analysis_type=analysis_type, question=question, filename=filename,
        )
        data_info = {
            "rows": discovery["row_count"],
            "cols": discovery["col_count"],
            "numeric_columns": discovery["numeric_columns"],
        }
    else:
        # Metin analizi
        if EXTRACTOR_AVAILABLE:
            text_content, doc_type = extract_text_from_file(filename, file_content)
        else:
            text_content = file_content.decode('utf-8', errors='ignore')
            doc_type = "text"
        
        analysis_prompt = format_analysis_for_llm(
            text=text_content, analysis_type=analysis_type, question=question, filename=filename,
        )
        data_info = {"type": doc_type, "chars": len(text_content)}
    
    system_prompt = _get_analysis_system_prompt(analysis_type)

    async def _event_generator():
        collected = []
        try:
            # Önce data_info gönder
            yield f"data: {_json.dumps({'data_info': data_info, 'filename': filename})}\n\n"
            
            async for token in ollama_client.stream(analysis_prompt, system_prompt=system_prompt):
                collected.append(token)
                yield f"data: {_json.dumps({'token': token})}\n\n"
        except Exception as exc:
            yield f"data: {_json.dumps({'error': str(exc)})}\n\n"
            return
        
        processing_ms = int((time.time() - start_time) * 1000)
        full_answer = "".join(collected)
        
        try:
            query = Query(
                user_id=current_user.id,
                question=f"[Dosya Analizi: {filename}] {question or analysis_type}",
                answer=full_answer[:5000],
                department=department,
                mode="Analiz",
                risk_level="Düşük",
                confidence=0.9,
                processing_time_ms=processing_ms,
            )
            db.add(query)
            await db.commit()
        except Exception:
            pass
        
        yield f"data: {_json.dumps({'done': True, 'processing_time_ms': processing_ms, 'analysis_type': analysis_type})}\n\n"
    
    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/discover")
async def discover_uploaded_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Dosyayı yükle, yapısını keşfet ve sütun bilgilerini döndür.
    Kullanıcı bu bilgiyle hangi analizleri yapacağını seçer.
    """
    if not ANALYZER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Analiz modülü kullanılamıyor")
    
    file_content = await file.read()
    df = parse_file_to_dataframe(file.filename, file_content)
    
    if df is None or df.empty:
        # Metin bazlı — basit bilgi döndür
        try:
            text = file_content.decode('utf-8', errors='ignore')
        except Exception:
            text = ""
        
        return {
            "type": "text",
            "filename": file.filename,
            "chars": len(text),
            "words": len(text.split()),
            "lines": len(text.split('\n')),
            "is_tabular": False,
            "available_analyses": ["full", "summary", "recommend", "report"],
        }
    
    discovery = discover_data(df)
    _cache_analysis(current_user.id, file.filename, {
        "df": df, "discovery": discovery, "filename": file.filename, "uploaded_at": time.time(),
    })
    
    # Hangi analizler yapılabilir?
    available = ["full", "summary", "recommend", "report", "quality"]
    if discovery["categorical_columns"] and discovery["numeric_columns"]:
        available.append("pivot")
        available.append("compare")
        available.append("pareto")
    if discovery["date_columns"]:
        available.append("trend")
        available.append("forecast")
    if len(discovery["numeric_columns"]) >= 2:
        available.append("correlation")
        available.append("distribution")
        available.append("anomaly")
    
    # Sayfalar (Excel)
    sheets = None
    if hasattr(df, 'attrs') and '_all_sheets' in df.attrs:
        sheets = df.attrs['_all_sheets']
    
    return {
        "type": "tabular",
        "filename": file.filename,
        "is_tabular": True,
        "rows": discovery["row_count"],
        "cols": discovery["col_count"],
        "columns": discovery["columns"],
        "numeric_columns": discovery["numeric_columns"],
        "categorical_columns": discovery["categorical_columns"],
        "date_columns": discovery["date_columns"],
        "has_missing": discovery["has_missing"],
        "missing_summary": discovery["missing_summary"],
        "sheets": sheets,
        "available_analyses": available,
        "sample_data": df.head(5).to_dict('records'),
    }


@router.post("/pivot")
async def create_pivot_table(
    request: PivotRequest,
    current_user: User = Depends(get_current_user),
):
    """Cache'teki veriden pivot tablo oluştur"""
    if not ANALYZER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Analiz modülü kullanılamıyor")
    
    cached = _get_cached(current_user.id, request.filename)
    if not cached or "df" not in cached:
        raise HTTPException(status_code=404, detail="Önce bir dosya yükleyin (/analyze/upload-analyze veya /analyze/discover)")
    
    df = cached["df"]
    
    if request.rows or request.values:
        result = create_pivot(
            df,
            rows=request.rows,
            columns=request.columns,
            values=request.values,
            aggfunc=request.aggfunc,
        )
    else:
        result = smart_pivot(df)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Pivot oluşturulamadı"))
    
    return {
        "success": True,
        "pivot_table": result["table_str"],
        "pivot_markdown": result.get("table_markdown"),
        "shape": result["shape"],
        "filename": cached["filename"],
    }


@router.post("/query")
async def query_data(
    request: QueryRequest,
    current_user: User = Depends(get_current_user),
):
    """Doğal dil ile veri sorgula"""
    if not ANALYZER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Analiz modülü kullanılamıyor")
    
    cached = _get_cached(current_user.id, request.filename)
    if not cached or "df" not in cached:
        raise HTTPException(status_code=404, detail="Önce bir dosya yükleyin")
    
    df = cached["df"]
    result = natural_language_query(df, request.question)
    
    if result.get("success"):
        return {
            "success": True,
            "answer": result["answer"],
            "value": result.get("value"),
            "query_type": result["query_type"],
            "filename": cached["filename"],
        }
    
    # Doğal dil sorgusu bulunamadıysa, LLM'e sor
    analysis_prompt = format_analysis_for_llm(
        df=df,
        analysis_type="full",
        question=request.question,
        filename=cached["filename"],
    )
    
    system_prompt = """Sen bir veri analistisin. Verilen soruyu verilere dayanarak yanıtla. 
Kısa ve net cevap ver. Sayısal değerleri mutlaka belirt. Türkçe yanıt ver."""
    
    if await ollama_client.is_available():
        answer = await ollama_client.generate(
            prompt=analysis_prompt,
            system_prompt=system_prompt,
            temperature=0.2,
        )
    else:
        answer = "LLM erişilemez, doğrudan veri sorgusu denendi ama eşleşme bulunamadı."
    
    return {
        "success": True,
        "answer": answer,
        "query_type": "llm_analysis",
        "filename": cached["filename"],
    }


@router.post("/statistics")
async def get_statistics(
    current_user: User = Depends(get_current_user),
    filename: Optional[str] = None,
):
    """Cache'teki verinin detaylı istatistikleri"""
    if not ANALYZER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Analiz modülü kullanılamıyor")
    
    cached = _get_cached(current_user.id, filename)
    if not cached or "df" not in cached:
        raise HTTPException(status_code=404, detail="Önce bir dosya yükleyin")
    
    df = cached["df"]
    stats = statistical_analysis(df)
    
    # v3.9.0 — Otomatik insight ekleme
    auto_insights = None
    if INSIGHT_AVAILABLE:
        try:
            report = extract_insights(df, max_insights=10)
            auto_insights = insights_to_dict(report)
        except Exception as ie:
            logger.warning("insight_extraction_failed", error=str(ie))
    
    return {
        "success": True,
        "filename": cached["filename"],
        "basic_stats": stats["basic_stats"],
        "correlations": stats.get("correlations"),
        "strong_correlations": stats.get("strong_correlations", []),
        "outliers": stats.get("outliers", {}),
        "distributions": stats.get("distributions", {}),
        "auto_insights": auto_insights,
    }


@router.post("/trend")
async def get_trend(
    current_user: User = Depends(get_current_user),
    filename: Optional[str] = None,
    date_col: Optional[str] = None,
    value_col: Optional[str] = None,
):
    """Cache'teki verinin trend analizi"""
    if not ANALYZER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Analiz modülü kullanılamıyor")
    
    cached = _get_cached(current_user.id, filename)
    if not cached or "df" not in cached:
        raise HTTPException(status_code=404, detail="Önce bir dosya yükleyin")
    
    df = cached["df"]
    result = trend_analysis(df, date_col=date_col, value_col=value_col)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return {"success": True, "filename": cached["filename"], **result}


@router.post("/compare")
async def compare_groups(
    current_user: User = Depends(get_current_user),
    filename: Optional[str] = None,
    group_col: Optional[str] = None,
):
    """Cache'teki veride grup karşılaştırması"""
    if not ANALYZER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Analiz modülü kullanılamıyor")
    
    cached = _get_cached(current_user.id, filename)
    if not cached or "df" not in cached:
        raise HTTPException(status_code=404, detail="Önce bir dosya yükleyin")
    
    df = cached["df"]
    result = comparison_analysis(df, group_col=group_col)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return {"success": True, "filename": cached["filename"], **result}


@router.get("/cached")
async def list_cached_files(
    current_user: User = Depends(get_current_user),
):
    """Kullanıcının cache'teki dosyalarını listele"""
    if current_user.id not in _analysis_cache:
        return {"files": [], "count": 0}
    
    files = []
    for fname, data in _analysis_cache[current_user.id].items():
        info = {
            "filename": fname,
            "uploaded_at": data.get("uploaded_at"),
        }
        if "discovery" in data:
            d = data["discovery"]
            info["rows"] = d["row_count"]
            info["cols"] = d["col_count"]
            info["type"] = "tabular"
        else:
            info["type"] = "text"
        files.append(info)
    
    return {"files": files, "count": len(files)}
