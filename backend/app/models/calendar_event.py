from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CalendarEvent(Base):
    __tablename__ = 'calendar_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    start_datetime: Mapped[datetime] = mapped_column(DateTime)
    end_datetime: Mapped[datetime] = mapped_column(DateTime)
    kind: Mapped[str] = mapped_column(String(50), default='manual')
    status: Mapped[str] = mapped_column(String(40), default='confirmed')
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    meeting_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    organizer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invite_emails_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    invited_user_ids_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    role_scope: Mapped[str | None] = mapped_column(String(50), nullable=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey('clients.id'), nullable=True)
    search_id: Mapped[int | None] = mapped_column(ForeignKey('searches.id'), nullable=True)
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey('candidates.id'), nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
