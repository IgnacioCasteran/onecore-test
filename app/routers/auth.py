# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import User
from ..schemas import LoginResponse, TokenResponse
from ..security import create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=LoginResponse, summary="Login anónimo (genera JWT)")
def login(db: Session = Depends(get_db)) -> LoginResponse:
    """
    Crea un usuario anónimo con rol 'uploader' y devuelve un JWT.
    (No requiere username/password, tal como pide el examen).
    """
    user = User(role="uploader")
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user_id=user.id, role=user.role)

    return LoginResponse(
        id_usuario=user.id,
        rol=user.role,
        token=TokenResponse(
            access_token=token,
            expires_in=settings.JWT_EXP_MINUTES * 60,
        ),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renueva el JWT usando el token actual",
)
def refresh(user: dict = Depends(get_current_user)) -> TokenResponse:
    """
    Renueva el token de acceso.

    Importante: este endpoint NO exige body.
    Funciona solo con Authorization: Bearer <token> (como tus tests).
    """
    sub = user.get("sub")
    role = user.get("role", "uploader")

    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    new_token = create_access_token(user_id=user_id, role=role)

    return TokenResponse(
        access_token=new_token,
        expires_in=settings.JWT_EXP_MINUTES * 60,
    )
