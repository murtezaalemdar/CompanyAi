"""Export API Routes — Dosya indirme ve export yönetimi"""

import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from app.api.routes.auth import get_current_user
from app.db.models import User
from app.core.export_service import (
    generate_export, get_export_info, detect_export_request,
    FORMAT_LABELS,
)

import structlog

logger = structlog.get_logger()

router = APIRouter()


class ExportRequest(BaseModel):
    content: str
    format: str  # excel, pdf, pptx, word, csv
    title: Optional[str] = "Rapor"


class ExportResponse(BaseModel):
    success: bool
    file_id: Optional[str] = None
    filename: Optional[str] = None
    format: Optional[str] = None
    download_url: Optional[str] = None
    error: Optional[str] = None


@router.post("/generate", response_model=ExportResponse)
async def generate_export_file(
    request: ExportRequest,
    current_user: User = Depends(get_current_user),
):
    """AI yanıtını istenen formatta dosya olarak üretir."""
    if request.format not in FORMAT_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"Desteklenmeyen format: {request.format}. "
                   f"Desteklenen: {', '.join(FORMAT_LABELS.keys())}"
        )
    
    if not request.content or len(request.content.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Export için yeterli içerik yok."
        )
    
    result = generate_export(
        content=request.content,
        fmt=request.format,
        title=request.title or "Rapor",
    )
    
    if not result:
        return ExportResponse(
            success=False,
            error="Dosya oluşturulurken hata oluştu."
        )
    
    logger.info("export_generated",
                user_id=current_user.id,
                format=request.format,
                file_id=result["file_id"])
    
    return ExportResponse(
        success=True,
        file_id=result["file_id"],
        filename=result["filename"],
        format=result["format"],
        download_url=f"/api/export/download/{result['file_id']}",
    )


@router.get("/download/{file_id}")
async def download_export(
    file_id: str,
    current_user: User = Depends(get_current_user),
):
    """Export edilmiş dosyayı indirir."""
    info = get_export_info(file_id)
    if not info:
        raise HTTPException(status_code=404, detail="Dosya bulunamadı veya süresi dolmuş.")
    
    filepath = info["path"]
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Dosya sunucuda bulunamadı.")
    
    logger.info("export_downloaded", file_id=file_id, format=info["format"])
    
    return FileResponse(
        path=filepath,
        filename=info["filename"],
        media_type=info["content_type"],
        headers={
            "Content-Disposition": f'attachment; filename="{info["filename"]}"',
        },
    )


@router.get("/formats")
async def list_formats(
    current_user: User = Depends(get_current_user),
):
    """Desteklenen export formatlarını listeler."""
    return {
        "formats": [
            {"key": k, **v} for k, v in FORMAT_LABELS.items()
        ]
    }
