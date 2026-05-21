from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.alert_log import AlertLog
from app.models.candidate import Candidate
from app.models.candidate_outreach import CandidateOutreach
from app.models.client import Client
from app.models.hub import MeetingIntegration
from app.models.search import Search
from app.models.user import User
from app.services.notifications import notify_user
from app.services.user_preferences import get_or_create_preferences


def _recent_alert_exists(db: Session, event_type: str, *, search_id: int | None = None, client_id: int | None = None, hours: int = 24) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    query = db.query(AlertLog).filter(AlertLog.event_type == event_type, AlertLog.created_at >= cutoff)
    if search_id is not None:
        query = query.filter(AlertLog.search_id == search_id)
    if client_id is not None:
        query = query.filter(AlertLog.client_id == client_id)
    return query.first() is not None


def run_alert_checks(db: Session) -> dict:
    counts = {
        "search_stale": 0,
        "candidate_no_response": 0,
        "search_due_soon": 0,
        "client_inactive": 0,
        "integration_error": 0,
    }
    now = datetime.now(timezone.utc)

    searches = db.query(Search).filter(Search.archived_at.is_(None)).all()
    for search in searches:
        prefs_user = None
        if search.assigned_talent_user_id:
            prefs_user = db.get(User, search.assigned_talent_user_id)
        stale_days = search.alert_stale_days or (get_or_create_preferences(db, prefs_user.id).default_stale_search_days if prefs_user else 14)
        last_activity = search.updated_at or search.created_at
        if last_activity and (now - last_activity.replace(tzinfo=timezone.utc if last_activity.tzinfo is None else last_activity.tzinfo)) >= timedelta(days=stale_days):
            if not _recent_alert_exists(db, "search_stale", search_id=search.id):
                users = []
                if search.assigned_talent_user_id:
                    user = db.get(User, search.assigned_talent_user_id)
                    if user:
                        users.append(user)
                for user in users:
                    if notify_user(
                        db,
                        user,
                        event_type="search_stale",
                        title="Búsqueda sin movimiento",
                        message=f'La búsqueda "{search.title}" superó {stale_days} días sin actividad.',
                        metadata={"search_id": search.id, "search_title": search.title},
                        client_id=search.client_id,
                        search_id=search.id,
                    ):
                        counts["search_stale"] += 1

        if search.manual_state == "desactivada" and search.deactivated_at:
            if (now - search.deactivated_at.replace(tzinfo=timezone.utc if search.deactivated_at.tzinfo is None else search.deactivated_at.tzinfo)) >= timedelta(days=25):
                if not _recent_alert_exists(db, "search_due_soon", search_id=search.id):
                    commercial_users = db.query(User).filter(User.role == "COMERCIAL", User.is_active.is_(True)).all()
                    for user in commercial_users:
                        if notify_user(
                            db,
                            user,
                            event_type="search_due_soon",
                            title="Búsqueda próxima a archivarse",
                            message=f'La búsqueda "{search.title}" lleva más de 25 días desactivada.',
                            metadata={"search_id": search.id},
                            client_id=search.client_id,
                            search_id=search.id,
                        ):
                            counts["search_due_soon"] += 1

    candidates = db.query(Candidate).filter(Candidate.archived_at.is_(None), Candidate.search_id.isnot(None)).all()
    for candidate in candidates:
        search = db.get(Search, candidate.search_id)
        if not search:
            continue
        no_response_days = search.alert_no_response_days or 7
        last_outreach = (
            db.query(CandidateOutreach)
            .filter(CandidateOutreach.candidate_id == candidate.id)
            .order_by(CandidateOutreach.created_at.desc())
            .first()
        )
        if not last_outreach or last_outreach.status != "sent":
            continue
        sent_at = last_outreach.sent_at or last_outreach.created_at
        if not sent_at:
            continue
        sent_at = sent_at.replace(tzinfo=timezone.utc if sent_at.tzinfo is None else sent_at.tzinfo)
        if now - sent_at < timedelta(days=no_response_days):
            continue
        if _recent_alert_exists(db, "candidate_no_response", search_id=search.id):
            continue
        user = db.get(User, search.assigned_talent_user_id) if search.assigned_talent_user_id else None
        if user and notify_user(
            db,
            user,
            event_type="candidate_no_response",
            title="Candidato sin respuesta",
            message=f"{candidate.full_name} no respondió en {no_response_days} días.",
            metadata={"candidate_id": candidate.id, "search_id": search.id},
            client_id=search.client_id,
            search_id=search.id,
            candidate_id=candidate.id,
        ):
            counts["candidate_no_response"] += 1

    clients = db.query(Client).filter(Client.status == "active").all()
    for client in clients:
        recent_search = (
            db.query(Search)
            .filter(Search.client_id == client.id, Search.archived_at.is_(None))
            .order_by(Search.updated_at.desc(), Search.created_at.desc())
            .first()
        )
        last_touch = None
        if recent_search:
            last_touch = recent_search.updated_at or recent_search.created_at
        if last_touch:
            last_touch = last_touch.replace(tzinfo=timezone.utc if last_touch.tzinfo is None else last_touch.tzinfo)
        inactive_days = 60
        if last_touch and now - last_touch >= timedelta(days=inactive_days):
            if not _recent_alert_exists(db, "client_inactive", client_id=client.id, hours=168):
                admins = db.query(User).filter(User.role.in_(["COMERCIAL", "SUPERADMIN"]), User.is_active.is_(True)).all()
                for user in admins:
                    if notify_user(
                        db,
                        user,
                        event_type="client_inactive",
                        title="Cliente sin actividad",
                        message=f'El cliente "{client.name}" no tiene búsquedas activas recientes.',
                        metadata={"client_id": client.id},
                        client_id=client.id,
                    ):
                        counts["client_inactive"] += 1

    broken = db.query(MeetingIntegration).filter(MeetingIntegration.is_active.is_(True), MeetingIntegration.last_error.isnot(None)).all()
    for integration in broken:
        if _recent_alert_exists(db, "integration_error", hours=12):
            continue
        admins = db.query(User).filter(User.role == "SUPERADMIN", User.is_active.is_(True)).all()
        for user in admins:
            if notify_user(
                db,
                user,
                event_type="integration_error",
                title="Error en integración",
                message=f"Falla en {integration.provider}: {integration.last_error}",
                metadata={"provider": integration.provider},
            ):
                counts["integration_error"] += 1

    return counts
