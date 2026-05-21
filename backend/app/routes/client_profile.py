from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_roles
from app.db.session import get_db
from app.models.client import Client
from app.models.client_profile import ClientContact, ClientProfile
from app.models.feedback import Feedback
from app.models.candidate import Candidate
from app.models.search import Search
from app.services.user_clients import require_client_access

router = APIRouter(prefix="/clients", tags=["client-profile"])


class ClientProfileUpdate(BaseModel):
    industry: str | None = None
    company_size: str | None = None
    culture: str | None = None
    benefits: str | None = None
    work_mode: str | None = None
    tech_stack: list[str] = Field(default_factory=list)
    frequent_requirements: list[str] = Field(default_factory=list)
    internal_notes: str | None = None


class ClientContactIn(BaseModel):
    full_name: str
    role_title: str | None = None
    email: str | None = None
    phone: str | None = None
    is_primary: bool = False


def _serialize_profile(profile: ClientProfile | None, contacts: list[ClientContact]) -> dict:
    return {
        "industry": profile.industry if profile else None,
        "company_size": profile.company_size if profile else None,
        "culture": profile.culture if profile else None,
        "benefits": profile.benefits if profile else None,
        "work_mode": profile.work_mode if profile else None,
        "tech_stack": (profile.tech_stack_json if profile else None) or [],
        "frequent_requirements": (profile.frequent_requirements_json if profile else None) or [],
        "internal_notes": profile.internal_notes if profile else None,
        "contacts": [
            {
                "id": c.id,
                "full_name": c.full_name,
                "role_title": c.role_title,
                "email": c.email,
                "phone": c.phone,
                "is_primary": c.is_primary,
            }
            for c in contacts
        ],
    }


@router.get("/{client_id}/profile", dependencies=[Depends(require_roles("TALENT", "COMERCIAL", "SUPERADMIN"))])
def get_client_profile(client_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    require_client_access(user, client_id, db)
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    profile = db.query(ClientProfile).filter(ClientProfile.client_id == client_id).first()
    contacts = db.query(ClientContact).filter(ClientContact.client_id == client_id).order_by(ClientContact.is_primary.desc(), ClientContact.id).all()
    closed = (
        db.query(Search)
        .filter(Search.client_id == client_id, Search.archived_at.isnot(None))
        .order_by(Search.archived_at.desc())
        .limit(20)
        .all()
    )
    return {
        "client_id": client_id,
        "client_name": client.name,
        "profile": _serialize_profile(profile, contacts),
        "search_history": [
            {
                "id": s.id,
                "title": s.title,
                "closed_at": (s.closed_at or s.archived_at).isoformat() if (s.closed_at or s.archived_at) else None,
                "placed_candidate_id": s.placed_candidate_id,
            }
            for s in closed
        ],
    }


@router.patch("/{client_id}/profile", dependencies=[Depends(require_roles("TALENT", "COMERCIAL", "SUPERADMIN"))])
def update_client_profile(client_id: int, payload: ClientProfileUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    require_client_access(user, client_id, db)
    profile = db.query(ClientProfile).filter(ClientProfile.client_id == client_id).first()
    if not profile:
        profile = ClientProfile(client_id=client_id)
    data = payload.model_dump(exclude_unset=True)
    for field in ("industry", "company_size", "culture", "benefits", "work_mode", "internal_notes"):
        if field in data:
            setattr(profile, field, data[field])
    if "tech_stack" in data:
        profile.tech_stack_json = data["tech_stack"]
    if "frequent_requirements" in data:
        profile.frequent_requirements_json = data["frequent_requirements"]
    profile.updated_at = datetime.now(timezone.utc)
    db.add(profile)
    db.commit()
    contacts = db.query(ClientContact).filter(ClientContact.client_id == client_id).all()
    return _serialize_profile(profile, contacts)


@router.post("/{client_id}/contacts", dependencies=[Depends(require_roles("TALENT", "COMERCIAL", "SUPERADMIN"))])
def create_client_contact(client_id: int, payload: ClientContactIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    require_client_access(user, client_id, db)
    if payload.is_primary:
        db.query(ClientContact).filter(ClientContact.client_id == client_id).update({"is_primary": False})
    row = ClientContact(
        client_id=client_id,
        full_name=payload.full_name.strip(),
        role_title=(payload.role_title or "").strip() or None,
        email=(payload.email or "").strip() or None,
        phone=(payload.phone or "").strip() or None,
        is_primary=payload.is_primary,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "full_name": row.full_name, "is_primary": row.is_primary}


@router.delete("/{client_id}/contacts/{contact_id}", dependencies=[Depends(require_roles("TALENT", "COMERCIAL", "SUPERADMIN"))])
def delete_client_contact(client_id: int, contact_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    require_client_access(user, client_id, db)
    row = db.get(ClientContact, contact_id)
    if not row or row.client_id != client_id:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(row)
    db.commit()
    return {"status": "ok"}
