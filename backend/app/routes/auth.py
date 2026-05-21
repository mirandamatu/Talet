from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_current_user, get_password_hash, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, LoginResponse

router = APIRouter(prefix='/auth', tags=['auth'])


@router.post('/login', response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=401, detail='Invalid credentials')
    if not user.is_active:
        raise HTTPException(status_code=401, detail='ACCOUNT_INACTIVE')
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail='Invalid credentials')

    token_data: dict = {'sub': str(user.id)}
    if user.organization_id is not None:
        token_data['organization_id'] = user.organization_id
    token = create_access_token(token_data)
    return LoginResponse(access_token=token, user={
        'id': user.id,
        'email': user.email,
        'role': user.role,
        'client_id': user.client_id,
        'client_ids': user.client_ids,
        'organization_id': user.organization_id,
        'must_change_password': user.must_change_password,
    })


@router.post('/change-password')
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid current password')

    user.password_hash = get_password_hash(payload.new_password)
    user.must_change_password = False
    db.add(user)
    db.commit()
    return {'status': 'ok'}
