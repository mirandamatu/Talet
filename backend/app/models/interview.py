from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Interview(Base):
    __tablename__ = 'interviews'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey('candidates.id'))
    slot_id: Mapped[int] = mapped_column(ForeignKey('availability_slots.id'))
    calendar_event_id: Mapped[int | None] = mapped_column(ForeignKey('calendar_events.id'), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default='booked')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    candidate = relationship('Candidate', back_populates='interviews')
