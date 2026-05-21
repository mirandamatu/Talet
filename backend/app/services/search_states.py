from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.search import Search

VALID_MANUAL_STATES = {"abierta", "activa", "desactivada", "eliminada"}
CAREER_PAGE_STATES = {"abierta"}
ARCHIVE_AFTER_DAYS = 30


ACTIVE_SEARCH_CANDIDATE_STATUSES = {
    "en_revision",
    "entrevistado",
    "aprobado",
    "pendiente_entrevista",
    "applied",
}


def normalize_manual_state(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized == "cerrada":
        return "desactivada"
    if normalized in VALID_MANUAL_STATES:
        return normalized
    return None


def get_search_candidate_counts(db: Session, search_id: int) -> dict[str, int]:
    from app.models.candidate import Candidate

    rows = (
        db.query(Candidate)
        .filter(Candidate.search_id == search_id, Candidate.archived_at.is_(None))
        .all()
    )
    candidate_count = len(rows)
    active_candidate_count = sum(1 for row in rows if row.status in ACTIVE_SEARCH_CANDIDATE_STATUSES)
    return {
        "candidate_count": candidate_count,
        "active_candidate_count": active_candidate_count,
    }


def classify_search(search: Search, db: Session) -> str:
    if search.archived_at is not None:
        return "eliminada"
    if search.manual_state == "desactivada":
        return "desactivada"
    if search.manual_state in {"abierta", "activa"}:
        return str(search.manual_state)
    counts = get_search_candidate_counts(db, search.id)
    if counts["active_candidate_count"] > 0:
        return "activa"
    return "abierta"


def apply_manual_state_change(search: Search, new_state: str | None) -> None:
    now = datetime.now(timezone.utc)
    search.manual_state = new_state
    search.updated_at = now
    if new_state == "desactivada":
        search.deactivated_at = now
    elif new_state != "eliminada":
        search.deactivated_at = None
    if new_state == "eliminada":
        search.archived_at = now


def archive_stale_deactivated_searches(db: Session) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=ARCHIVE_AFTER_DAYS)
    rows = (
        db.query(Search)
        .filter(
            Search.manual_state == "desactivada",
            Search.archived_at.is_(None),
            Search.deactivated_at.isnot(None),
            Search.deactivated_at <= cutoff,
        )
        .all()
    )
    count = 0
    for search in rows:
        search.archived_at = datetime.now(timezone.utc)
        search.updated_at = search.archived_at
        db.add(search)
        count += 1
    if count:
        db.commit()
    return count
