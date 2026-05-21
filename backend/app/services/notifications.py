import json
from datetime import datetime, timezone

from sqlalchemy import or_

from sqlalchemy.orm import Session

from app.models.alert_log import AlertLog
from app.models.notification_log import NotificationLog
from app.models.calendar_event import CalendarEvent
from app.models.user import User
from app.services.email import send_email as deliver_email
from app.services.user_clients import can_access_client
from app.services.user_preferences import is_notification_enabled


def _build_payload(
    event_type: str,
    title: str,
    message: str,
    metadata: dict | None = None,
) -> dict:
    return {
        "event_type": event_type,
        "title": title,
        "message": message,
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def notify_user(
    db: Session,
    user: User,
    *,
    event_type: str,
    title: str,
    message: str,
    metadata: dict | None = None,
    client_id: int | None = None,
    search_id: int | None = None,
    candidate_id: int | None = None,
    also_email: bool = True,
) -> bool:
    if not user.is_active:
        return False
    if not is_notification_enabled(db, user.id, event_type):
        return False

    payload = _build_payload(event_type=event_type, title=title, message=message, metadata=metadata)
    db.add(
        NotificationLog(
            type="event",
            to_email=user.email,
            status="unread",
            error=json.dumps(payload, ensure_ascii=False),
        )
    )
    delivered_email = False
    if also_email:
        result = deliver_email(db, user.email, title, message)
        delivered_email = result.get("status") == "sent"

    db.add(
        AlertLog(
            event_type=event_type,
            user_id=user.id,
            client_id=client_id,
            search_id=search_id,
            candidate_id=candidate_id,
            title=title,
            message=message,
            metadata_json=metadata or {},
            delivered_app=True,
            delivered_email=delivered_email,
        )
    )
    db.commit()
    return True


def notify_users(
    db: Session,
    users: list[User],
    *,
    event_type: str,
    title: str,
    message: str,
    metadata: dict | None = None,
    client_id: int | None = None,
    search_id: int | None = None,
    candidate_id: int | None = None,
) -> int:
    count = 0
    for user in users:
        if notify_user(
            db,
            user,
            event_type=event_type,
            title=title,
            message=message,
            metadata=metadata,
            client_id=client_id,
            search_id=search_id,
            candidate_id=candidate_id,
        ):
            count += 1
    return count


def create_event_notifications_for_roles(
    db: Session,
    *,
    client_id: int,
    roles: list[str],
    event_type: str,
    title: str,
    message: str,
    metadata: dict | None = None,
) -> int:
    users = (
        db.query(User)
        .filter(User.role.in_(roles), User.is_active.is_(True))
        .all()
    )
    count = 0
    for user in users:
        if not can_access_client(user, client_id, db):
            continue
        payload = _build_payload(event_type=event_type, title=title, message=message, metadata=metadata)
        db.add(
            NotificationLog(
                type="event",
                to_email=user.email,
                status="unread",
                error=json.dumps(payload, ensure_ascii=False),
            )
        )
        count += 1
    if count > 0:
        db.commit()
    return count


def create_event_notifications_for_user_ids(
    db: Session,
    *,
    user_ids: list[int],
    event_type: str,
    title: str,
    message: str,
    metadata: dict | None = None,
) -> int:
    if not user_ids:
        return 0
    users = (
        db.query(User)
        .filter(User.id.in_(sorted(set(user_ids))), User.is_active.is_(True))
        .all()
    )
    count = 0
    for user in users:
        payload = _build_payload(event_type=event_type, title=title, message=message, metadata=metadata)
        db.add(
            NotificationLog(
                type="event",
                to_email=user.email,
                status="unread",
                error=json.dumps(payload, ensure_ascii=False),
            )
        )
        count += 1
    if count > 0:
        db.commit()
    return count


def list_event_notifications_for_user(db: Session, user_email: str) -> list[dict]:
    user = db.query(User).filter(User.email == user_email).first()
    if user:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        client_ids = user.client_ids
        query = db.query(CalendarEvent).filter(CalendarEvent.start_datetime >= now)
        if user.role != 'SUPERADMIN':
            query = query.filter(or_(
                CalendarEvent.created_by == user.id,
                CalendarEvent.client_id.in_(client_ids),
                CalendarEvent.role_scope == user.role,
            ))
        due_events = [
            event for event in query.order_by(CalendarEvent.start_datetime).all()
            if 0 <= (event.start_datetime - now).total_seconds() / 3600 <= 24
        ]
        if user.role != 'SUPERADMIN':
            invited_due = [
                event for event in db.query(CalendarEvent).filter(CalendarEvent.start_datetime >= now).order_by(CalendarEvent.start_datetime).all()
                if user.id in (event.invited_user_ids_json or []) and 0 <= (event.start_datetime - now).total_seconds() / 3600 <= 24
            ]
            due_by_id = {event.id: event for event in due_events}
            for event in invited_due:
                due_by_id[event.id] = event
            due_events = list(due_by_id.values())
        created = 0
        for event in due_events:
            exists = (
                db.query(NotificationLog)
                .filter(
                    NotificationLog.type == "event",
                    NotificationLog.to_email == user_email,
                    NotificationLog.error.contains('"event_type": "calendar_event_reminder"'),
                    NotificationLog.error.contains(f'"event_id": {event.id}'),
                )
                .first()
            )
            if exists:
                continue
            payload = _build_payload(
                event_type="calendar_event_reminder",
                title="Recordatorio de calendario",
                message=f'El evento "{event.title}" empieza el {event.start_datetime.strftime("%d/%m/%Y %H:%M")}.',
                metadata={"event_id": event.id, "event_title": event.title, "start_datetime": event.start_datetime.isoformat()},
            )
            db.add(NotificationLog(type="event", to_email=user_email, status="unread", retries=0, error=json.dumps(payload, ensure_ascii=False)))
            created += 1
        if created:
            db.commit()

    rows = (
        db.query(NotificationLog)
        .filter(NotificationLog.type == "event", NotificationLog.to_email == user_email, NotificationLog.status != "archived")
        .order_by(NotificationLog.id.desc())
        .all()
    )
    out: list[dict] = []
    for row in rows:
        payload = {}
        try:
            payload = json.loads(row.error) if row.error else {}
        except Exception:
            payload = {}
        out.append(
            {
                "id": row.id,
                "status": row.status,
                "event_type": payload.get("event_type") or row.type,
                "title": payload.get("title") or "Notificación",
                "message": payload.get("message") or "",
                "metadata": payload.get("metadata") or {},
                "created_at": payload.get("created_at") or (row.created_at.isoformat() if row.created_at else None),
            }
        )
    return out


def mark_notifications_read(db: Session, user_email: str) -> int:
    rows = (
        db.query(NotificationLog)
        .filter(NotificationLog.type == "event", NotificationLog.to_email == user_email, NotificationLog.status == "unread")
        .all()
    )
    for row in rows:
        row.status = "read"
        db.add(row)
    if rows:
        db.commit()
    return len(rows)


def mark_notifications_read_by_ids(db: Session, user_email: str, ids: list[int]) -> int:
    if not ids:
        return 0
    rows = (
        db.query(NotificationLog)
        .filter(
            NotificationLog.type == "event",
            NotificationLog.to_email == user_email,
            NotificationLog.status == "unread",
            NotificationLog.id.in_(sorted(set(ids))),
        )
        .all()
    )
    for row in rows:
        row.status = "read"
        db.add(row)
    if rows:
        db.commit()
    return len(rows)


def archive_notifications(db: Session, user_email: str, ids: list[int]) -> int:
    if not ids:
        return 0
    rows = (
        db.query(NotificationLog)
        .filter(NotificationLog.type == "event", NotificationLog.to_email == user_email, NotificationLog.id.in_(ids))
        .all()
    )
    for row in rows:
        row.status = "archived"
        db.add(row)
    if rows:
        db.commit()
    return len(rows)
