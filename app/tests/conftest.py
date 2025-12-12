# tests/conftest.py
import io
import pytest
from fastapi.testclient import TestClient

from app.main import app  # ajusta si tu archivo se llama distinto
from app.security import create_access_token


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture
def jwt_token():
    """
    Crea un JWT válido como si hubiera pasado por /auth/login.
    Reutiliza tu misma función de seguridad.
    """
    # En tu implementación el 'sub' es el id de usuario (por ejemplo 40)
    return create_access_token(user_id=40)


@pytest.fixture
def auth_headers(jwt_token):
    return {"Authorization": f"Bearer {jwt_token}"}
