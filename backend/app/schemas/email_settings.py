from pydantic import BaseModel


class EmailSettingsIn(BaseModel):
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    use_tls: bool = True


class EmailSettingsOut(BaseModel):
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_from_email: str | None = None
    use_tls: bool = True
    is_configured: bool = False
    has_password: bool = False
