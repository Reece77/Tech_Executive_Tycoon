from __future__ import annotations

from pydantic import BaseModel


class ErrorOut(BaseModel):
    """Stable error body for every 4xx response."""

    code: str
    message: str
    event_id: int | None = None  # critical_event_open: the event blocking Continue (M6)
