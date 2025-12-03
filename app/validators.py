from io import BytesIO
from typing import Dict, Any, List
import pandas as pd

def validate_csv_file(file_bytes: bytes) -> Dict[str, Any]:
    """
    Valida un CSV:
      - detecta filas con valores vacíos
      - detecta filas duplicadas
    Devuelve un resumen que podemos guardar en SQL Server.
    """
    buffer = BytesIO(file_bytes)
    df = pd.read_csv(buffer)

    issues: List[str] = []

    # Valores vacíos
    empty_rows = df[df.isnull().any(axis=1)]
    if not empty_rows.empty:
        issues.append(f"Filas con valores vacíos: {empty_rows.index.tolist()}")

    # Duplicados completos
    duplicated = df[df.duplicated()]
    if not duplicated.empty:
        issues.append(f"Filas duplicadas: {duplicated.index.tolist()}")

    summary = {
        "row_count": int(len(df)),
        "columns": list(df.columns),
        "issues": issues,
    }
    return summary
