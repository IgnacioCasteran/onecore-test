# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

from .db import Base, engine
from .routers import auth, files, documents, events

# ==================================
# Cargar .env al iniciar la API
# ==================================
load_dotenv()

print("\n=========== VARIABLES .ENV CARGADAS ===========")
print("USE_TEXTRACT =", os.getenv("USE_TEXTRACT"))
print("AWS_REGION =", os.getenv("AWS_REGION"))
print("AWS_ACCESS_KEY =", "OK" if os.getenv("AWS_ACCESS_KEY") else "MISSING")
print("AWS_SECRET_KEY =", "OK" if os.getenv("AWS_SECRET_KEY") else "MISSING")
print("AWS_BUCKET =", os.getenv("AWS_BUCKET"))
print("================================================\n")


# API FastAPI
app = FastAPI(title="OneCore Technical Test")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # <- permite cualquier origen (incluye 'null')
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Crear tablas
Base.metadata.create_all(bind=engine)

# Registrar routers
app.include_router(auth.router)
app.include_router(files.router)
app.include_router(documents.router)
app.include_router(events.router)


@app.get("/ping")
def ping():
    return {"message": "pong"}

