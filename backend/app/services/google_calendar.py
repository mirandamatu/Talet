from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build

from app.core.config import get_settings
from app.models.google_calendar_connection import GoogleCalendarConnection


GOOGLE_CALENDAR_SCOPE = 'https://www.googleapis.com/auth/calendar'
GOOGLE_GMAIL_SEND_SCOPE = 'https://www.googleapis.com/auth/gmail.send'
# Selector de cuenta e identificación del mail (UX estándar OAuth)
GOOGLE_OPENID_SCOPE = 'openid'
GOOGLE_USERINFO_EMAIL_SCOPE = 'https://www.googleapis.com/auth/userinfo.email'


def oauth_scope_string() -> str:
    """Una sola pantalla de consentimiento: calendario + envío Gmail + cuenta."""
    return ' '.join(
        (
            GOOGLE_CALENDAR_SCOPE,
            GOOGLE_GMAIL_SEND_SCOPE,
            GOOGLE_OPENID_SCOPE,
            GOOGLE_USERINFO_EMAIL_SCOPE,
        )
    )


def google_oauth_env_configured() -> bool:
    s = get_settings()
    return bool(s.google_oauth_client_id and s.google_oauth_client_secret and s.google_oauth_redirect_uri)


def connection_oauth_scopes(connection: GoogleCalendarConnection) -> list[str]:
    raw = (connection.scope or '').strip()
    if raw:
        parts = [p for p in raw.split() if p]
        return parts if parts else [GOOGLE_CALENDAR_SCOPE]
    return [GOOGLE_CALENDAR_SCOPE]


def build_google_oauth_url(*, state: str, force_consent: bool = True) -> str:
    settings = get_settings()
    params = {
        'client_id': settings.google_oauth_client_id or '',
        'redirect_uri': settings.google_oauth_redirect_uri or '',
        'response_type': 'code',
        'access_type': 'offline',
        'prompt': 'consent' if force_consent else 'select_account',
        'include_granted_scopes': 'true',
        'scope': oauth_scope_string(),
        'state': state,
    }
    return f'https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}'


def connection_to_credentials(connection: GoogleCalendarConnection) -> Credentials | None:
    settings = get_settings()
    if not connection.access_token:
        return None
    scope_list = connection_oauth_scopes(connection)
    creds = Credentials(
        token=connection.access_token,
        refresh_token=connection.refresh_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        scopes=scope_list,
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())
        connection.access_token = creds.token
        connection.expires_at = creds.expiry
    return creds


def create_calendar_event(
    *,
    connection: GoogleCalendarConnection,
    summary: str,
    description: str,
    start_dt: datetime,
    end_dt: datetime,
    attendee_emails: list[str],
) -> dict | None:
    creds = connection_to_credentials(connection)
    if not creds:
        return None
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    payload = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_dt.astimezone(timezone.utc).isoformat()},
        "end": {"dateTime": end_dt.astimezone(timezone.utc).isoformat()},
        "attendees": [{"email": email} for email in attendee_emails if email],
    }
    return service.events().insert(calendarId="primary", body=payload, sendUpdates="all").execute()
