from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.user_preference import UserPreference

DEFAULT_NOTIFICATION_SETTINGS = {
    "new_candidate_application": True,
    "candidate_presented": True,
    "client_feedback_received": True,
    "search_state_changed": True,
    "hub_message_received": True,
    "search_stale": True,
    "candidate_no_response": True,
    "search_due_soon": True,
    "client_inactive": True,
    "integration_error": True,
    "calendar_event_reminder": True,
}

DEFAULT_REMINDER_SETTINGS = {
    "candidate_follow_up": {"enabled": True, "frequency": "weekly"},
    "search_expiry": {"enabled": True, "frequency": "weekly"},
    "hub_tasks": {"enabled": True, "frequency": "daily"},
}


def get_or_create_preferences(db: Session, user_id: int) -> UserPreference:
    row = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    if row:
        return row
    row = UserPreference(
        user_id=user_id,
        notification_settings_json=dict(DEFAULT_NOTIFICATION_SETTINGS),
        reminder_settings_json=dict(DEFAULT_REMINDER_SETTINGS),
        default_stale_search_days=14,
        default_no_response_days=7,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def is_notification_enabled(db: Session, user_id: int, event_type: str) -> bool:
    prefs = get_or_create_preferences(db, user_id)
    settings = prefs.notification_settings_json or DEFAULT_NOTIFICATION_SETTINGS
    return bool(settings.get(event_type, True))


def serialize_preferences(row: UserPreference) -> dict:
    return {
        "notification_settings": row.notification_settings_json or DEFAULT_NOTIFICATION_SETTINGS,
        "reminder_settings": row.reminder_settings_json or DEFAULT_REMINDER_SETTINGS,
        "default_stale_search_days": row.default_stale_search_days,
        "default_no_response_days": row.default_no_response_days,
    }
