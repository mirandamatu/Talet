from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserClient(Base):
    __tablename__ = 'user_clients'
    __table_args__ = (UniqueConstraint('user_id', 'client_id', name='uq_user_clients_user_client'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey('clients.id', ondelete='CASCADE'), nullable=False, index=True)

    user = relationship('User', back_populates='client_links')
    client = relationship('Client', back_populates='user_links')
