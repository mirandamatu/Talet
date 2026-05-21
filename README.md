# Acid Talent

Portal simple de seguimiento de candidatos para clientes. UI básica, sin dashboards, con flujo: puestos -> candidatos -> detalle.

## Stack
- Backend: FastAPI + Postgres + Alembic
- Frontend: React (Vite)
- Storage CV: S3 compatible (MinIO en dev)

## Configuración

Crear un archivo `.env` en `backend/` basado en `.env.example`.

### Variables de entorno

```
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/acid_talent
JWT_SECRET=change-me
ACCESS_TOKEN_EXPIRE_MINUTES=480

S3_ENDPOINT_URL=http://localhost:9000
S3_REGION=us-east-1
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=acid-talent
S3_PUBLIC_URL_BASE=http://localhost:9000/acid-talent

SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=no-reply@acidtalent.local

AI_API_KEY=
AI_API_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini
AI_TIMEOUT_SECONDS=45
```

## Backend

```
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

## Frontend

```
cd frontend
npm install
npm run dev
```

## Usuarios seed
- SUPERADMIN: admin@acidt.com / admin123
- COMERCIAL: comercial@acidt.com / comercial123
- TALENT: talent@acidt.com / talent123
- CLIENTE: cliente@acidt.com / cliente123

## Notas
- CVs se suben a S3. Si no hay credenciales, la carga falla.
- Borrado de candidato es soft delete (`archived_at`).
- Si `AI_API_KEY` no está configurada, el sistema usa un fallback heurístico para scoring y preguntas sugeridas.

## IA Recruiting (nuevo)
- Al cargar un candidato, se genera automáticamente un score de match IA (`ai_fit_score`) y recomendación.
- Al crear/editar una búsqueda, IA propone preguntas extra para completar la JD (`ai_questions`).
- Endpoints IA disponibles bajo `/api/ai/*` para recalcular match, recalcular preguntas y analizar entrevistas con transcripción.
