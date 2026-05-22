"""Helpers for organization-scoped access."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.client import Client
from app.models.search import Search
from app.models.user import User


def require_organization_id(user: User) -> int:
    oid = user.organization_id
    if oid is None:
        raise HTTPException(status_code=403, detail="Organization required for this account")
    return oid


def get_client_organization_id(db: Session, client_id: int) -> int | None:
    c = db.get(Client, client_id)
    return c.organization_id if c else None


def get_search_organization_id(db: Session, search_id: int) -> int | None:
    s = db.get(Search, search_id)
    if not s:
        return None
    return get_client_organization_id(db, s.client_id)


def get_candidate_organization_id(db: Session, candidate: Candidate) -> int | None:
    if candidate.search_id is not None:
        return get_search_organization_id(db, candidate.search_id)
    if candidate.client_id is not None:
        return get_client_organization_id(db, candidate.client_id)
    from app.models.candidate_search_assignment import CandidateSearchAssignment

    assignment = (
        db.query(CandidateSearchAssignment)
        .filter(CandidateSearchAssignment.candidate_id == candidate.id, CandidateSearchAssignment.archived_at.is_(None))
        .first()
    )
    if assignment:
        return get_search_organization_id(db, assignment.search_id)
    return None


def ensure_same_organization(user: User, organization_id: int | None) -> None:
    expected = require_organization_id(user)
    if organization_id is None or organization_id != expected:
        raise HTTPException(status_code=404, detail="Not found")


def ensure_candidate_in_organization(db: Session, user: User, candidate: Candidate) -> None:
    oid = get_candidate_organization_id(db, candidate)
    ensure_same_organization(user, oid)
