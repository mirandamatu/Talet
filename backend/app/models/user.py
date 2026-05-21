from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50))
    organization_id: Mapped[int | None] = mapped_column(ForeignKey('organizations.id'), nullable=True, index=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey('clients.id'), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    organization = relationship('Organization', back_populates='users')
    client = relationship('Client', back_populates='users')
    client_links = relationship('UserClient', back_populates='user', cascade='all, delete-orphan')
    assigned_clients = relationship('Client', secondary='user_clients', viewonly=True)
    preferences = relationship('UserPreference', back_populates='user', uselist=False, cascade='all, delete-orphan')

    @property
    def client_ids(self) -> list[int]:
        ids = [link.client_id for link in self.client_links]
        if self.client_id is not None and self.client_id not in ids:
            ids.append(self.client_id)
        return sorted(set(ids))
