# app/aws_s3.py
import uuid
import io
import boto3
from botocore.client import Config

from .config import settings

# Cliente S3
s3 = boto3.client(
    "s3",
    aws_access_key_id=settings.AWS_ACCESS_KEY,
    aws_secret_access_key=settings.AWS_SECRET_KEY,
    region_name=settings.AWS_REGION,
    config=Config(signature_version="s3v4"),
)

BUCKET = settings.AWS_BUCKET


def _guess_content_type(filename: str) -> str:
    name = filename.lower()

    if name.endswith(".csv"):
        return "text/csv"
    if name.endswith(".pdf"):
        return "application/pdf"
    if name.endswith(".jpg") or name.endswith(".jpeg"):
        return "image/jpeg"
    if name.endswith(".png"):
        return "image/png"

    return "application/octet-stream"


def save_file(file_obj: io.BytesIO, filename: str):
    """
    Guarda un archivo genérico en S3 y devuelve (tipo, clave).

    - file_obj: instancia de BytesIO (importante: se hace seek(0) dentro).
    - filename: nombre original del archivo.

    return:
        ("s3", storage_key)
    """
    file_obj.seek(0)

    ext = filename.split(".")[-1].lower() if "." in filename else "bin"
    storage_key = f"uploads/{uuid.uuid4()}.{ext}"

    content_type = _guess_content_type(filename)

    s3.upload_fileobj(
        file_obj,
        BUCKET,
        storage_key,
        ExtraArgs={"ContentType": content_type},
    )

    return "s3", storage_key

