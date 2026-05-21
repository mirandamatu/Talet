from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    full_name: str | None = None
    email: str
    password: str
    role: str
    client_id: int | None = None
    client_ids: list[int] = Field(default_factory=list)
    must_change_password: bool = False
    is_active: bool = True


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    role: str | None = None
    client_id: int | None = None
    client_ids: list[int] | None = None
    must_change_password: bool | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    id: int
    full_name: str | None
    email: str
    role: str
    organization_id: int | None = None
    client_id: int | None
    client_ids: list[int] = Field(default_factory=list)
    is_active: bool
    must_change_password: bool

    class Config:
        from_attributes = True


class AdminChangePassword(BaseModel):
    new_password: str
