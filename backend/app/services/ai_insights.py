from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.ai_insight import AIInsight


def create_ai_insight(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    kind: str,
    score: float | None = None,
    recommendation: bool | None = None,
    summary: str | None = None,
    payload_json: dict[str, Any] | None = None,
    created_by: int | None = None,
    commit: bool = True,
) -> AIInsight:
    insight = AIInsight(
        entity_type=entity_type,
        entity_id=entity_id,
        kind=kind,
        score=score,
        recommendation=recommendation,
        summary=summary,
        payload_json=payload_json or {},
        created_by=created_by,
    )
    db.add(insight)
    if commit:
        db.commit()
        db.refresh(insight)
    return insight


def get_latest_ai_insight(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    kind: str,
) -> AIInsight | None:
    return (
        db.query(AIInsight)
        .filter(
            AIInsight.entity_type == entity_type,
            AIInsight.entity_id == entity_id,
            AIInsight.kind == kind,
        )
        .order_by(AIInsight.created_at.desc(), AIInsight.id.desc())
        .first()
    )


def get_candidate_fit_fields(db: Session, candidate_id: int) -> dict[str, Any]:
    insight = get_latest_ai_insight(
        db,
        entity_type='candidate',
        entity_id=candidate_id,
        kind='candidate_fit',
    )
    if not insight:
        return {
            'ai_fit_score': None,
            'ai_fit_recommendation': None,
            'ai_fit_summary': None,
            'ai_fit_reasons': [],
        }
    payload = insight.payload_json or {}
    return {
        'ai_fit_score': insight.score,
        'ai_fit_recommendation': insight.recommendation,
        'ai_fit_summary': insight.summary,
        'ai_fit_reasons': payload.get('reasons', []),
    }


def get_search_questions_fields(db: Session, search_id: int) -> dict[str, Any]:
    insight = get_latest_ai_insight(
        db,
        entity_type='search',
        entity_id=search_id,
        kind='search_questions',
    )
    if not insight:
        return {
            'ai_questions': [],
            'ai_questions_summary': None,
            'ai_questions_needs_follow_up': False,
        }
    payload = insight.payload_json or {}
    questions = payload.get('questions') or []
    return {
        'ai_questions': questions,
        'ai_questions_summary': insight.summary,
        'ai_questions_needs_follow_up': bool(payload.get('needs_follow_up')),
    }
