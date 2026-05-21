from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.search import Search
from app.services.search_states import archive_stale_deactivated_searches


def run_scheduled_maintenance(db: Session) -> dict:
    archived = archive_stale_deactivated_searches(db)
    return {
        "archived_deactivated_searches": archived,
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }


def touch_search_activity(db: Session, search: Search) -> None:
    search.updated_at = datetime.now(timezone.utc)
    db.add(search)
