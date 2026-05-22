from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Search(Base):
    __tablename__ = 'searches'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey('clients.id'))
    title: Mapped[str] = mapped_column(String(200))
    job_description: Mapped[str] = mapped_column(Text)
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    manual_state: Mapped[str | None] = mapped_column(String(30), nullable=True)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_talent_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    alert_stale_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alert_no_response_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    placed_candidate_id: Mapped[int | None] = mapped_column(ForeignKey('candidates.id'), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    client = relationship('Client', back_populates='searches')
    candidates = relationship('Candidate', back_populates='search', foreign_keys='Candidate.search_id')
    candidate_assignments = relationship('CandidateSearchAssignment', back_populates='search')
    slots = relationship('AvailabilitySlot', back_populates='search')
    documents = relationship('SearchDocument', back_populates='search', cascade='all, delete-orphan')
    ai_questions = relationship('SearchAIQuestion', back_populates='search', cascade='all, delete-orphan')
    assigned_talent = relationship('User', foreign_keys=[assigned_talent_user_id])
