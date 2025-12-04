# 🧪 Evaluación Técnica OneCore — Parte 1  
API Web con Python + FastAPI + JWT + S3 + SQL Server

**Parte 1** de la evaluación técnica para OneCore**, donde se desarrolla una aplicación backend en Python utilizando **FastAPI**, con autenticación mediante **JWT**, carga y validación de archivos CSV, almacenamiento en **AWS S3** y persistencia en **SQL Server**.

---

## 📌 Características implementadas en la Parte 1

### ✔️ 1. Autenticación con JWT
- Endpoint `/auth/login` permite iniciar sesión como usuario anónimo.
- Genera un **JWT firmado** con:
  - `sub` → id del usuario  
  - `role`  
  - `exp` → 15 minutos  

### ✔️ 2. Renovación de Token
- Endpoint `/auth/refresh`
- Recibe un token válido y genera uno nuevo.
- Solo funciona si el token **no ha expirado**.

### ✔️ 3. Carga, validación y almacenamiento de archivos CSV
- Endpoint protegido `/files/upload-csv` (requiere rol `uploader`)
- Se envía:
  - Archivo CSV
  - `dataset_name`
  - `description`
- El servicio:
  - Valida el CSV (estructura, columnas, contenido)
  - Guarda el archivo en **AWS S3**
  - Registra el archivo en la tabla `csvfiles`
  - Guarda cada fila en `csvrows`
  - Registra un evento en `eventlogs`

---

## 🧱 Requisitos del Proyecto

- Python **3.10+**
- SQL Server (local o remoto)
- Cuenta AWS con acceso a S3
- Archivo `.env` configurado

---

## 🔧 Instalación y Configuración

1️⃣ Clonar el repositorio
```bash
git clone https://github.com/tu_usuario/onecore-test.git
cd onecore-test

2️⃣ Crear entorno virtual
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows

3️⃣ Instalar dependencias
pip install -r requirements.txt

4️⃣ Crear archivo .env
Ejemplo:
SECRET_KEY=clave_secreta
AWS_ACCESS_KEY_ID=xxxx
AWS_SECRET_ACCESS_KEY=xxxx
AWS_BUCKET_NAME=mi_bucket
SQLSERVER_HOST=localhost
SQLSERVER_DB=onecore_db
SQLSERVER_USER=sa
SQLSERVER_PASSWORD=xxxx

▶️ Ejecutar la aplicación
uvicorn app.main:app --reload

Documentación interactiva:

👉 http://127.0.0.1:8000/docs
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
🔐 Endpoints de Autenticación
POST /auth/login

Devuelve un JWT válido por 15 minutos.

Ejemplo de respuesta:
{
  "access_token": "jwt_generado",
  "token_type": "bearer",
  "expires_in": 900
}

POST /auth/refresh?token=jwt_valido

Renueva el token si aún no expiró.
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
📤 Endpoint para subir CSV
POST /files/upload-csv

Content-Type: multipart/form-data

Campos requeridos:
| Campo        | Tipo   | Descripción        |
| ------------ | ------ | ------------------ |
| csv_file     | file   | Archivo CSV        |
| dataset_name | string | Nombre del dataset |
| description  | string | Descripción        |

Ejemplo de respuesta:
{
  "file_id": 3,
  "filename": "prueba.csv",
  "dataset_name": "clientes_noviembre",
  "description": "Carga de prueba",
  "storage": {
    "type": "s3",
    "key": "uploads/archivo.csv"
  },
  "validation": {
    "row_count": 2,
    "columns": ["id", "nombre", "monto"],
    "issues": []
  }
}
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
🗄️ Estructura de Tablas (SQL Server)
Tabla csvfiles
| Campo              | Tipo     |
| ------------------ | -------- |
| id                 | int      |
| filename           | varchar  |
| dataset_name       | varchar  |
| description        | text     |
| s3_key             | varchar  |
| uploaded_by        | int      |
| validation_summary | text     |
| uploaded_at        | datetime |

Tabla csvrows
| Campo      | Tipo |
| ---------- | ---- |
| id         | int  |
| file_id    | int  |
| row_number | int  |
| data       | text |

Tabla eventlogs
| Campo       | Tipo     |
| ----------- | -------- |
| id          | int      |
| event_type  | varchar  |
| description | text     |
| created_at  | datetime |
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
✔️Parte 1
La Parte 1 está 100% funcional, incluyendo:

.Autenticación JWT

.Renovación de token

.Carga/validación/almacenamiento de CSV

.Persistencia en SQL Server

.Storage en AWS S3

.Registro histórico de eventos
