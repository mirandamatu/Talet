from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, require_roles
from app.db.session import get_db
from app.models.client import Client
from app.models.user import User
from app.schemas.client import ClientCreate, ClientOut, ClientUpdate
from app.schemas.user import AdminChangePassword, UserCreate, UserOut, UserUpdate
from app.services.plan_limits import check_client_limit, check_user_limit
from app.services.tenancy import require_organization_id
from app.services.user_clients import sync_user_clients

router = APIRouter(prefix='/admin', tags=['admin'])


@router.post('/clients', response_model=ClientOut)
def create_client(
    payload: ClientCreate,
    user: User = Depends(require_roles('SUPERADMIN')),
    db: Session = Depends(get_db),
):
    oid = require_organization_id(user)
    check_client_limit(db, oid)
    client = Client(name=payload.name, status=payload.status, organization_id=oid)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get('/clients', response_model=list[ClientOut])
def list_clients(
    user: User = Depends(require_roles('SUPERADMIN')),
    db: Session = Depends(get_db),
):
    oid = require_organization_id(user)
    return db.query(Client).filter(Client.organization_id == oid).order_by(Client.id).all()


@router.patch('/clients/{client_id}', response_model=ClientOut)
def update_client(
    client_id: int,
    payload: ClientUpdate,
    user: User = Depends(require_roles('SUPERADMIN')),
    db: Session = Depends(get_db),
):
    client = db.get(Client, client_id)
    if not client or client.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail='Client not found')
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def _resolve_user_clients(role: str, client_id: int | None, client_ids: list[int] | None) -> tuple[list[int], int | None]:
    merged = []
    if client_id is not None:
        merged.append(int(client_id))
    if client_ids:
        merged.extend(int(cid) for cid in client_ids)
    unique_ids = sorted(set(merged))

    if role == 'CLIENTE':
        if len(unique_ids) > 1:
            raise HTTPException(status_code=400, detail='CLIENTE can only be assigned to one client')
        return unique_ids, (unique_ids[0] if unique_ids else None)

    if role in ('COMERCIAL', 'TALENT'):
        if not unique_ids:
            raise HTTPException(status_code=400, detail='Talent y Comercial deben tener al menos un cliente asignado')
        return unique_ids, None

    return [], None


@router.post('/users', response_model=UserOut)
def create_user(
    payload: UserCreate,
    admin: User = Depends(require_roles('SUPERADMIN')),
    db: Session = Depends(get_db),
):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail='Email already exists')

    oid = require_organization_id(admin)
    check_user_limit(db, oid)

    client_ids, primary_client_id = _resolve_user_clients(payload.role, payload.client_id, payload.client_ids)
    if payload.role == 'CLIENTE' and not client_ids:
        generated_name = (payload.full_name or payload.email.split('@')[0]).strip()
        new_client = Client(name=generated_name, status='active', organization_id=oid)
        db.add(new_client)
        db.flush()
        client_ids = [new_client.id]
        primary_client_id = new_client.id

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        role=payload.role,
        client_id=primary_client_id,
        organization_id=oid,
        must_change_password=payload.must_change_password,
        is_active=payload.is_active,
    )
    db.add(user)
    db.flush()
    sync_user_clients(db, user, client_ids)
    db.commit()
    db.refresh(user)
    return user


@router.get('/users', response_model=list[UserOut])
def list_users(
    user: User = Depends(require_roles('SUPERADMIN')),
    db: Session = Depends(get_db),
):
    oid = require_organization_id(user)
    return db.query(User).filter(User.organization_id == oid).order_by(User.id).all()


@router.patch('/users/{user_id}', response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    admin: User = Depends(require_roles('SUPERADMIN')),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user or user.organization_id != admin.organization_id:
        raise HTTPException(status_code=404, detail='User not found')

    data = payload.model_dump(exclude_unset=True)

    if 'email' in data and data['email'] != user.email:
        if db.query(User).filter(User.email == data['email']).first():
            raise HTTPException(status_code=400, detail='Email already exists')

    role = data.get('role', user.role)
    client_id = data['client_id'] if 'client_id' in data else user.client_id
    client_ids = data['client_ids'] if 'client_ids' in data else user.client_ids
    resolved_client_ids, primary_client_id = _resolve_user_clients(role, client_id, client_ids)

    for field in ('full_name', 'email', 'role', 'must_change_password', 'is_active'):
        if field in data:
            setattr(user, field, data[field])

    user.client_id = primary_client_id
    db.add(user)
    db.flush()
    sync_user_clients(db, user, resolved_client_ids)
    db.commit()
    db.refresh(user)
    return user


@router.delete('/users/{user_id}')
def delete_user(
    user_id: int,
    admin: User = Depends(require_roles('SUPERADMIN')),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user or user.organization_id != admin.organization_id:
        raise HTTPException(status_code=404, detail='User not found')
    try:
        db.delete(user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail='Cannot delete user with historical references')
    return {'status': 'ok'}


@router.post('/users/{user_id}/change-password')
def change_user_password(
    user_id: int,
    payload: AdminChangePassword,
    admin: User = Depends(require_roles('SUPERADMIN')),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user or user.organization_id != admin.organization_id:
        raise HTTPException(status_code=404, detail='User not found')
    user.password_hash = get_password_hash(payload.new_password)
    user.must_change_password = True
    db.add(user)
    db.commit()
    return {'status': 'ok'}
