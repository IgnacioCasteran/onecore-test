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
from ..aws_s3 import save_file  # esta función debe estar en aws_s3.py


router = APIRouter(prefix="/files", tags=["Files"])


@router.post(
    "/upload-csv",
    status_code=status.HTTP_201_CREATED,
    summary="Sube un archivo CSV, lo valida, lo guarda en S3 y registra el evento",
)
async def upload_csv(
    csv_file: UploadFile = File(...),
    dataset_name: str = Form(...),        # 🔹 parámetro adicional obligatorio
    description: str = Form(...),         # 🔹 parámetro adicional obligatorio
    db: Session = Depends(get_db),
    user=Depends(require_role("uploader")),  # solo usuarios con rol "uploader"
):
    # 1) Validar extensión
    if not csv_file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos con extensión .csv",
        )

    # 2) Leer contenido del archivo
    try:
        file_bytes: bytes = await csv_file.read()
        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo CSV está vacío",
            )
    finally:
        # Liberar el buffer interno de UploadFile
        await csv_file.close()

    # 3) Guardar archivo en S3 (o donde defina save_file)
    try:
        # BytesIO envuelve los bytes en un archivo en memoria tipo file-like
        location_type, storage_key = save_file(BytesIO(file_bytes), csv_file.filename)
    except Exception as e:
        # Cualquier problema con S3 / almacenamiento
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al guardar el archivo: {str(e)}",
        )

    # 4) Validar contenido del CSV
    try:
        validation = validate_csv_file(file_bytes)
    except Exception as e:
        # Si la validación explota, igual ya está guardado el archivo en S3,
        # pero devolvemos que hubo un problema en la validación.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al validar el CSV: {str(e)}",
        )

    validation_json = json.dumps(validation, ensure_ascii=False)

    # 5) Guardar registro del archivo y de cada fila en SQL Server
    try:
        # Registro del archivo
        csv_record = CsvFile(
            filename=csv_file.filename,
            dataset_name=dataset_name,         # 🔹 guardamos parámetros extra
            description=description,
            s3_key=storage_key,
            uploaded_by=int(user["sub"]),
            validation_summary=validation_json,
            uploaded_at=datetime.utcnow(),
        )
        db.add(csv_record)
        db.flush()  # para tener csv_record.id antes del commit

        # ===== Guardar filas del CSV en CsvRow =====
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
                f"Archivo {csv_file.filename} subido por usuario {user['sub']} "
                f"({location_type}:{storage_key}), "
                f"dataset='{dataset_name}'"
            ),
            created_at=datetime.utcnow(),  # tu modelo lo permite aunque tenga default
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
        "filename": csv_file.filename,
        "dataset_name": csv_record.dataset_name,
        "description": csv_record.description,
        "storage": {
            "type": location_type,  # por ejemplo: "s3"
            "key": storage_key,     # ruta/clave dentro del bucket
        },
        "validation": validation,   # estructura que devuelve validate_csv_file
    }
