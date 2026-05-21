from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.alert_log import AlertLog
from app.models.candidate import Candidate
from app.models.candidate_presentation import CandidatePresentation
from app.models.client import Client
from app.models.feedback import Feedback
from app.models.interview import Interview
from app.models.search import Search
from app.models.search_candidate_analysis import SearchCandidateAnalysis
from app.models.status_history import StatusHistory
from app.models.user import User
from app.services.search_states import classify_search
from app.services.user_clients import get_accessible_clients, get_user_client_ids


def _visible_searches(db: Session, user: User) -> list[Search]:
    if user.organization_id is None:
        return []
    q = (
        db.query(Search)
        .join(Client, Search.client_id == Client.id)
        .filter(Client.organization_id == user.organization_id)
        .order_by(Search.id.desc())
    )
    if user.role == "SUPERADMIN":
        return q.all()
    client_ids = get_user_client_ids(user)
    if not client_ids:
        return []
    return q.filter(Search.client_id.in_(client_ids)).all()


def _visible_candidates(db: Session, user: User) -> list[Candidate]:
    if user.organization_id is None:
        return []
    org_id = user.organization_id
    clients_in_org = {c.id for c in db.query(Client.id).filter(Client.organization_id == org_id).all()}
    assigns = set(get_user_client_ids(user)) if user.role != "SUPERADMIN" else None

    rows = db.query(Candidate).order_by(Candidate.id.desc()).all()
    searches = {s.id: s for s in db.query(Search).all()}
    visible = []
    for candidate in rows:
        in_org = False
        if candidate.search_id:
            s = searches.get(candidate.search_id)
            if s and s.client_id in clients_in_org:
                in_org = True
        elif candidate.client_id and candidate.client_id in clients_in_org:
            in_org = True
        if not in_org:
            continue

        if user.role == "SUPERADMIN":
            visible.append(candidate)
            continue

        if candidate.search_id:
            s = searches.get(candidate.search_id)
            if s and s.client_id in assigns:
                visible.append(candidate)
        elif candidate.client_id in assigns and user.role in ("TALENT", "COMERCIAL"):
            visible.append(candidate)
    return visible


def _avg_stage_days(db: Session, candidates: list[Candidate]) -> dict:
    if not candidates:
        return {}
    ids = [c.id for c in candidates]
    rows = db.query(StatusHistory).filter(StatusHistory.candidate_id.in_(ids)).order_by(StatusHistory.candidate_id, StatusHistory.id).all()
    grouped: dict[int, list] = defaultdict(list)
    for row in rows:
        grouped[row.candidate_id].append(row)
    totals: dict[str, list[float]] = defaultdict(list)
    for history in grouped.values():
        for idx in range(1, len(history)):
            prev = history[idx - 1]
            curr = history[idx]
            if prev.created_at and curr.created_at:
                delta = (curr.created_at - prev.created_at).total_seconds() / 86400
                totals[f"{prev.to_status}->{curr.to_status}"].append(delta)
    return {key: round(sum(values) / len(values), 1) for key, values in totals.items() if values}


def build_metrics_summary(db: Session, user: User) -> dict:
    searches = _visible_searches(db, user)
    candidates = _visible_candidates(db, user)
    search_states = Counter(classify_search(search, db) for search in searches)
    candidate_statuses = Counter(candidate.status or "sin_estado" for candidate in candidates)
    clients = get_accessible_clients(user, db)
    role_q = db.query(User).filter(User.is_active.is_(True))
    if user.organization_id is not None:
        role_q = role_q.filter(User.organization_id == user.organization_id)
    role_counts = Counter(row.role for row in role_q.all())

    source_counts = Counter((c.source or "manual") for c in candidates)
    ai_scores = [
        float(row.match_score)
        for row in db.query(SearchCandidateAnalysis).all()
        if row.match_score is not None
    ]
    high_match_pct = round(100 * sum(1 for s in ai_scores if s >= 7) / len(ai_scores), 1) if ai_scores else 0

    presented = db.query(CandidatePresentation).count()
    approved = db.query(Candidate).filter(Candidate.status == "aprobado").count()
    acceptance_rate = round(100 * approved / presented, 1) if presented else 0

    summary = {
        "role": user.role,
        "searches": {
            "total": len(searches),
            "abiertas": search_states.get("abierta", 0),
            "activas": search_states.get("activa", 0),
            "desactivadas": search_states.get("desactivada", 0),
            "eliminadas": search_states.get("eliminada", 0),
        },
        "candidates": {
            "total": len(candidates),
            "por_estado": dict(candidate_statuses),
            "por_fuente": dict(source_counts),
        },
        "ai": {
            "avg_match_score": round(sum(ai_scores) / len(ai_scores), 1) if ai_scores else None,
            "high_match_pct": high_match_pct,
        },
        "commercial": {
            "acceptance_rate_pct": acceptance_rate,
            "presented_total": presented,
        },
        "talent": {
            "avg_stage_days": _avg_stage_days(db, candidates),
            "interviews_total": db.query(Interview).count(),
        },
        "scope": {
            "clients_total": len(clients),
            "talent_total": role_counts.get("TALENT", 0) if user.role == "SUPERADMIN" else None,
            "commercial_total": role_counts.get("COMERCIAL", 0) if user.role == "SUPERADMIN" else None,
            "client_user_total": role_counts.get("CLIENTE", 0) if user.role == "SUPERADMIN" else None,
        },
        "sections": [],
    }

    if user.role == "TALENT":
        summary["sections"] = [
            {"title": "Pipeline por etapa", "description": "Tiempo promedio entre estados del candidato."},
            {"title": "Calidad del banco IA", "description": f"{high_match_pct}% de análisis con match ≥ 7/10."},
        ]
    elif user.role == "CLIENTE":
        summary["sections"] = [
            {"title": "Mis candidatos presentados", "description": "Seguimiento de feedback y tiempos de respuesta."},
        ]
    elif user.role == "COMERCIAL":
        summary["sections"] = [
            {"title": "Tasa de aceptación", "description": f"{acceptance_rate}% de candidatos presentados aprobados."},
        ]
    else:
        summary["sections"] = [
            {"title": "Vista global", "description": "Comparativa operativa entre cuentas y roles."},
            {"title": "Log de alertas", "description": "Actividad reciente del sistema de alertas."},
        ]
        summary["alerts_recent"] = [
            {
                "event_type": row.event_type,
                "title": row.title,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in db.query(AlertLog).order_by(AlertLog.id.desc()).limit(20).all()
        ]

    return summary
