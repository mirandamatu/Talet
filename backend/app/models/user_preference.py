from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    notification_settings_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reminder_settings_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    default_stale_search_days: Mapped[int] = mapped_column(Integer, default=14)
    default_no_response_days: Mapped[int] = mapped_column(Integer, default=7)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user = relationship("User", back_populates="preferences")
