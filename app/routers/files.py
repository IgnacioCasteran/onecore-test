# app/routers/files.py
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
import csv
import io as io_mod  # para usar io_mod.StringIO

from ..db import get_db
from ..models import CsvFile, EventLog, CsvRow
from ..security import require_role
from ..validators import validate_csv_file
from ..aws_s3 import save_file  # función para guardar en S3 (o similar)


router = APIRouter(prefix="/files", tags=["Files"])


@router.post(
    "/upload-csv",
    status_code=status.HTTP_201_CREATED,
    summary="Sube un archivo CSV, lo valida, lo guarda en S3 y registra el evento",
)
async def upload_csv(
    file: UploadFile = File(...),               # 👈 nombre que usan los tests
    dataset_name: str = Form(""),               # 👈 ahora OPCIONAL
    description: str = Form(""),                # 👈 ahora OPCIONAL
    db: Session = Depends(get_db),
    user=Depends(require_role("uploader")),     # solo usuarios con rol "uploader"
):
    """
    Endpoint para subir un CSV.

    - Valida que tenga extensión .csv
    - Lo guarda en S3 (o almacenamiento configurado)
    - Valida el contenido con `validate_csv_file`
    - Guarda registro en SQL Server (CsvFile + CsvRow)
    - Registra evento UPLOAD_CSV en EventLog
    """
    # 1) Validar extensión
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos con extensión .csv",
        )

    # 2) Leer contenido del archivo
    try:
        file_bytes: bytes = await file.read()
        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo CSV está vacío",
            )
    finally:
        await file.close()

    # 3) Guardar archivo en S3 (o donde defina save_file)
    try:
        location_type, storage_key = save_file(BytesIO(file_bytes), file.filename)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al guardar el archivo: {str(e)}",
        )

    # 4) Validar contenido del CSV
    try:
        validation = validate_csv_file(file_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al validar el CSV: {str(e)}",
        )

    validation_json = json.dumps(validation, ensure_ascii=False)

    # 5) Guardar registro del archivo y de cada fila en SQL Server
    try:
        # Registro del archivo
        csv_record = CsvFile(
            filename=file.filename,
            dataset_name=dataset_name or "",   # si viene vacío, guardamos string vacío
            description=description or "",
            s3_key=storage_key,
            uploaded_by=int(user["sub"]),
            validation_summary=validation_json,
            uploaded_at=datetime.utcnow(),
        )
        db.add(csv_record)
        db.flush()  # para tener csv_record.id antes del commit

        # Guardar filas del CSV en CsvRow
        text = file_bytes.decode("utf-8")
        reader = csv.DictReader(io_mod.StringIO(text))

        for i, row in enumerate(reader, start=1):
            row_json = json.dumps(row, ensure_ascii=False)
            db.add(
                CsvRow(
                    file_id=csv_record.id,
                    row_number=i,
                    data=row_json,
                )
            )

        # 6) Registrar evento en el histórico
        event = EventLog(
            event_type="UPLOAD_CSV",
            description=(
                f"Archivo {file.filename} subido por usuario {user['sub']} "
                f"({location_type}:{storage_key}), "
                f"dataset='{dataset_name or ''}'"
            ),
            created_at=datetime.utcnow(),
        )
        db.add(event)

        db.commit()
        db.refresh(csv_record)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al registrar el archivo en la base de datos: {str(e)}",
        )

    # 7) Respuesta al cliente
    return {
        "file_id": csv_record.id,
        "filename": csv_record.filename,
        "dataset_name": csv_record.dataset_name,
        "description": csv_record.description,
        "storage": {
            "type": location_type,
            "key": storage_key,
        },
        "validation": validation,
    }
