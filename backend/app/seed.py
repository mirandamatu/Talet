"""Datos de demostración: usuarios base, búsquedas y CVs locales.

Idempotente: podés ejecutar `python -m app.seed` varias veces; no duplica por email
de candidato / título de búsqueda. Los PDF se guardan en `uploads/cvs/demo/`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from pypdf import PdfWriter
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.session import SessionLocal
import app.db.imports  # noqa: F401
from app.models.candidate import Candidate
from app.models.client import Client
from app.models.organization import Organization
from app.models.search import Search
from app.models.user import User
from app.models.user_client import UserClient

SEED_MARKER = '[seed:v2]'
ORG_SLUG = 'aptia-default-seed'
PUBLIC_SLUG = 'demo-empresa'

USERS_SPEC: list[tuple[str, str, str, str, bool]] = [
    ('Admin Principal', 'admin@acidt.com', 'admin123', 'SUPERADMIN', False),
    ('Comercial Demo', 'comercial@acidt.com', 'comercial123', 'COMERCIAL', False),
    ('Talent Demo', 'talent@acidt.com', 'talent123', 'TALENT', False),
    ('Cliente Demo', 'cliente@acidt.com', 'cliente123', 'CLIENTE', True),
]

LINK_USER_EMAILS = ('comercial@acidt.com', 'talent@acidt.com')

SEARCH_SPECS: list[dict] = [
    {
        'title': 'QA Manual y Automatización',
        'manual_state': 'abierta',
        'archived': False,
        'job_description': (
            '<p>Buscamos <strong>QA Engineer</strong> con experiencia en pruebas manuales y automatizadas '
            '(Selenium, Cypress o similar).</p><p>Requisitos: APIs REST, Git, metodologías ágiles.</p>'
        ),
        'contact_name': 'Laura Gómez',
        'contact_email': 'laura.gomez@demo.local',
    },
    {
        'title': 'Desarrollador Full Stack',
        'manual_state': 'activa',
        'archived': False,
        'job_description': (
            '<p>Stack: <strong>React</strong>, <strong>Python/FastAPI</strong>, PostgreSQL.</p>'
            '<p>Valoramos tests, code review y documentación.</p>'
        ),
        'contact_name': 'Pedro Martínez',
        'contact_email': 'pedro.martinez@demo.local',
    },
    {
        'title': 'Product Manager',
        'manual_state': 'abierta',
        'archived': False,
        'job_description': (
            '<p>Perfil con foco en discovery, roadmap y trabajo con ingeniería y diseño.</p>'
            '<p>Experiencia en productos B2B SaaS deseable.</p>'
        ),
        'contact_name': 'Cliente Demo',
        'contact_email': 'cliente@acidt.com',
    },
    {
        'title': 'Analista de Datos (histórico)',
        'manual_state': None,
        'archived': True,
        'job_description': (
            '<p><em>Búsqueda archivada de ejemplo.</em> SQL, dashboards y storytelling con datos.</p>'
        ),
        'contact_name': 'RRHH Demo',
        'contact_email': 'rrhh@demo.local',
    },
    {
        'title': 'Diseño UX/UI',
        'manual_state': None,
        'archived': False,
        'job_description': (
            '<p>Diseño de interfaces, sistemas de diseño y trabajo con Figma.</p>'
            '<p>Portfolio con casos de usuarios y accesibilidad.</p>'
        ),
        'contact_name': 'Nadia Ferreira',
        'contact_email': 'nadia@demo.local',
    },
]

# search_title, full_name, email, short_profile, status, pdf_filename
CANDIDATE_SPECS: list[tuple[str, str, str, str, str, str]] = [
    (
        'QA Manual y Automatización',
        'Ana Pérez',
        'ana.perez@seed.local',
        'QA manual 4 años; casos de prueba, regresión y smoke. Certificación ISTQB.',
        'en_revision',
        'cv_ana_perez.pdf',
    ),
    (
        'QA Manual y Automatización',
        'Luis Gómez',
        'luis.gomez@seed.local',
        'QA automation (Python, Pytest, API testing). CI/CD básico.',
        'entrevistado',
        'cv_luis_gomez.pdf',
    ),
    (
        'QA Manual y Automatización',
        'Paula Ruiz',
        'paula.ruiz@seed.local',
        'Semi senior QA, enfoque mobile y accesibilidad.',
        'pendiente_entrevista',
        'cv_paula_ruiz.pdf',
    ),
    (
        'Desarrollador Full Stack',
        'Marina Díaz',
        'marina.diaz@seed.local',
        'Full stack 6 años: React, Node, Python. Lideró módulo de facturación.',
        'aprobado',
        'cv_marina_diaz.pdf',
    ),
    (
        'Desarrollador Full Stack',
        'Tomás Vega',
        'tomas.vega@seed.local',
        'Backend pesado (PostgreSQL, Redis); front en React.',
        'en_revision',
        'cv_tomas_vega.pdf',
    ),
    (
        'Product Manager',
        'Lucía Ferraro',
        'lucia.ferraro@seed.local',
        'PM en SaaS B2B; OKRs, discovery y métricas.',
        'en_revision',
        'cv_lucia_ferraro.pdf',
    ),
    (
        'Analista de Datos (histórico)',
        'Diego Morales',
        'diego.morales@seed.local',
        'SQL avanzado, Looker/Power BI; búsqueda histórica de ejemplo.',
        'descartado',
        'cv_diego_morales.pdf',
    ),
    (
        'Diseño UX/UI',
        'Camila Sosa',
        'camila.sosa@seed.local',
        'UX/UI 5 años; design systems y research liviano.',
        'en_revision',
        'cv_camila_sosa.pdf',
    ),
]

# Banco de talento: sin search_id
BANK_SPECS: list[tuple[str, str, str, str, str]] = [
    (
        'Roberto En Banca',
        'roberto.banca@seed.local',
        'Perfil senior backend; disponible en 30 días. Python, microservicios.',
        'en_banca',
        'cv_roberto_banca.pdf',
    ),
    (
        'Valentina Herrera',
        'valentina.herrera@seed.local',
        'Data analyst junior; SQL, Python, entusiasmo por negocio.',
        'en_banca',
        'cv_valentina_herrera.pdf',
    ),
]


def _pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _uploads_base() -> Path:
    return Path(__file__).resolve().parents[1] / 'uploads'


def _write_demo_cv(filename: str) -> tuple[str, str]:
    """Escribe `uploads/cvs/demo/<filename>` y devuelve (url, filename para DB)."""
    key = f'cvs/demo/{filename.replace(" ", "_")}'
    full = _uploads_base() / key
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(_pdf_bytes())
    return f'/uploads/{key}'.replace('\\', '/'), filename


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_org_client(db: Session) -> tuple[Organization, Client]:
    org = db.query(Organization).filter(Organization.slug == ORG_SLUG).first()
    if not org:
        org = Organization(
            name='Default',
            slug=ORG_SLUG,
            plan='starter',
            plan_status='trial',
        )
        db.add(org)
        db.flush()

    client = (
        db.query(Client)
        .filter(Client.organization_id == org.id, Client.name == 'Cliente Demo')
        .first()
    )
    if not client:
        client = Client(name='Cliente Demo', status='active', organization_id=org.id)
        db.add(client)
        db.flush()

    if not client.public_slug:
        existing = db.query(Client).filter(Client.public_slug == PUBLIC_SLUG).first()
        client.public_slug = PUBLIC_SLUG if not existing else f'{PUBLIC_SLUG}-{client.id}'
    db.commit()
    db.refresh(org)
    db.refresh(client)
    return org, client


def _ensure_users(db: Session, org: Organization, client: Client) -> None:
    for full_name, email, password, role, must_change in USERS_SPEC:
        if db.query(User).filter(User.email == email).first():
            continue
        u = User(
            full_name=full_name,
            email=email,
            password_hash=get_password_hash(password),
            role=role,
            organization_id=org.id,
            client_id=client.id if role in ('COMERCIAL', 'TALENT', 'CLIENTE') else None,
            must_change_password=must_change,
            is_active=True,
        )
        db.add(u)
    db.commit()


def _ensure_user_client_links(db: Session, client: Client) -> None:
    for email in LINK_USER_EMAILS:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            continue
        exists = (
            db.query(UserClient)
            .filter(UserClient.user_id == user.id, UserClient.client_id == client.id)
            .first()
        )
        if not exists:
            db.add(UserClient(user_id=user.id, client_id=client.id))
    db.commit()


def _ensure_searches(db: Session, client: Client) -> dict[str, Search]:
    """Devuelve mapa título -> Search."""
    out: dict[str, Search] = {}
    for spec in SEARCH_SPECS:
        title = spec['title']
        row = (
            db.query(Search)
            .filter(Search.client_id == client.id, Search.title == title)
            .first()
        )
        if row:
            out[title] = row
            continue
        archived_at = _now() if spec.get('archived') else None
        row = Search(
            client_id=client.id,
            title=title,
            job_description=spec['job_description'],
            contact_name=spec.get('contact_name'),
            contact_email=spec.get('contact_email'),
            manual_state=spec.get('manual_state'),
            internal_notes=SEED_MARKER,
            archived_at=archived_at,
        )
        db.add(row)
        db.flush()
        out[title] = row
    db.commit()
    for spec in SEARCH_SPECS:
        t = spec['title']
        if t not in out:
            s = (
                db.query(Search)
                .filter(Search.client_id == client.id, Search.title == t)
                .first()
            )
            if s:
                out[t] = s
    return out


def _ensure_candidates(
    db: Session,
    client: Client,
    by_title: dict[str, Search],
) -> None:
    for search_title, full_name, email, short_profile, status, fname in CANDIDATE_SPECS:
        if (
            db.query(Candidate)
            .filter(Candidate.client_id == client.id, Candidate.email == email)
            .first()
        ):
            continue
        search = by_title.get(search_title)
        if not search:
            continue
        url, display_name = _write_demo_cv(fname)
        db.add(
            Candidate(
                search_id=search.id,
                client_id=client.id,
                full_name=full_name,
                email=email,
                short_profile=short_profile,
                cv_file_url=url,
                cv_file_name=display_name,
                cv_uploaded_at=_now(),
                status=status,
                internal_notes=SEED_MARKER,
            )
        )
    db.commit()


def _ensure_bank(db: Session, client: Client) -> None:
    for full_name, email, short_profile, status, fname in BANK_SPECS:
        if (
            db.query(Candidate)
            .filter(Candidate.client_id == client.id, Candidate.email == email)
            .first()
        ):
            continue
        url, display_name = _write_demo_cv(fname)
        db.add(
            Candidate(
                search_id=None,
                client_id=client.id,
                full_name=full_name,
                email=email,
                short_profile=short_profile,
                cv_file_url=url,
                cv_file_name=display_name,
                cv_uploaded_at=_now(),
                status=status,
                internal_notes=SEED_MARKER,
            )
        )
    db.commit()


def seed() -> None:
    db: Session = SessionLocal()
    try:
        org, client = _ensure_org_client(db)
        _ensure_users(db, org, client)
        _ensure_user_client_links(db, client)
        by_title = _ensure_searches(db, client)
        _ensure_candidates(db, client, by_title)
        _ensure_bank(db, client)
        print('Seed OK: usuarios demo, búsquedas, CVs en /uploads/cvs/demo/ y banco de talento.')
    finally:
        db.close()


if __name__ == '__main__':
    seed()
