from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_search_assignment import CandidateSearchAssignment
from app.models.search import Search


PROJECT_STATUSES = {"aprobado", "activo", "contratado", "en_proyecto", "trabajando"}
VISIBLE_ASSIGNMENT_STATUSES = {
    "en_revision",
    "entrevistado",
    "aprobado",
    "rechazado",
    "pendiente_entrevista",
    "applied",
    "activo",
    "contratado",
    "en_proyecto",
    "trabajando",
}


def serialize_assignment(row: CandidateSearchAssignment, search: Search | None = None) -> dict:
    search = search or row.search
    return {
        "id": row.id,
        "candidate_id": row.candidate_id,
        "search_id": row.search_id,
        "search_title": search.title if search else None,
        "client_id": search.client_id if search else None,
        "status": row.status,
        "notes": row.notes,
        "assigned_by_user_id": row.assigned_by_user_id,
        "assigned_at": row.assigned_at.isoformat() if row.assigned_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "archived_at": row.archived_at.isoformat() if row.archived_at else None,
    }


def get_assignment(db: Session, candidate_id: int, search_id: int) -> CandidateSearchAssignment | None:
    return (
        db.query(CandidateSearchAssignment)
        .filter(
            CandidateSearchAssignment.candidate_id == candidate_id,
            CandidateSearchAssignment.search_id == search_id,
            CandidateSearchAssignment.archived_at.is_(None),
        )
        .first()
    )


def list_assignments_for_candidate(db: Session, candidate_id: int) -> list[CandidateSearchAssignment]:
    return (
        db.query(CandidateSearchAssignment)
        .filter(
            CandidateSearchAssignment.candidate_id == candidate_id,
            CandidateSearchAssignment.archived_at.is_(None),
        )
        .order_by(CandidateSearchAssignment.id.desc())
        .all()
    )


def list_candidates_for_search(db: Session, search_id: int, include_archived: bool = False) -> list[tuple[Candidate, CandidateSearchAssignment]]:
    q = (
        db.query(Candidate, CandidateSearchAssignment)
        .join(CandidateSearchAssignment, CandidateSearchAssignment.candidate_id == Candidate.id)
        .filter(CandidateSearchAssignment.search_id == search_id)
    )
    if not include_archived:
        q = q.filter(Candidate.archived_at.is_(None), CandidateSearchAssignment.archived_at.is_(None))
    return q.order_by(CandidateSearchAssignment.id.desc(), Candidate.id.desc()).all()


def assign_candidate_to_search(
    db: Session,
    *,
    candidate: Candidate,
    search: Search,
    status: str = "en_revision",
    assigned_by_user_id: int | None = None,
    notes: str | None = None,
) -> CandidateSearchAssignment:
    row = (
        db.query(CandidateSearchAssignment)
        .filter(
            CandidateSearchAssignment.candidate_id == candidate.id,
            CandidateSearchAssignment.search_id == search.id,
        )
        .first()
    )
    now = datetime.now(timezone.utc)
    if row:
        row.status = status or row.status or "en_revision"
        row.notes = notes if notes is not None else row.notes
        row.assigned_by_user_id = assigned_by_user_id or row.assigned_by_user_id
        row.updated_at = now
        row.archived_at = None
    else:
        row = CandidateSearchAssignment(
            candidate_id=candidate.id,
            search_id=search.id,
            status=status or "en_revision",
            notes=notes,
            assigned_by_user_id=assigned_by_user_id,
            assigned_at=now,
            updated_at=now,
        )
    if candidate.client_id is None:
        candidate.client_id = search.client_id
    # Primary search_id is kept for legacy routes; assignments are the source of truth.
    if candidate.search_id is None:
        candidate.search_id = search.id
    if candidate.status in {None, "", "banco_talent", "banco_no_activo", "en_banca"}:
        candidate.status = row.status
    db.add(candidate)
    db.add(row)
    db.commit()
    db.refresh(row)
    db.refresh(candidate)
    return row


def sync_assignment_status(db: Session, candidate_id: int, search_id: int | None, status: str) -> None:
    if search_id is None:
        return
    row = get_assignment(db, candidate_id, search_id)
    if not row:
        return
    row.status = status
    row.updated_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()


def candidate_has_project_assignment(db: Session, candidate_id: int) -> bool:
    return (
        db.query(CandidateSearchAssignment.id)
        .filter(
            CandidateSearchAssignment.candidate_id == candidate_id,
            CandidateSearchAssignment.archived_at.is_(None),
            CandidateSearchAssignment.status.in_(PROJECT_STATUSES),
        )
        .first()
        is not None
    )
