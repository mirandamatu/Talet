from pydantic import BaseModel


class AIInterviewAnalysisIn(BaseModel):
    transcript: str
    role_context: str = 'internal_interview'


class AICandidateFitOut(BaseModel):
    candidate_id: int
    search_id: int
    score: float | None = None
    recommendation: bool | None = None
    summary: str | None = None
    reasons: list[str] = []
    model: str | None = None


class AISearchQuestionsOut(BaseModel):
    search_id: int
    needs_follow_up: bool = False
    summary: str | None = None
    questions: list[str] = []
    model: str | None = None


class AIInterviewAnalysisOut(BaseModel):
    interview_id: int
    candidate_id: int
    search_id: int
    fit_score: float | None = None
    recommendation: bool | None = None
    summary: str | None = None
    strengths: list[str] = []
    risks: list[str] = []
    next_steps: list[str] = []
    talent_feedback: str | None = None
    model: str | None = None
