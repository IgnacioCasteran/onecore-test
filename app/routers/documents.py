# app/routers/documents.py
from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Depends,
    HTTPException,
    status,
    Form,
)
from sqlalchemy.orm import Session
from datetime import datetime
from io import BytesIO
import json

from ..db import get_db
from ..models import Document, EventLog
from ..security import require_role
from ..aws_s3 import save_file
from ..ai_utils import extract_text_from_document, analyze_document as analyze_document_ai

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/analyze",
    status_code=status.HTTP_201_CREATED,
    summary="Sube un documento PDF/JPG/PNG, extrae texto, clasifica y registra evento",
)
async def analyze_document_endpoint(
    file: UploadFile = File(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(require_role("uploader")),  # mismo rol que para CSV
):
    # 1) Validar tipo de archivo
    allowed_types = {
        "application/pdf",
        "image/jpeg",
        "image/png",
    }
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos PDF, JPG o PNG",
        )

    # 2) Leer contenido
    file_bytes: bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo está vacío",
        )

    # 3) Guardar en S3
    try:
        location_type, storage_key = save_file(BytesIO(file_bytes), file.filename)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al guardar el archivo: {str(e)}",
        )

    # 4) Extraer texto (usa pypdf si es PDF, Tesseract si es imagen)
    try:
        text = extract_text_from_document(file_bytes, file.filename)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al extraer texto del documento: {str(e)}",
        )

    # 5) Análisis de IA (clasificación + extracción de campos)
    try:
        core_extracted = analyze_document_ai(text or "")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el análisis de IA del documento: {str(e)}",
        )

    # doc_type viene de la IA ("factura" o "informacion")
    doc_type = core_extracted.get("doc_type", "informacion")

    # 6) Datos extraídos finales: campos + descripción + texto bruto
    extracted = {
        **core_extracted,
        "description": description,
        "text": text,
    }
    extracted_json = json.dumps(extracted, ensure_ascii=False)

    # 7) Guardar en SQL Server + registro de evento
    try:
        document = Document(
            filename=file.filename,
            s3_key=storage_key,
            doc_type=doc_type,
            extracted_data=extracted_json,
            created_at=datetime.utcnow(),
        )
        db.add(document)

        event = EventLog(
            event_type="DOC_ANALYSIS",
            description=(
                f"Documento {file.filename} ({doc_type}) analizado y guardado por "
                f"usuario {user['sub']} ({location_type}:{storage_key})"
            ),
            created_at=datetime.utcnow(),
        )
        db.add(event)

        db.commit()
        db.refresh(document)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al registrar el documento en la base de datos: {str(e)}",
        )

    # 8) Respuesta
    return {
        "document_id": document.id,
        "filename": document.filename,
        "doc_type": document.doc_type,
        "storage": {
            "type": location_type,
            "key": storage_key,
        },
        "extracted": extracted,  # lo mismo que guardamos en extracted_data
    }
