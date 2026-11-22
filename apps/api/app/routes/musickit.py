from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.services.musickit_token import MusicKitNotConfigured, get_developer_token

router = APIRouter(prefix="/musickit", tags=["musickit"])


class DeveloperTokenOut(BaseModel):
    token: str
    expires_at: int


@router.get("/developer-token", response_model=DeveloperTokenOut)
def developer_token() -> DeveloperTokenOut:
    """Short-lived MusicKit developer token. 503 when Apple credentials aren't configured."""
    try:
        t = get_developer_token(settings)
    except MusicKitNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return DeveloperTokenOut(token=t.token, expires_at=t.expires_at)
