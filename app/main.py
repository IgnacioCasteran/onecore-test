from fastapi import FastAPI
from .routers import auth, files
from .db import Base, engine

app = FastAPI(title="OneCore Technical Test")

# Crear tablas
Base.metadata.create_all(bind=engine)

# Rutas
app.include_router(auth.router)
app.include_router(files.router)

@app.get("/ping")
def ping():
    return {"message": "pong"}

