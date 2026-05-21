from datetime import datetime

from pydantic import BaseModel


class CalendarEventCreate(BaseModel):
    title: str
    start_datetime: datetime
    end_datetime: datetime
    kind: str = 'manual'
    notes: str | None = None
    meeting_url: str | None = None
    invite_emails: list[str] = []
    invited_user_ids: list[int] = []
    role_scope: str | None = None
    client_id: int | None = None
    search_id: int | None = None
    candidate_id: int | None = None


class CalendarEventOut(CalendarEventCreate):
    id: int
    created_by: int | None = None
    status: str = 'confirmed'
    organizer_email: str | None = None
    google_event_id: str | None = None
    mail_warnings: list[str] = []
    mails_sent: int = 0

    class Config:
        from_attributes = True
