# app/security.py
from datetime import datetime, timedelta

import jwt
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .config import settings

# Esquema Bearer usado por las dependencias de FastAPI
bearer = HTTPBearer()


def create_access_token(
    user_id: int,
    role: str = "uploader",
    expires_delta: timedelta | None = None,
) -> str:
    """
    Crea un JWT de acceso.

    Compatibilidad con los tests:
    -----------------------------
    Los tests llaman: create_access_token(user_id=40)

    Por eso la firma acepta 'user_id' como primer parámetro,
    y un 'role' opcional con valor por defecto "uploader".
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.JWT_EXP_MINUTES)

    expire = datetime.utcnow() + expires_delta

    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
    }

    encoded_jwt = jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def create_token(user_id: int, role: str) -> str:
    """
    Helper específico de la app que reutiliza create_access_token.
    """
    return create_access_token(user_id=user_id, role=role)


def decode_token(token: str) -> dict:
    """
    Decodifica y valida un JWT. Lanza HTTPException si es inválido o expirado.
    """
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> dict:
    """
    Dependencia FastAPI: obtiene el usuario actual a partir del header Authorization: Bearer.
    """
    token = credentials.credentials
    return decode_token(token)


def require_role(role: str):
    """
    Dependencia que exige que el usuario tenga un rol concreto.
    Se usa en los endpoints protegidos.
    """
    def wrapper(user=Depends(get_current_user)):
        if user.get("role") != role:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return wrapper
