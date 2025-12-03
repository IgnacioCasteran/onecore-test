import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "OneCore API"

    # ================================
    # JWT
    # ================================
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev_key_change_me")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXP_MINUTES: int = 15

    # ================================
    # SQL SERVER LOCAL (SQLEXPRESS)
    # ================================
    SQLSERVER_HOST: str = os.getenv("SQLSERVER_HOST", r"localhost\SQLEXPRESS")
    SQLSERVER_DB: str = os.getenv("SQLSERVER_DB", "onecore_db")

    @property
    def DATABASE_URI(self) -> str:
        # Asegúrate de tener instalado el ODBC Driver 17 o 18
        driver = "ODBC Driver 17 for SQL Server"
        return (
            "mssql+pyodbc://@"
            f"{self.SQLSERVER_HOST}/{self.SQLSERVER_DB}"
            f"?driver={driver.replace(' ', '+')}&trusted_connection=yes"
        )

    # ================================
    # AWS – CREDENCIALES PARA S3
    # ================================
    AWS_ACCESS_KEY: str = os.getenv("AWS_ACCESS_KEY", "")
    AWS_SECRET_KEY: str = os.getenv("AWS_SECRET_KEY", "")
    AWS_BUCKET: str = os.getenv("AWS_BUCKET", "onecore-bucket")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")  # ← AGREGADO (IMPORTANTE)


settings = Settings()

