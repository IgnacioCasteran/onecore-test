from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(String(50), default="anonymous")

    # Relación inversa
    files = relationship("CsvFile", back_populates="user")


class CsvFile(Base):
    __tablename__ = "csvfiles"

    id = Column(Integer, primary_key=True)

    # Nombre del archivo real
    filename = Column(String(255), nullable=False)

    # Parámetros adicionales requeridos por el test
    dataset_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Archivo en S3
    s3_key = Column(String(500), nullable=False)

    # Usuario que lo subió
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Resumen JSON de validación
    validation_summary = Column(Text, nullable=False)

    uploaded_at = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    user = relationship("User", back_populates="files")

    rows = relationship(
        "CsvRow",
        back_populates="file",
        cascade="all, delete-orphan",
    )


class CsvRow(Base):
    """
    Representa cada fila del CSV procesado.
    Guarda el número de fila y el contenido JSON.
    """
    __tablename__ = "csvrows"

    id = Column(Integer, primary_key=True, index=True)

    file_id = Column(Integer, ForeignKey("csvfiles.id"), nullable=False)
    row_number = Column(Integer, nullable=False)

    # Fila completa como JSON
    data = Column(Text, nullable=False)

    file = relationship("CsvFile", back_populates="rows")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    filename = Column(String(255))
    s3_key = Column(String(500))
    doc_type = Column(String(50))
    extracted_data = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class EventLog(Base):
    __tablename__ = "eventlogs"

    id = Column(Integer, primary_key=True)
    event_type = Column(String(100))
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

