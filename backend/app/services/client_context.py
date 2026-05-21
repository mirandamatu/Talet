from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.client import Client
from app.models.client_profile import ClientContact, ClientProfile
from app.models.feedback import Feedback
from app.models.search import Search


def build_client_context(db: Session, client_id: int) -> str:
    client = db.get(Client, client_id)
    if not client:
        return ""

    profile = db.query(ClientProfile).filter(ClientProfile.client_id == client_id).first()
    contacts = db.query(ClientContact).filter(ClientContact.client_id == client_id).order_by(ClientContact.is_primary.desc()).all()

    parts = [f"Empresa: {client.name}"]
    if profile:
        if profile.industry:
            parts.append(f"Rubro: {profile.industry}")
        if profile.company_size:
            parts.append(f"Tamaño: {profile.company_size}")
        if profile.work_mode:
            parts.append(f"Modalidad: {profile.work_mode}")
        if profile.culture:
            parts.append(f"Cultura: {profile.culture}")
        if profile.benefits:
            parts.append(f"Beneficios: {profile.benefits}")
        if profile.tech_stack_json:
            parts.append(f"Stack tecnológico: {', '.join(profile.tech_stack_json)}")
        if profile.frequent_requirements_json:
            parts.append(f"Requisitos frecuentes: {', '.join(profile.frequent_requirements_json)}")
        if profile.internal_notes:
            parts.append(f"Notas internas: {profile.internal_notes}")

    if contacts:
        contact_lines = []
        for contact in contacts[:8]:
            line = contact.full_name
            if contact.role_title:
                line += f" ({contact.role_title})"
            if contact.is_primary:
                line += " [referente principal]"
            contact_lines.append(line)
        parts.append("Contactos clave: " + "; ".join(contact_lines))

    feedback_rows = (
        db.query(Feedback, Candidate)
        .join(Candidate, Candidate.id == Feedback.candidate_id)
        .join(Search, Search.id == Candidate.search_id)
        .filter(Search.client_id == client_id)
        .order_by(Feedback.created_at.desc())
        .limit(20)
        .all()
    )
    approved = []
    rejected = []
    for fb, candidate in feedback_rows:
        label = f"{candidate.full_name}: {fb.stage}/{fb.main_reason}"
        if fb.comment:
            label += f" — {fb.comment[:120]}"
        if fb.stage in {"APPROVED", "approved", "aprobado"} or candidate.status == "aprobado":
            approved.append(label)
        elif fb.stage in {"REJECTED", "REJECTED", "descartado", "rechazado"} or candidate.status in {"descartado", "rechazado"}:
            rejected.append(label)
    if approved:
        parts.append("Historial aprobados recientes:\n- " + "\n- ".join(approved[:8]))
    if rejected:
        parts.append("Historial rechazados recientes:\n- " + "\n- ".join(rejected[:8]))

    closed_searches = (
        db.query(Search)
        .filter(Search.client_id == client_id, Search.archived_at.isnot(None))
        .order_by(Search.archived_at.desc())
        .limit(8)
        .all()
    )
    if closed_searches:
        history = [f"{s.title} (cerrada {s.closed_at or s.archived_at})" for s in closed_searches]
        parts.append("Búsquedas cerradas recientes: " + "; ".join(history))

    return "\n\n".join(parts)
