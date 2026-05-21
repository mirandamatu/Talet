from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SearchCandidateAnalysis(Base):
    __tablename__ = "search_candidate_analyses"
    __table_args__ = (
        UniqueConstraint("search_id", "candidate_id", name="uq_search_candidate_analysis_pair"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_id: Mapped[int] = mapped_column(ForeignKey("searches.id"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), index=True)
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommendation_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasons_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    source_hash: Mapped[str] = mapped_column(String(64), index=True)
    model_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_analyzed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
