"""Vacía todas las búsquedas, candidatos y datos relacionados (DB + CVs locales).

Ejecutar: `python -m app.wipe_recruiting`

No elimina usuarios, clientes, organizaciones ni conexiones de calendario por usuario.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal

# Sentencias en orden seguro ante FK (PostgreSQL).
_DELETE_STATEMENTS: tuple[str, ...] = (
    'DELETE FROM interview_transcripts',
    'DELETE FROM interviews',
    """DELETE FROM calendar_events
       WHERE search_id IS NOT NULL OR candidate_id IS NOT NULL""",
    'DELETE FROM candidate_outreach_tokens',
    'DELETE FROM candidate_outreach',
    'DELETE FROM search_candidate_analyses',
    'DELETE FROM feedback',
    'DELETE FROM status_history',
    'DELETE FROM candidate_note_visibility',
    'DELETE FROM candidate_notes',
    """DELETE FROM ai_insights
       WHERE entity_type IN ('candidate', 'search', 'interview')""",
    'DELETE FROM candidates',
    'DELETE FROM availability_slots',
    'DELETE FROM search_documents',
    'DELETE FROM search_ai_questions',
    'DELETE FROM searches',
    """DELETE FROM activity_logs
       WHERE entity_type IN ('candidate', 'search', 'interview')""",
)


def cleanup_local_cv_uploads() -> int:
    """Borra ficheros bajo uploads/cvs/ (dev/local). Devuelve cantidad borrada."""
    base = Path(__file__).resolve().parents[1] / 'uploads' / 'cvs'
    if not base.is_dir():
        return 0
    n = 0
    for path in sorted(base.rglob('*'), reverse=True):
        if path.is_file():
            path.unlink(missing_ok=True)
            n += 1
    return n


def wipe_recruiting_data(session: Session) -> None:
    for stmt in _DELETE_STATEMENTS:
        session.execute(text(stmt))
    session.commit()


def run() -> None:
    db: Session = SessionLocal()
    try:
        wipe_recruiting_data(db)
        removed = cleanup_local_cv_uploads()
        print(f'Listo: busquedas, candidatos y datos vinculados eliminados. CVs locales borrados: {removed}.')
    finally:
        db.close()


if __name__ == '__main__':
    run()
