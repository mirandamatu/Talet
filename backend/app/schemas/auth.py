from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    user: dict


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
