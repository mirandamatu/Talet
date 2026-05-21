from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes import admin, ai, auth, careers, client, client_profile, commercial, health, hub, integrations, product, recruiting, scheduler, talent
from app.services.google_calendar import google_oauth_env_configured
from app.db.session import SessionLocal
from app.services.scheduler import run_scheduled_maintenance

app = FastAPI(title='Atipia API')


@app.on_event('startup')
def _run_startup_maintenance() -> None:
    db = SessionLocal()
    try:
        result = run_scheduled_maintenance(db)
        print(f'[Atipia] Maintenance: {result}')
    except Exception as exc:
        print(f'[Atipia] Maintenance skipped: {exc}')
    finally:
        db.close()


@app.on_event('startup')
def _log_google_oauth_status() -> None:
    if google_oauth_env_configured():
        print('[Atipia] Google OAuth: configurado (Continuar con Google habilitado).')
    else:
        print(
            '[Atipia] Google OAuth: NO configurado. '
            'Definí GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET y '
            'GOOGLE_OAUTH_REDIRECT_URI en backend/.env y reiniciá.'
        )


app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(health.router, prefix='/api')
app.include_router(auth.router, prefix='/api')
app.include_router(admin.router, prefix='/api')
app.include_router(commercial.router, prefix='/api')
app.include_router(client_profile.router, prefix='/api')
app.include_router(talent.router, prefix='/api')
app.include_router(client.router, prefix='/api')
app.include_router(ai.router, prefix='/api')
app.include_router(product.router, prefix='/api')
app.include_router(recruiting.router, prefix='/api/recruiting')
app.include_router(hub.router, prefix='/api')
app.include_router(integrations.router, prefix='/api')
app.include_router(scheduler.router, prefix='/api')
app.include_router(careers.router, prefix='/api')

uploads_dir = Path(__file__).resolve().parents[1] / 'uploads'
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount('/uploads', StaticFiles(directory=str(uploads_dir)), name='uploads')
