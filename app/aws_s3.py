import io
import uuid
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


def save_file(file_obj: io.BytesIO, filename: str):
    """
    Guarda un archivo en S3.

    file_obj -> BytesIO
    filename -> nombre original del archivo

    return:
        ("s3", storage_key)
    """

    # Nos aseguramos que el puntero está al inicio
    file_obj.seek(0)

    # extensión real
    ext = filename.split(".")[-1].lower() if "." in filename else "bin"
    storage_key = f"uploads/{uuid.uuid4()}.{ext}"

    # Tipo de contenido simple (ahora mismo solo usamos CSV)
    content_type = "text/csv" if ext == "csv" else "application/octet-stream"

    # Subir archivo
    s3.upload_fileobj(
        file_obj,
        BUCKET,
        storage_key,
        ExtraArgs={"ContentType": content_type},
    )

    return "s3", storage_key

