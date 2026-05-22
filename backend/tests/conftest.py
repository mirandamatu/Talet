import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "test-secret-with-more-than-32-characters")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:5173")

from app.core.security import create_access_token, get_password_hash
from app.db.base import Base
import app.db.imports  # noqa: F401
from app.db.session import get_db
from app.main import app
from app.models.candidate import Candidate
from app.models.client import Client
from app.models.organization import Organization
from app.models.search import Search
from app.models.user import User
from app.models.user_client import UserClient


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def org(db):
    row = Organization(name="Atipia Test", slug="atipia-test")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture()
def client_account(db, org):
    row = Client(name="Cliente Test", status="active", public_slug="cliente-test", organization_id=org.id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def make_user(db, *, role, email, client=None, org=None, active=True, password="secret123"):
    row = User(
        full_name=f"{role} User",
        email=email,
        password_hash=get_password_hash(password),
        role=role,
        client_id=client.id if client else None,
        organization_id=org.id if org else client.organization_id if client else None,
        is_active=active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    if client:
        db.add(UserClient(user_id=row.id, client_id=client.id))
        db.commit()
        db.refresh(row)
    return row


def auth_headers(user):
    token = create_access_token({"sub": str(user.id), "organization_id": user.organization_id})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def users(db, org, client_account):
    return {
        "superadmin": make_user(db, role="SUPERADMIN", email="super@test.com", org=org),
        "comercial": make_user(db, role="COMERCIAL", email="comercial@test.com", client=client_account),
        "talent": make_user(db, role="TALENT", email="talent@test.com", client=client_account),
        "cliente": make_user(db, role="CLIENTE", email="cliente@test.com", client=client_account),
        "inactive": make_user(db, role="CLIENTE", email="inactive@test.com", client=client_account, active=False),
    }


@pytest.fixture()
def headers(users):
    return {role: auth_headers(user) for role, user in users.items()}


@pytest.fixture()
def search(db, client_account):
    row = Search(
        client_id=client_account.id,
        title="Backend Engineer",
        job_description="Python, FastAPI y PostgreSQL",
        manual_state="abierta",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture()
def candidate(db, client_account, search):
    row = Candidate(
        client_id=client_account.id,
        search_id=search.id,
        full_name="Ada Lovelace",
        email="ada@test.com",
        short_profile="Backend senior",
        status="en_revision",
        cv_file_url=str(Path("uploads") / "ada.pdf"),
        cv_file_name="ada.pdf",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
