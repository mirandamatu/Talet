from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.search import Search
from app.models.search_candidate_analysis import SearchCandidateAnalysis
from app.services.ai_engine import analyze_candidate_fit, extract_docx_text, extract_pdf_text
from app.services.ai_notes import create_pinned_ai_note
from app.services.client_context import build_client_context


def _candidate_text(candidate: Candidate) -> str:
    if not candidate.cv_file_url or not candidate.cv_file_url.startswith("/uploads/"):
        return ""
    full_path = Path(__file__).resolve().parents[2] / candidate.cv_file_url.lstrip("/")
    if not full_path.exists():
        return ""
    raw = full_path.read_bytes()
    name = (candidate.cv_file_name or "").lower()
    if name.endswith(".docx"):
        return extract_docx_text(raw)
    return extract_pdf_text(raw)


def build_analysis_source_hash(search: Search, candidate: Candidate) -> str:
    parts = [
        str(search.id),
        search.title or "",
        search.job_description or "",
        str(candidate.id),
        candidate.full_name or "",
        candidate.short_profile or "",
        candidate.cv_file_name or "",
        candidate.cv_file_url or "",
        candidate.cv_uploaded_at.isoformat() if candidate.cv_uploaded_at else "",
        candidate.status or "",
    ]
    return hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()


def recommendation_level_from_score(score: float | None) -> str:
    numeric = float(score or 0)
    if numeric >= 7:
        return "alto"
    if numeric >= 5:
        return "medio"
    return "bajo"


def serialize_analysis(row: SearchCandidateAnalysis, candidate_name: str) -> dict:
    score_10 = float(row.match_score or 0)
    return {
        "candidate_id": row.candidate_id,
        "search_id": row.search_id,
        "candidate_name": candidate_name,
        "match_score": row.match_score,
        "score_10": row.match_score,
        "match_percentage": round(score_10 * 10),
        "recommendation_level": row.recommendation_level,
        "summary": row.summary,
        "reasons": row.reasons_json or [],
        "provider_model": row.model_name,
        "last_analyzed_at": row.last_analyzed_at.isoformat() if row.last_analyzed_at else None,
        "search_specific": True,
    }


def upsert_search_candidate_analysis(
    db: Session,
    *,
    search: Search,
    candidate: Candidate,
    created_by: int | None = None,
    persist_note: bool = True,
) -> SearchCandidateAnalysis:
    source_hash = build_analysis_source_hash(search, candidate)
    existing = (
        db.query(SearchCandidateAnalysis)
        .filter(
            SearchCandidateAnalysis.search_id == search.id,
            SearchCandidateAnalysis.candidate_id == candidate.id,
        )
        .first()
    )
    if existing and existing.source_hash == source_hash:
        return existing

    client_context = build_client_context(db, search.client_id)
    fit = analyze_candidate_fit(
        search_title=search.title,
        job_description=search.job_description,
        candidate_name=candidate.full_name,
        short_profile=candidate.short_profile,
        cv_text=_candidate_text(candidate),
        client_context=client_context,
    )
    score_10 = float(fit.get("score_10") or fit.get("score") or 0)
    row = existing or SearchCandidateAnalysis(search_id=search.id, candidate_id=candidate.id)
    row.match_score = score_10
    row.recommendation_level = recommendation_level_from_score(score_10)
    row.summary = fit.get("summary")
    row.reasons_json = fit.get("reasons") or fit.get("strengths") or []
    row.source_hash = source_hash
    row.model_name = fit.get("model")
    row.last_analyzed_at = datetime.now(timezone.utc)
    row.created_by = created_by
    db.add(row)
    db.commit()
    db.refresh(row)

    if persist_note:
        note_body = (
            f"Análisis IA CV — Score {score_10}/10\n"
            f"{fit.get('summary') or ''}\n"
            f"Fortalezas: {', '.join(fit.get('strengths') or fit.get('reasons') or [])}\n"
            f"Debilidades: {', '.join(fit.get('weaknesses') or [])}"
        ).strip()
        create_pinned_ai_note(
            db,
            candidate_id=candidate.id,
            search_id=search.id,
            author_user_id=created_by,
            note_type="ai_cv_analysis",
            body=note_body[:4000],
        )
    return row
