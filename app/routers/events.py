# app/routers/events.py
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime
from io import BytesIO
import pandas as pd

from ..db import get_db
from ..models import EventLog
from ..security import require_role

router = APIRouter(prefix="/events", tags=["Events"])


@router.get(
    "",
    summary="Lista el histórico de eventos con filtros opcionales",
)
def list_events(
    db: Session = Depends(get_db),
    event_type: str | None = Query(None),
    description: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    user=Depends(require_role("uploader")),  # podrías cambiar a 'admin' si quieres
):
    query = db.query(EventLog)

    if event_type:
        query = query.filter(EventLog.event_type == event_type)

    if description:
        query = query.filter(EventLog.description.ilike(f"%{description}%"))

    if date_from:
        query = query.filter(EventLog.created_at >= date_from)

    if date_to:
        query = query.filter(EventLog.created_at <= date_to)

    events = query.order_by(EventLog.created_at.desc()).all()

    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "description": e.description,
            "created_at": e.created_at,
        }
        for e in events
    ]


@router.get(
    "/export",
    summary="Exporta el histórico de eventos filtrado a un archivo Excel",
)
def export_events_to_excel(
    db: Session = Depends(get_db),
    event_type: str | None = Query(None),
    description: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    user=Depends(require_role("uploader")),  # idem, se puede cambiar a 'admin'
):
    query = db.query(EventLog)

    if event_type:
        query = query.filter(EventLog.event_type == event_type)

    if description:
        query = query.filter(EventLog.description.ilike(f"%{description}%"))

    if date_from:
        query = query.filter(EventLog.created_at >= date_from)

    if date_to:
        query = query.filter(EventLog.created_at <= date_to)

    events = query.order_by(EventLog.created_at.desc()).all()

    rows = [
        {
            "ID": e.id,
            "Tipo": e.event_type,
            "Descripción": e.description,
            "FechaHora": e.created_at,
        }
        for e in events
    ]

    if not rows:
        raise HTTPException(status_code=404, detail="No hay eventos para exportar")

    df = pd.DataFrame(rows)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Eventos")

    output.seek(0)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"eventos_{timestamp}.xlsx"

    return StreamingResponse(
        output,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
