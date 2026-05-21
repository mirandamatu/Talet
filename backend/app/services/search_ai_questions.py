from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.search_ai_question import SearchAIQuestion


def replace_search_ai_questions(db: Session, search_id: int, questions: list[str], created_by: int | None = None) -> None:
    db.query(SearchAIQuestion).filter(SearchAIQuestion.search_id == search_id).delete()
    for question in questions[:8]:
        clean = str(question).strip()
        if clean:
            db.add(SearchAIQuestion(search_id=search_id, question=clean, status='pending', created_by=created_by))
    db.commit()
