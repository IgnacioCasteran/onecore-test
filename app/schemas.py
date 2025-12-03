from pydantic import BaseModel
from datetime import datetime

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class LoginResponse(BaseModel):
    id_usuario: int
    rol: str
    token: TokenResponse
