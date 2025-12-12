# app/security.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

bearer = HTTPBearer()


def _utc_now() -> datetime:
    """Devuelve datetime timezone-aware en UTC (evita warnings de utcnow())."""
    return datetime.now(timezone.utc)


def create_access_token(
    user_id: int,
    role: str = "uploader",
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Crea un JWT de acceso.

    Compatibilidad con tests:
    - Los tests llaman: create_access_token(user_id=40)
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.JWT_EXP_MINUTES)

    exp = _utc_now() + expires_delta

    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": exp,
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


# Alias "de app" (para compatibilidad con código existente)
def create_token(user_id: int, role: str) -> str:
    """Alias legacy de la app: crea JWT a partir de user_id y role."""
    return create_access_token(user_id=user_id, role=role)


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decodifica y valida un JWT. Lanza HTTPException si es inválido o expirado.
    """
    try:
        decoded = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if not isinstance(decoded, dict):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        return decoded
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


# Alias "de app" (para compatibilidad con imports previos)
def decode_access_token(token: str) -> Dict[str, Any]:
    """Alias más explícito (opcional) por si querés usar naming estándar."""
    return decode_token(token)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> Dict[str, Any]:
    """
    Dependencia FastAPI: obtiene el usuario actual a partir del header Authorization: Bearer <token>.
    """
    return decode_token(credentials.credentials)


def require_role(role: str) -> Callable[..., Dict[str, Any]]:
    """
    Dependencia que exige que el usuario tenga un rol concreto.
    """
    def wrapper(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        if user.get("role") != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden",
            )
        return user

    return wrapper
