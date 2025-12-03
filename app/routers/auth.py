from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import timedelta
from ..db import get_db
from ..models import User
from ..security import create_token, decode_token
from ..schemas import LoginResponse, TokenResponse
from ..config import settings

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/login", response_model=LoginResponse)
def login(db: Session = Depends(get_db)):
    # Crear usuario anónimo
    user = User(role="uploader")
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token(user.id, user.role)

    return LoginResponse(
        id_usuario=user.id,
        rol=user.role,
        token=TokenResponse(
            access_token=token,
            expires_in=settings.JWT_EXP_MINUTES * 60
        )
    )

@router.post("/refresh", response_model=TokenResponse)
def refresh(token: str):
    payload = decode_token(token)
    new_token = create_token(payload["sub"], payload["role"])
    return TokenResponse(
        access_token=new_token,
        expires_in=settings.JWT_EXP_MINUTES * 60
    )
