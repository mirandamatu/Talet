from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CandidatePresentation(Base):
    __tablename__ = "candidate_presentations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), index=True)
    search_id: Mapped[int] = mapped_column(ForeignKey("searches.id"), index=True)
    presented_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    presented_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    candidate = relationship("Candidate", back_populates="presentations")
    search = relationship("Search")
    presenter = relationship("User")
