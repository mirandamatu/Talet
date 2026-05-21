"""Crea una búsqueda mínima con 2 candidatos (PDF local). Idempotente.

Ejecutar desde `backend/`: `python -m app.quick_sample_search`
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
import app.db.imports  # noqa: F401
from app.models.candidate import Candidate
from app.models.search import Search

from app.seed import _ensure_org_client, _now, _write_demo_cv

SAMPLE_SEARCH_TITLE = 'Desarrollo Backend (muestra)'
SAMPLE_CONTACT_EMAIL = 'mirandamatu62@gmail.com'
SAMPLE_CONTACT_NAME = 'Contacto Demo'

_SAMPLE_CANDS: tuple[tuple[str, str, str, str, str], ...] = (
    (
        'Patricia Moyano',
        'patricia.moyano.quick@seed.local',
        'Backend Python 3 años — FastAPI, PostgreSQL, Redis. Tests automatizados.',
        'en_revision',
        'cv_patricia_moyano.pdf',
    ),
    (
        'Javier Coria',
        'javier.coria.quick@seed.local',
        'Backend engineer — integraciones REST, observabilidad, Docker.',
        'en_revision',
        'cv_javier_coria.pdf',
    ),
)


def ensure_sample_search_with_two_candidates(db: Session) -> tuple[Search, int]:
    _, client = _ensure_org_client(db)

    jd = (
        '<p>Muestra rápida: <strong>Desarrollo backend</strong> con Python.</p>'
        '<p>Dominio de APIs REST, bases SQL y trabajo en equipo con Product y QA.</p>'
    )

    search = (
        db.query(Search)
        .filter(Search.client_id == client.id, Search.title == SAMPLE_SEARCH_TITLE)
        .first()
    )
    if not search:
        search = Search(
            client_id=client.id,
            title=SAMPLE_SEARCH_TITLE,
            job_description=jd,
            contact_name=SAMPLE_CONTACT_NAME,
            contact_email=SAMPLE_CONTACT_EMAIL,
            manual_state='abierta',
            internal_notes='[quick-sample]',
        )
        db.add(search)
        db.flush()
    else:
        search.contact_email = SAMPLE_CONTACT_EMAIL
        search.contact_name = SAMPLE_CONTACT_NAME

    added = 0
    for full_name, email, profile, status, fname in _SAMPLE_CANDS:
        if (
            db.query(Candidate)
            .filter(Candidate.client_id == client.id, Candidate.email == email)
            .first()
        ):
            continue
        url, display_name = _write_demo_cv(fname)
        db.add(
            Candidate(
                search_id=search.id,
                client_id=client.id,
                full_name=full_name,
                email=email,
                short_profile=profile,
                cv_file_url=url,
                cv_file_name=display_name,
                cv_uploaded_at=_now(),
                status=status,
                internal_notes='[quick-sample]',
            )
        )
        added += 1

    db.commit()
    db.refresh(search)
    return search, added


def run() -> None:
    db: Session = SessionLocal()
    try:
        search, n = ensure_sample_search_with_two_candidates(db)
        ids = (
            db.query(Candidate.id, Candidate.full_name)
            .filter(Candidate.search_id == search.id)
            .order_by(Candidate.id.asc())
            .all()
        )
        print(f'Busqueda id={search.id} titulo="{search.title}". Candidatos nuevos: {n}. Total en esta busqueda: {len(ids)}.')
        for cid, name in ids:
            print(f'  - candidato id={cid} {name}')
    finally:
        db.close()


if __name__ == '__main__':
    run()
