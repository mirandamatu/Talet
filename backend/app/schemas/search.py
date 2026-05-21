from pydantic import BaseModel


class SearchDocumentOut(BaseModel):
    id: int
    search_id: int
    kind: str
    file_name: str
    file_url: str
    content_type: str | None = None
    extracted_text: str | None = None
    created_at: str | None = None


class SearchAIQuestionOut(BaseModel):
    id: int
    search_id: int
    question: str
    answer: str | None = None
    status: str


class SearchCreate(BaseModel):
    client_id: int
    title: str
    job_description: str
    contact_name: str | None = None
    contact_email: str | None = None


class SearchUpdate(BaseModel):
    title: str | None = None
    job_description: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    manual_state: str | None = None


class SearchOut(BaseModel):
    id: int
    client_id: int
    title: str
    job_description: str
    contact_name: str | None
    contact_email: str | None
    archived_at: str | None = None
    search_state: str | None = None
    manual_state: str | None = None
    candidate_count: int = 0
    active_candidate_count: int = 0
    documents: list[SearchDocumentOut] = []
    ai_question_items: list[SearchAIQuestionOut] = []
    ai_questions: list[str] = []
    ai_questions_summary: str | None = None
    ai_questions_needs_follow_up: bool = False

    class Config:
        from_attributes = True
