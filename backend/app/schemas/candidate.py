from pydantic import BaseModel


class CandidateCreate(BaseModel):
    full_name: str
    short_profile: str | None = None


class CandidateUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    short_profile: str | None = None
    search_id: int | None = None
    status: str | None = None


class CandidateAssignmentCreate(BaseModel):
    search_ids: list[int]
    status: str | None = "en_revision"
    notes: str | None = None


class CandidateAssignmentOut(BaseModel):
    id: int
    candidate_id: int
    search_id: int
    search_title: str | None = None
    client_id: int | None = None
    status: str
    notes: str | None = None
    assigned_by_user_id: int | None = None
    assigned_at: str | None = None
    updated_at: str | None = None
    archived_at: str | None = None


class CandidateBankOut(BaseModel):
    id: int
    full_name: str
    email: str | None = None
    short_profile: str | None = None
    status: str
    created_at: str | None = None
    client_id: int | None = None

    class Config:
        from_attributes = True


class CandidateOut(BaseModel):
    id: int
    search_id: int | None
    full_name: str
    email: str | None = None
    short_profile: str | None
    cv_file_url: str | None
    cv_file_name: str | None = None
    cv_uploaded_at: str | None = None
    status: str
    archived_at: str | None
    discarded_reason: str | None = None
    discarded_comment: str | None = None
    internal_notes: str | None = None
    has_client_feedback: bool = False
    latest_client_feedback_reason: str | None = None
    client_feedback: list[dict] = []
    ai_fit_score: float | None = None
    ai_fit_recommendation: bool | None = None
    ai_fit_summary: str | None = None
    ai_fit_reasons: list[str] = []
    assignment_status: str | None = None
    assignments: list[CandidateAssignmentOut] = []
    is_presented_to_client: bool = False
    presented_at: str | None = None

    class Config:
        from_attributes = True


class CandidateStatusUpdate(BaseModel):
    status: str
    feedback: dict | None = None
