from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.hub import MeetingIntegration
from app.models.interview import Interview
from app.models.interview_transcript import InterviewTranscript

router = APIRouter(prefix="/integrations", tags=["integrations"])


class TranscriptWebhookPayload(BaseModel):
    interview_id: int
    candidate_id: int
    meeting_id: str | None = None
    transcript: str
    source_type: str | None = None


def _store_transcript(db: Session, *, provider: str, payload: TranscriptWebhookPayload) -> dict:
    transcript = (payload.transcript or "").strip()
    if len(transcript) < 20:
        raise HTTPException(status_code=400, detail="Transcript too short")
    interview = db.get(Interview, payload.interview_id)
    if not interview or interview.candidate_id != payload.candidate_id:
        raise HTTPException(status_code=404, detail="Interview not found")
    source_type = payload.source_type or provider
    row = (
        db.query(InterviewTranscript)
        .filter(InterviewTranscript.interview_id == interview.id, InterviewTranscript.source_type == source_type)
        .first()
    )
    if not row:
        row = InterviewTranscript(
            interview_id=interview.id,
            candidate_id=payload.candidate_id,
            source_type=source_type,
            content=transcript,
            created_by=None,
        )
    else:
        row.content = transcript
        row.updated_at = datetime.now(timezone.utc)
    db.add(row)
    integration = (
        db.query(MeetingIntegration)
        .filter(MeetingIntegration.provider == provider, MeetingIntegration.is_active.is_(True))
        .first()
    )
    if integration:
        integration.last_error = None
        integration.updated_at = datetime.now(timezone.utc)
        db.add(integration)
    db.commit()
    db.refresh(row)
    return {"status": "ok", "transcript_id": row.id}


@router.post("/zoom/transcript")
def zoom_transcript_webhook(payload: TranscriptWebhookPayload, db: Session = Depends(get_db)):
    return _store_transcript(db, provider="zoom", payload=payload)


@router.post("/meet/transcript")
def meet_transcript_webhook(payload: TranscriptWebhookPayload, db: Session = Depends(get_db)):
    return _store_transcript(db, provider="meet", payload=payload)
