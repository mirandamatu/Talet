"""Public career page endpoints — no authentication required."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.candidate import Candidate
from app.models.client import Client
from app.models.organization import Organization
from app.models.search import Search
from app.models.user import User
from app.services.ai_engine import analyze_candidate_fit, extract_pdf_text
from app.services.ai_insights import create_ai_insight
from app.services.notifications import notify_user
from app.services.presentations import resolve_assigned_talent
from app.services.scheduler import touch_search_activity
from app.services.storage import save_cv_local, upload_cv

router = APIRouter(prefix="/careers", tags=["careers"])

MAX_CV_BYTES = 10 * 1024 * 1024  # 10 MB


def _slug_from_name(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[áàäâ]", "a", slug)
    slug = re.sub(r"[éèëê]", "e", slug)
    slug = re.sub(r"[íìïî]", "i", slug)
    slug = re.sub(r"[óòöô]", "o", slug)
    slug = re.sub(r"[úùüû]", "u", slug)
    slug = re.sub(r"ñ", "n", slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:80]


def _branding_payload(db: Session, client: Client) -> dict:
    org = db.get(Organization, client.organization_id) if client.organization_id else None
    if org and org.plan == "enterprise":
        return {
            "logo_url": org.logo_url,
            "primary_color": org.primary_color,
        }
    return {"logo_url": None, "primary_color": None}


@router.get("/{slug}")
def get_career_page(slug: str, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.public_slug == slug).first()
    if not client or client.status != "active":
        raise HTTPException(status_code=404, detail="Career page not found")

    searches = (
        db.query(Search)
        .filter(
            Search.client_id == client.id,
            Search.archived_at.is_(None),
            Search.manual_state == "abierta",
        )
        .order_by(Search.created_at.desc())
        .all()
    )

    return {
        "client": {
            "id": client.id,
            "name": client.name,
            "slug": client.public_slug,
        },
        "jobs": [
            {
                "id": s.id,
                "title": s.title,
                "description": s.job_description,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in searches
        ],
        "branding": _branding_payload(db, client),
    }


async def _read_cv_required(cv: UploadFile | None) -> tuple[bytes, str]:
    if cv is None or not cv.filename:
        raise HTTPException(status_code=400, detail="El CV en PDF es obligatorio")
    content_type = cv.content_type or ""
    filename = cv.filename.lower()
    if content_type != "application/pdf" and not filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")
    raw = await cv.read()
    if len(raw) > MAX_CV_BYTES:
        raise HTTPException(status_code=400, detail="El archivo supera el límite de 10 MB")
    if not raw:
        raise HTTPException(status_code=400, detail="El archivo PDF está vacío")
    return raw, cv.filename or "cv.pdf"


async def _process_application(
    db: Session,
    *,
    slug: str,
    search_id: int | None,
    full_name: str,
    email: str,
    personal_description: str | None,
    raw_cv: bytes,
    cv_name: str,
) -> dict:
    client = db.query(Client).filter(Client.public_slug == slug).first()
    if not client or client.status != "active":
        raise HTTPException(status_code=404, detail="Career page not found")

    short_profile = (personal_description or "").strip() or None

    try:
        cv_url = upload_cv(BytesIO(raw_cv), cv_name)
    except Exception:
        try:
            cv_url = save_cv_local(BytesIO(raw_cv), cv_name)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"No se pudo subir el CV: {exc}")

    search: Search | None = None
    if search_id is not None:
        search = db.get(Search, search_id)
        if (
            not search
            or search.client_id != client.id
            or search.archived_at is not None
            or search.manual_state != "abierta"
        ):
            raise HTTPException(status_code=404, detail="Job not found")
        candidate = Candidate(
            search_id=search.id,
            client_id=client.id,
            full_name=full_name.strip(),
            email=email.strip().lower(),
            short_profile=short_profile,
            cv_file_url=cv_url,
            cv_file_name=cv_name,
            cv_uploaded_at=datetime.now(timezone.utc),
            status="applied",
            source="career_page",
        )
    else:
        candidate = Candidate(
            search_id=None,
            client_id=client.id,
            full_name=full_name.strip(),
            email=email.strip().lower(),
            short_profile=short_profile,
            cv_file_url=cv_url,
            cv_file_name=cv_name,
            cv_uploaded_at=datetime.now(timezone.utc),
            status="en_banca",
            source="career_page",
        )
    db.add(candidate)
    if search is not None:
        touch_search_activity(db, search)
    db.commit()
    db.refresh(candidate)

    if search is not None:
        try:
            cv_text = extract_pdf_text(raw_cv)
            fit = analyze_candidate_fit(
                search_title=search.title,
                job_description=search.job_description,
                candidate_name=candidate.full_name,
                short_profile=short_profile or "",
                cv_text=cv_text,
            )
            create_ai_insight(
                db,
                entity_type="candidate",
                entity_id=candidate.id,
                kind="candidate_fit",
                score=fit.get("score"),
                recommendation=fit.get("recommendation"),
                summary=fit.get("summary"),
                payload_json={"reasons": fit.get("reasons") or [], "model": fit.get("model") or "heuristic"},
                created_by=None,
            )
        except Exception:
            pass

        assigned = resolve_assigned_talent(db, search)
        notify_targets: list[User] = []
        if assigned:
            notify_targets.append(assigned)
        else:
            notify_targets = (
                db.query(User)
                .filter(User.role == "TALENT", User.is_active.is_(True))
                .all()
            )
        for user in notify_targets:
            notify_user(
                db,
                user,
                event_type="new_candidate_application",
                title="Nuevo candidato en búsqueda",
                message=f'{candidate.full_name} postuló a "{search.title}" desde la career page.',
                metadata={
                    "candidate_id": candidate.id,
                    "search_id": search.id,
                    "search_title": search.title,
                    "source": "career_page",
                },
                client_id=client.id,
                search_id=search.id,
                candidate_id=candidate.id,
            )

    if search is not None:
        return {
            "status": "ok",
            "candidate_id": candidate.id,
            "message": "Tu postulación fue recibida. ¡Muchas gracias!",
            "kind": "job",
        }
    return {
        "status": "ok",
        "candidate_id": candidate.id,
        "message": "Recibimos tu CV. Te contactaremos si surge una oportunidad acorde a tu perfil.",
        "kind": "bank",
    }


@router.post("/{slug}/apply")
async def apply_careers(
    slug: str,
    full_name: str = Form(...),
    email: str = Form(...),
    personal_description: str | None = Form(None),
    cover_letter: str | None = Form(None),
    search_id: int | None = Form(None),
    cv: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    raw, cv_name = await _read_cv_required(cv)
    description = personal_description or cover_letter
    return await _process_application(
        db,
        slug=slug,
        search_id=search_id,
        full_name=full_name,
        email=email,
        personal_description=description,
        raw_cv=raw,
        cv_name=cv_name,
    )


@router.post("/{slug}/apply/{search_id}")
async def apply_to_job_legacy(
    slug: str,
    search_id: int,
    full_name: str = Form(...),
    email: str = Form(...),
    personal_description: str | None = Form(None),
    cover_letter: str | None = Form(None),
    cv: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    raw, cv_name = await _read_cv_required(cv)
    description = personal_description or cover_letter
    return await _process_application(
        db,
        slug=slug,
        search_id=search_id,
        full_name=full_name,
        email=email,
        personal_description=description,
        raw_cv=raw,
        cv_name=cv_name,
    )
