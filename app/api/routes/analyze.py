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
from fastapi.responses import StreamingResponse, FileResponse
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

# ── Tip-spesifik sistem prompt'ları (v3.9.7 — enhanced) ──
def _get_analysis_system_prompt(analysis_type: str) -> str:
    """Analiz tipine göre optimize edilmiş sistem prompt'u döndür"""
    base = (
        "Sen deneyimli bir veri analisti ve iş zekası uzmanısın. Türkçe yanıt ver. "
        "Sayısal değerleri daima belirt. Markdown tabloları aktif kullan. "
        "Her analiz bölümünü başlıklarla (##, ###) yapılandır. "
        "Önemli sayıları **kalın** yaz. Bulgularını maddeler halinde sun. "
        "Veriye dayalı somut çıkarımlar yap, genel/belirsiz ifadelerden kaçın."
    )

    type_prompts = {
        "full": f"""{base}
Kapsamlı bir tam analiz raporu üret. Mutlaka şu bölümleri dahil et:
## 📋 Yönetici Özeti (en kritik 3-4 bulgu, tek paragraf)
## 📊 Temel Metrikler (markdown tablo: Metrik | Değer | Yorum)
## 📈 Detaylı Bulgular (her önemli sütun/metrik için derinlemesine)
## 🔍 Karşılaştırma ve Trendler
## ⚠️ Dikkat Edilmesi Gerekenler (anomali, risk, eksik)
## ✅ Aksiyon Önerileri (öncelik sırasıyla, somut adımlar)
Her bölümde markdown tabloları kullan. Hiçbir bölümü atlama.""",

        "pivot": f"""{base}
Pivot tablo ve çapraz analiz uzmanısın. Yanıtını şu yapıda sun:
## 📊 Pivot Tablo Özeti
- Hangi kategoriler hangi değerlere göre çaprazlanmış
## 📋 Detaylı Pivot Tablo (markdown tablo formatında)
## 🔍 Öne Çıkan Bulgular
- En yüksek/düşük hücreler, oranlar, paylar
## 💡 Stratejik Çıkarımlar
Tüm sayıları yüzde ve oran olarak da ifade et.""",

        "trend": f"""{base}
Zaman serisi ve trend analizi uzmanısın. Yanıtını şu yapıda sun:
## 📈 Trend Özeti (genel yön, büyüme hızı)
## 📊 Dönemsel Performans Tablosu (markdown tablo: Dönem | Değer | Değişim% | Yorum)
## 🔄 Hareketli Ortalamalar ve Momentum
## 📉 Volatilite ve Risk Profili
## 🔮 Gelecek Dönem Beklentileri
## ✅ Stratejik Öneriler
Tüm trendi sayılarla destekle, grafik verisi oluştur.""",

        "compare": f"""{base}
Karşılaştırmalı analiz uzmanısın. Yanıtını şu yapıda sun:
## 📊 Karşılaştırma Özet Tablosu (Grup | Metrik1 | Metrik2 | ... | Genel Sıralama)
## 🏆 En İyi Performans Gösterenler (neden iyi, hangi metriklerde)
## ⚠️ En Düşük Performans Gösterenler (neden kötü, nerede gerileme)
## 📈 İstatistiksel Anlamlılık (p-value, etki büyüklüğü yorumu)
## 🔍 Grup İçi Tutarlılık (std sapma, CV analizi)
## ✅ Grup Bazlı Aksiyon Önerileri
Her grubu ayrı değerlendir, sıralama tablosu oluştur.""",

        "summary": f"""{base}
Veriden etkili bir yönetici özeti çıkar:
## 📋 Veri Kapsamı (ne, ne zaman, ne kadar — tek paragraf)
## 🎯 Kritik Bulgular (en önemli 3-5 sayısal bulgu, madde halinde)
## ⚡ Dikkat Çekici Noktalar (anomali, trend kırılması, fırsat)
## 📌 Sonuç ve Öneri (tek paragraf, net ve aksiyona yönelik)
Kısa, öz ama bilgi dolu olsun. Maksimum 15 cümle.""",

        "recommend": f"""{base}
Stratejik danışman gibi düşün. Yapılandırılmış tavsiye raporu sun:
## 🚨 Acil Aksiyonlar (0-1 ay) — En az 2 madde
## 📋 Kısa Vadeli İyileştirmeler (1-3 ay) — En az 3 madde
## 🎯 Uzun Vadeli Stratejiler (3-12 ay) — En az 2 madde
## 📊 Öncelik Matrisi (markdown tablo: Aksiyon | Öncelik | Beklenen Etki | Maliyet/Zorluk)
Her tavsiyeyi verilerle destekle. ROI/etki tahmini yap.""",

        "report": f"""{base}
Profesyonel yönetici raporu yaz. Resmi ve yapılandırılmış format:
## 📋 Yönetici Özeti
## 📊 KPI Tablosu (markdown tablo: KPI | Mevcut Değer | Hedef | Durum)
## 📈 Detaylı Analiz Bulguları
### Bölüm 1: [Konuya göre]
### Bölüm 2: [Konuya göre]
## 🔍 Karşılaştırmalı Değerlendirme
## ⚠️ Risk ve Uyarılar
## ✅ Aksiyon Planı (markdown tablo: Adım | Sorumlu | Süre | Öncelik)
## 📌 Sonuç
Resmi dil kullan. Tüm bölümlerde sayısal veri olsun.""",

        "anomaly": f"""{base}
Anomali tespiti uzmanısın. Detaylı anomali raporu sun:
## 🔴 Anomali Özeti (toplam, ciddiyet dağılımı)
## 📊 Anomali Tablosu (Sütun | Anomali Sayısı | Ciddiyet | En Uç Değer | Normal Aralık)
## 🔍 Yöntem Bazlı Sonuçlar (IQR, Z-Score, Modified Z-Score karşılaştırması)
## ⚠️ Kritik Anomaliler (her biri ayrı açıklamayla)
## 🤔 Olası Nedenler (veri hatası mı, gerçek sapma mı?)
## ✅ Temizleme Stratejisi (sil/düzelt/araştır önerileri)
Her anomaliyi iş süreçleri perspektifinden yorumla.""",

        "correlation": f"""{base}
Korelasyon analizi uzmanısın. İlişkileri raporla:
## 📊 Korelasyon Matrisi (markdown tablo formatında)
## 🔴 Güçlü İlişkiler (|r| > 0.7, tablo: Değişken1 | Değişken2 | Pearson | Spearman | Yön)
## 🟡 Orta İlişkiler (0.4 < |r| < 0.7)
## 🔍 İstatistiksel Anlamlılık (p-value yorumu)
## 💡 Nedensellik Tartışması (korelasyon ≠ nedensellik uyarısı ile)
## ✅ Stratejik Çıkarımlar (hangi değişkeni değiştirirsek ne olur?)
Pearson ve Spearman farklarını yorumla.""",

        "distribution": f"""{base}
Dağılım analizi uzmanısın. İstatistiksel dağılımları raporla:
## 📊 Dağılım Özet Tablosu (Sütun | Ort | Medyan | Std | CV% | Dağılım Tipi)
## 📈 Normal Dağılım Testi Sonuçları (Sütun | Test | p-value | Normal mi?)
## 🔍 Çarpıklık ve Basıklık Yorumu (her sütun için)
## 📊 Yüzdelik Dilimler (P25, P50, P75, P95, P99 tablosu)
## ⚠️ Dikkat Çekici Dağılımlar (çarpık, bimodal, uç değerli)
## ✅ Analiz Stratejisi Önerileri (parametrik mi non-parametrik test mi?)
İstatistiksel terimleri iş diline çevir.""",

        "forecast": f"""{base}
Tahminleme uzmanısın. Çok modelli projeksiyon raporu sun:
## 📈 Tahmin Özeti (en iyi model, beklenen değişim)
## 📊 Model Karşılaştırma Tablosu (Model | MAPE% | Tahmini Değer | Trend | Güven)
## 🔮 En İyi Model Detayları (parametre, güven aralığı)
## 📊 Senaryo Analizi (İyimser | Baz | Kötümser senaryolar tablosu)
## ⚠️ Model Kısıtlamaları ve Varsayımlar
## ✅ Tahminlere Dayalı Aksiyon Önerileri
Güven aralıklarını ve belirsizlikleri mutlaka belirt.""",

        "pareto": f"""{base}
Pareto ve ABC analizi uzmanısın. Raporunu şu yapıda sun:
## 📊 Pareto Kuralı Sonucu (80/20 geçerli mi? tablo ile göster)
## 📋 ABC Sınıflandırma Tablosu (Sınıf | Öğe Sayısı | Toplam Değer | Pay% | Öğeler)
## 🏆 A Sınıfı Detay Analizi (her öğe ayrı, neden değerli?)
## 🔍 B Sınıfı Fırsat Analizi (A'ya çıkma potansiyeli)
## ⚠️ C Sınıfı Değerlendirme (optimize et veya kes)
## ✅ Kaynak Dağılımı Önerileri (bütçe, zaman, personel yüzdeleri)
Her öneriyi katkı yüzdeleriyle destekle.""",

        "quality": f"""{base}
Veri kalitesi denetçisisin. Profesyonel denetim raporu sun:
## 📊 Kalite Skor Kartı (Boyut | Skor | Not | Açıklama tablosu)
## 🔍 Bütünlük Analizi (eksik veri haritası, sütun bazlı tablo)
## 🔄 Teksillik Kontrolü (tekrar satır analizi)
## ⚡ Tutarlılık Denetimi (tip uyumsuzlukları, format sorunları)
## ✅ Geçerlilik Testi (aralık ihlalleri, mantıksal kontroller)
## 📋 Temizlik Planı (Adım | Sütun | İşlem | Öncelik tablosu)
## 📌 Sonuç (veri güvenilirlik değerlendirmesi)
Her sorunu somut örneklerle göster.""",

        # ── CEO-TIER ANALİZ TİPLERİ (v3.8.0 → v3.9.7 enhanced) ──
        "profitability": f"""{base}
CEO'ya hitap eden karlılık raporu sun:
## 💰 Karlılık Özeti (toplam gelir, maliyet, net kâr marjı)
## 📊 Segment Bazlı Karlılık Tablosu (Segment | Gelir | Maliyet | Net Kâr | Marj% | Sıralama)
## 🔴 Zarar Eden Segmentler (gizli maliyet analizi)
## 🟢 En Kârlı Segmentler (büyütme fırsatları)
## 💡 Fiyatlama Analizi ve Fırsatlar
## 📊 Contribution Margin Tablosu
## ✅ Patron'un Aksiyon Listesi (direkt TL/₺ etkisiyle)
Her bulguyu para birimi cinsinden ifade et.""",

        "bottleneck": f"""{base}
CEO'ya hitap eden darboğaz raporu sun:
## 🔴 Ana Darboğaz Tespiti (nerede, neden, ne kadar etkili?)
## 📊 Süreç Performans Tablosu (Adım | Süre | Kapasite% | Hata% | Maliyet | Skor)
## ⛓️ Zincirleme Etki Analizi (darboğazın domino etkisi)
## 📈 Kapasite ve Verimlilik Haritası
## 💡 İyileştirme Önerileri (ROI ile: Aksiyon | Maliyet | Tasarruf | Süre)
## ✅ Öncelikli Aksiyon Planı
Her darboğazın finansal etkisini hesapla.""",

        "executive": f"""{base}
CEO/CFO'ya hitap eden Şirket Sağlık Dashboard'u oluştur:
## 🏥 Genel Sağlık Skoru (0-100 puan, harf notu, durum)
## 📊 4 Boyut Tablosu (Boyut | Skor | Not | Trend | Renk)
- 💰 Finansal Sağlamlık
- ⚙️ Operasyonel Verimlilik
- 📈 Büyüme İvmesi
- 🛡️ Risk Maruziyet
## 🏆 En Güçlü 3 Gösterge
## ⚠️ En Zayıf 3 Gösterge (acil müdahale gereken)
## ✅ Stratejik Öncelikler (harf notuyla sıralı)
Tek bakışta anlaşılır dashboard formatı kullan.""",

        "benchmark": f"""{base}
CEO'ya hitap eden sektörel kıyaslama raporu sun:
## 📊 Kıyaslama Tablosu (KPI | Şirket | Sektör Ort. | En İyi | Konum | Gap)
## 🏆 Üstün Olduğumuz Alanlar (neden iyi, nasıl sürdürülür?)
## ⚠️ Geride Kaldığımız Alanlar (gap analizi, kapatma süresi)
## 📈 Rekabet Pozisyonu Değerlendirmesi
## 🎯 Hedef Belirleme (KPI | Mevcut | 3 Ay Hedef | 12 Ay Hedef)
## ✅ Gap Kapatma Aksiyon Planı
Her KPI'ı sektör benchmark'ı ile karşılaştır.""",
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


# ══════════════════════════════════════════════════════════════
# ANALİZ SONUÇLARINI DIŞA AKTAR (v3.9.7)
# ══════════════════════════════════════════════════════════════

EXPORT_AVAILABLE = False
try:
    from app.core.export_service import generate_export, get_export_info
    EXPORT_AVAILABLE = True
except Exception:
    pass


class AnalysisExportRequest(BaseModel):
    """Analiz sonucu export talebi"""
    content: str = Field(..., description="Analiz sonuç metni (markdown)")
    format: str = Field("excel", description="excel, pdf, csv, word, pptx")
    title: Optional[str] = Field(None, description="Rapor başlığı")
    analysis_type: Optional[str] = Field(None, description="Analiz tipi")
    filename: Optional[str] = Field(None, description="Orijinal dosya adı")


@router.post("/export")
async def export_analysis(
    req: AnalysisExportRequest,
    current_user: User = Depends(get_current_user),
):
    """Analiz sonucunu Excel/PDF/CSV/Word/PPTX olarak dışa aktar"""
    if not EXPORT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Export modülü kullanılamıyor")

    fmt = req.format.lower().strip()
    if fmt not in ("excel", "pdf", "csv", "word", "pptx"):
        raise HTTPException(status_code=400, detail=f"Desteklenmeyen format: {fmt}")

    # Başlık oluştur
    type_labels = {
        "full": "Tam Analiz", "pivot": "Pivot Tablo", "trend": "Trend Analizi",
        "compare": "Karşılaştırma", "summary": "Özet Rapor", "recommend": "Tavsiyeler",
        "report": "Profesyonel Rapor", "anomaly": "Anomali Tespiti", "correlation": "Korelasyon",
        "distribution": "Dağılım Analizi", "forecast": "Tahminleme", "pareto": "Pareto ABC",
        "quality": "Veri Kalitesi", "profitability": "Karlılık Analizi",
        "bottleneck": "Darboğaz Analizi", "executive": "Sağlık Skoru",
        "benchmark": "Kıyaslama Raporu",
    }
    title = req.title or type_labels.get(req.analysis_type, "Analiz Raporu")
    if req.filename:
        title = f"{title} — {req.filename}"

    try:
        result = generate_export(req.content, fmt, title)
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Export hatası"))

        return {
            "success": True,
            "file_id": result["file_id"],
            "filename": result["filename"],
            "format": fmt,
            "download_url": f"/export/download/{result['file_id']}",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("analysis_export_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Export sırasında hata: {str(e)}")


@router.get("/export/download/{file_id}")
async def download_analysis_export(
    file_id: str,
    current_user: User = Depends(get_current_user),
):
    """Export dosyasını indir"""
    if not EXPORT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Export modülü kullanılamıyor")

    info = get_export_info(file_id)
    if not info:
        raise HTTPException(status_code=404, detail="Dosya bulunamadı veya süresi dolmuş")

    import os
    if not os.path.exists(info["path"]):
        raise HTTPException(status_code=404, detail="Dosya disk üzerinde bulunamadı")

    media_types = {
        "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
        "csv": "text/csv",
        "word": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }

    return FileResponse(
        path=info["path"],
        filename=info["filename"],
        media_type=media_types.get(info["format"], "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{info["filename"]}"'},
    )
