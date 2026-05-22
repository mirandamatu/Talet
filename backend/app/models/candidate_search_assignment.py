from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CandidateSearchAssignment(Base):
    __tablename__ = "candidate_search_assignments"
    __table_args__ = (
        UniqueConstraint("candidate_id", "search_id", name="uq_candidate_search_assignment_pair"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), index=True)
    search_id: Mapped[int] = mapped_column(ForeignKey("searches.id"), index=True)
    status: Mapped[str] = mapped_column(String(50), default="en_revision")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    candidate = relationship("Candidate", back_populates="search_assignments")
    search = relationship("Search", back_populates="candidate_assignments")
