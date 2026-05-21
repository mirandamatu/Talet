from pydantic import BaseModel


class FeedbackCreate(BaseModel):
    stage: str
    main_reason: str
    ratings_json: dict | None = None
    comment: str | None = None
