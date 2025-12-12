# app/routers/files.py
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, Tuple

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..aws_s3 import save_file
from ..db import get_db
from ..models import CsvFile, CsvRow, EventLog
from ..security import require_role
from ..validators import validate_csv_file

router = APIRouter(prefix="/files", tags=["Files"])


def _utc_now() -> datetime:
    """Datetime timezone-aware en UTC."""
    return datetime.now(timezone.utc)


def _ensure_csv_filename(filename: str | None) -> str:
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no tiene nombre",
        )
    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos con extensión .csv",
        )
    return filename


async def _read_upload_file(upload: UploadFile) -> bytes:
    try:
        data = await upload.read()
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo CSV está vacío",
            )
        return data
    finally:
        await upload.close()


def _store_in_s3(file_bytes: bytes, filename: str) -> Tuple[str, str]:
    """Guarda en S3 (o backend definido por save_file)."""
    try:
        storage_type, storage_key = save_file(BytesIO(file_bytes), filename)
        return storage_type, storage_key
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al guardar el archivo: {str(e)}",
        )


def _parse_csv_rows(file_bytes: bytes) -> list[dict]:
    """
    Parsea filas del CSV como dicts.

    Usa utf-8-sig para tolerar BOM (muy común en CSV exportados).
    """
    try:
        text = file_bytes.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        return list(reader)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al leer el CSV: {str(e)}",
        )


@router.post(
    "/upload-csv",
    status_code=status.HTTP_201_CREATED,
    summary="Sube un archivo CSV, lo valida, lo guarda en S3 y registra el evento",
)
async def upload_csv(
    file: UploadFile = File(...),          # 👈 nombre que usan los tests
    dataset_name: str = Form(""),          # 👈 opcional
    description: str = Form(""),           # 👈 opcional
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(require_role("uploader")),
) -> Dict[str, Any]:
    """
    Endpoint para subir un CSV.

    Flujo:
    1) valida extensión
    2) lee bytes
    3) guarda en S3
    4) valida contenido
    5) guarda CsvFile + CsvRow + EventLog en DB
    6) responde metadata + validación
    """
    filename = _ensure_csv_filename(file.filename)
    file_bytes = await _read_upload_file(file)

    storage_type, storage_key = _store_in_s3(file_bytes, filename)

    # Validación lógica del CSV (vacíos, duplicados, tipos, etc.)
    try:
        validation = validate_csv_file(file_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al validar el CSV: {str(e)}",
        )

    validation_json = json.dumps(validation, ensure_ascii=False)

    # Persistencia en DB
    try:
        csv_record = CsvFile(
            filename=filename,
            dataset_name=(dataset_name or "").strip(),
            description=(description or "").strip(),
            s3_key=storage_key,
            uploaded_by=int(user["sub"]),
            validation_summary=validation_json,
            uploaded_at=_utc_now(),
        )
        db.add(csv_record)
        db.flush()  # obtener csv_record.id antes del commit

        # Guardar filas del CSV
        rows = _parse_csv_rows(file_bytes)
        for i, row in enumerate(rows, start=1):
            db.add(
                CsvRow(
                    file_id=csv_record.id,
                    row_number=i,
                    data=json.dumps(row, ensure_ascii=False),
                )
            )

        # Registrar evento
        db.add(
            EventLog(
                event_type="UPLOAD_CSV",
                description=(
                    f"Archivo {filename} subido por usuario {user['sub']} "
                    f"({storage_type}:{storage_key}), "
                    f"dataset='{(dataset_name or '').strip()}'"
                ),
                created_at=_utc_now(),
            )
        )

        db.commit()
        db.refresh(csv_record)

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al registrar el archivo en la base de datos: {str(e)}",
        )

    return {
        "file_id": csv_record.id,
        "filename": csv_record.filename,
        "dataset_name": csv_record.dataset_name,
        "description": csv_record.description,
        "storage": {"type": storage_type, "key": storage_key},
        "validation": validation,
    }
