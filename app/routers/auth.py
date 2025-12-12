# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
from ..db import get_db
from ..models import User
from ..security import create_access_token, get_current_user   # 👈 usamos estas
from ..schemas import LoginResponse, TokenResponse
from ..config import settings

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=LoginResponse)
def login(db: Session = Depends(get_db)):
    """
    Crea un usuario anónimo con rol 'uploader' y devuelve un JWT.

    Este endpoint está pensado para simplificar el examen:
    no pedimos usuario/contraseña, igual que en el Swagger.
    """
    # Crear usuario anónimo
    user = User(role="uploader")
    db.add(user)
    db.commit()
    db.refresh(user)

    # Creamos el token usando la misma función que usan los tests
    token = create_access_token(user_id=user.id, role=user.role)

    return LoginResponse(
        id_usuario=user.id,
        rol=user.role,
        token=TokenResponse(
            access_token=token,
            expires_in=settings.JWT_EXP_MINUTES * 60,
        ),
    )


@router.post("/refresh", response_model=TokenResponse, summary="Renueva el JWT usando el token actual")
def refresh(user: dict = Depends(get_current_user)):
    """
    Renueva el token de acceso.

    IMPORTANTE:
    - Los tests llaman a este endpoint así:
        POST /auth/refresh
        con solo el header Authorization: Bearer <token>
    - Por eso NO debemos exigir body ni parámetros extra.
    """
    try:
        user_id = int(user.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    role = user.get("role", "uploader")

    new_token = create_access_token(user_id=user_id, role=role)

    return TokenResponse(
        access_token=new_token,
        expires_in=settings.JWT_EXP_MINUTES * 60,
    )
