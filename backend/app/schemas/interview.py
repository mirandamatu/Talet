from pydantic import BaseModel


class InterviewCreate(BaseModel):
    slot_id: int


class InterviewOut(BaseModel):
    id: int
    candidate_id: int
    slot_id: int
    calendar_event_id: int | None = None
    status: str

    class Config:
        from_attributes = True
