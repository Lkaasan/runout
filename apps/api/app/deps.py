import secrets
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

_basic = HTTPBasic()


def require_admin(creds: Annotated[HTTPBasicCredentials, Depends(_basic)]) -> None:
    """Single shared password from env over HTTP basic (any username)."""
    if not settings.admin_password:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Admin disabled: set ADMIN_PASSWORD"
        )
    if not secrets.compare_digest(creds.password.encode(), settings.admin_password.encode()):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Wrong password",
            headers={"WWW-Authenticate": "Basic"},
        )


AdminDep = Depends(require_admin)
