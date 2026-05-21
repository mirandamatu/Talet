from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog


def log_activity(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    action: str,
    actor_user_id: int | None = None,
    summary: str | None = None,
    payload_json: dict | None = None,
    commit: bool = True,
) -> ActivityLog:
    row = ActivityLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_user_id=actor_user_id,
        summary=summary,
        payload_json=payload_json or {},
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    return row
