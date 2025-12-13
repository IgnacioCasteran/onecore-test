# app/routers/documents.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, Tuple

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..ai_utils import analyze_document as analyze_document_ai
from ..ai_utils import extract_text_from_document
from ..aws_s3 import save_file
from ..db import get_db
from ..models import Document, EventLog
from ..security import require_role

router = APIRouter(prefix="/documents", tags=["Documents"])

_ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}


def _utc_now() -> datetime:
    """Datetime timezone-aware en UTC (evita warnings de utcnow)."""
    return datetime.now(timezone.utc)


def _validate_document_upload(file: UploadFile) -> None:
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos PDF, JPG o PNG",
        )
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no tiene nombre",
        )


async def _read_upload_file(upload: UploadFile) -> bytes:
    try:
        data = await upload.read()
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo está vacío",
            )
        return data
    finally:
        await upload.close()


def _store_in_s3(file_bytes: bytes, filename: str) -> Tuple[str, str]:
    try:
        return save_file(BytesIO(file_bytes), filename)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al guardar el archivo: {str(e)}",
        )


def _extract_text(file_bytes: bytes, filename: str) -> str:
    try:
        return extract_text_from_document(file_bytes, filename)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al extraer texto del documento: {str(e)}",
        )


def _run_ai_analysis(text: str) -> Dict[str, Any]:
    try:
        return analyze_document_ai(text or "")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el análisis de IA del documento: {str(e)}",
        )


@router.post(
    "/analyze",
    status_code=status.HTTP_201_CREATED,
    summary="Sube un documento PDF/JPG/PNG, extrae texto, clasifica y registra evento",
)
async def analyze_document_endpoint(
    file: UploadFile = File(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(require_role("uploader")),
):
    """
    Sube un documento, lo guarda en S3, extrae texto (PDF->pypdf / imagen->OCR),
    ejecuta análisis (clasificación + extracción) y persiste en SQL Server.
    """
    _validate_document_upload(file)
    filename = file.filename  # ya validado que existe
    file_bytes = await _read_upload_file(file)

    location_type, storage_key = _store_in_s3(file_bytes, filename)

    text = _extract_text(file_bytes, filename)
    core_extracted = _run_ai_analysis(text)

    doc_type = core_extracted.get("doc_type", "informacion")

    extracted = {
        **core_extracted,
        "description": description,
        "text": text,
    }
    extracted_json = json.dumps(extracted, ensure_ascii=False)

    try:
        document = Document(
            filename=filename,
            s3_key=storage_key,
            doc_type=doc_type,
            extracted_data=extracted_json,
            created_at=_utc_now(),
        )
        db.add(document)

        event = EventLog(
            event_type="DOC_ANALYSIS",
            description=(
                f"Documento {filename} ({doc_type}) analizado y guardado por "
                f"usuario {user['sub']} ({location_type}:{storage_key})"
            ),
            created_at=_utc_now(),
        )
        db.add(event)

        db.commit()
        db.refresh(document)

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al registrar el documento en la base de datos: {str(e)}",
        )

    return {
        "document_id": document.id,
        "filename": document.filename,
        "doc_type": document.doc_type,
        "storage": {"type": location_type, "key": storage_key},
        "extracted": extracted,
    }
