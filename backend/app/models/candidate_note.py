from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CandidateNote(Base):
    __tablename__ = "candidate_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), index=True)
    search_id: Mapped[int | None] = mapped_column(ForeignKey("searches.id"), nullable=True, index=True)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    note_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
