from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Candidate(Base):
    __tablename__ = 'candidates'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey('clients.id'), nullable=True, index=True)
    search_id: Mapped[int | None] = mapped_column(ForeignKey('searches.id'), nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    short_profile: Mapped[str | None] = mapped_column(Text, nullable=True)
    cv_file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cv_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cv_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default='en_revision')
    source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    client = relationship('Client', foreign_keys=[client_id])
    search = relationship('Search', back_populates='candidates', foreign_keys=[search_id])
    history = relationship('StatusHistory', back_populates='candidate')
    feedback = relationship('Feedback', back_populates='candidate')
    interviews = relationship('Interview', back_populates='candidate')
    presentations = relationship('CandidatePresentation', back_populates='candidate')
    search_assignments = relationship('CandidateSearchAssignment', back_populates='candidate')
