from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Client(Base):
    __tablename__ = 'clients'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(50), default='active')
    public_slug: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(20), default='starter')
    plan_status: Mapped[str] = mapped_column(String(20), default='trial')
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey('organizations.id'), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    organization = relationship('Organization', back_populates='clients')
    users = relationship('User', back_populates='client')
    searches = relationship('Search', back_populates='client')
    user_links = relationship('UserClient', back_populates='client', cascade='all, delete-orphan')
    profile = relationship('ClientProfile', back_populates='client', uselist=False, cascade='all, delete-orphan')
    contacts = relationship('ClientContact', back_populates='client', cascade='all, delete-orphan')
