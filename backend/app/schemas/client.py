from pydantic import BaseModel


class ClientCreate(BaseModel):
    name: str
    status: str = 'active'


class ClientUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    public_slug: str | None = None


class ClientOut(BaseModel):
    id: int
    name: str
    status: str
    public_slug: str | None = None
    organization_id: int | None = None

    class Config:
        from_attributes = True


class ClientSlugUpdate(BaseModel):
    public_slug: str
