from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.user import User
from app.models.user_client import UserClient


def get_user_client_ids(user: User) -> list[int]:
    ids = set(user.client_ids)
    return sorted(ids)


def can_access_client(user: User, client_id: int, db: Session) -> bool:
    client = db.get(Client, client_id)
    if not client:
        return False
    if user.organization_id is None or client.organization_id != user.organization_id:
        return False
    if user.role == "SUPERADMIN":
        return True
    return client_id in set(get_user_client_ids(user))


def require_client_access(user: User, client_id: int, db: Session) -> None:
    if not can_access_client(user, client_id, db):
        raise HTTPException(status_code=404, detail="Client not found")


def get_accessible_clients(user: User, db: Session) -> list[Client]:
    if user.organization_id is None:
        return []
    q = db.query(Client).filter(Client.organization_id == user.organization_id)
    if user.role == "SUPERADMIN":
        return q.order_by(Client.id).all()
    ids = get_user_client_ids(user)
    if not ids:
        return []
    return q.filter(Client.id.in_(ids)).order_by(Client.id).all()


def sync_user_clients(db: Session, user: User, client_ids: list[int]) -> list[int]:
    clean_ids = sorted(set(client_ids))
    if clean_ids:
        rows = (
            db.query(Client)
            .filter(Client.id.in_(clean_ids), Client.organization_id == user.organization_id)
            .all()
        )
        existing_ids = {c.id for c in rows}
        missing = [cid for cid in clean_ids if cid not in existing_ids]
        if missing:
            raise HTTPException(status_code=400, detail=f"Invalid client ids: {missing}")

    current_ids = {link.client_id for link in user.client_links}
    wanted_ids = set(clean_ids)
    to_remove = [link for link in user.client_links if link.client_id not in wanted_ids]
    for link in to_remove:
        db.delete(link)
    for cid in wanted_ids - current_ids:
        db.add(UserClient(user_id=user.id, client_id=cid))
    return clean_ids
