from datetime import datetime

from pydantic import BaseModel, Field


class SearchCandidateAnalysisOut(BaseModel):
    candidate_id: int
    search_id: int
    candidate_name: str
    match_score: float | None = None
    recommendation_level: str | None = None
    summary: str | None = None
    reasons: list[str] = []
    provider_model: str | None = None
    last_analyzed_at: str | None = None
    search_specific: bool = True


class SearchCandidateAnalysesOut(BaseModel):
    search_id: int
    items: list[SearchCandidateAnalysisOut] = []


class MailDraftRequest(BaseModel):
    kind: str
    candidate_id: int
    search_id: int | None = None
    extra_context: str | None = None
    reason: str | None = None


class MailDraftOut(BaseModel):
    subject: str
    body: str
    kind: str


class MailSendRequest(BaseModel):
    kind: str
    candidate_id: int
    search_id: int | None = None
    subject: str
    body: str


class CandidateOutreachOut(BaseModel):
    id: int
    candidate_id: int
    search_id: int | None = None
    kind: str
    subject: str
    body: str
    status: str
    sent_by_user_id: int | None = None
    created_at: str | None = None
    sent_at: str | None = None
    mail_sent_via: str | None = None
    mail_delivery_detail: str | None = None


class CandidateReplyOut(BaseModel):
    status: str
    candidate_id: int
    search_id: int | None = None
    next_status: str | None = None


class CandidateNoteCreate(BaseModel):
    body: str
    visible_roles: list[str] = []
    visible_user_ids: list[int] = []


class CandidateNoteUpdate(BaseModel):
    body: str | None = None
    visible_roles: list[str] | None = None
    visible_user_ids: list[int] | None = None


class CandidateNoteOut(BaseModel):
    id: int
    candidate_id: int
    author_user_id: int
    author_name: str | None = None
    body: str
    visible_roles: list[str] = []
    visible_user_ids: list[int] = []
    created_at: str | None = None
    updated_at: str | None = None


class GoogleCalendarStatusOut(BaseModel):
    connected: bool = False
    google_email: str | None = None
    expires_at: str | None = None
    gmail_send_enabled: bool = False
    oauth_configured: bool = False
    can_send_mail: bool = False


class InterviewProposalRequest(BaseModel):
    candidate_id: int
    search_id: int
    title: str
    notes: str | None = None
    meeting_url: str | None = None
    slot_options: list[dict] = Field(default_factory=list)
    email_body_override: str | None = None  # si se envía, se usa como cuerpo editable; el backend adjunta horarios y links


class InterviewProposalChoiceRequest(BaseModel):
    selected_start_datetime: datetime | None = None
    selected_end_datetime: datetime | None = None
    accepted: bool = True


class TranscriptUpsertRequest(BaseModel):
    interview_id: int
    candidate_id: int
    source_type: str = "manual_text"
    content: str


class TranscriptOut(BaseModel):
    id: int
    interview_id: int
    candidate_id: int
    source_type: str
    content: str
    created_by: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


class CvHtmlOut(BaseModel):
    candidate_id: int
    file_name: str | None = None
    html: str | None = None
    source_type: str
