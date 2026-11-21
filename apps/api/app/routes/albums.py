from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class AlbumSummary(BaseModel):
    slug: str
    title: str
    artist: str
    artwork_url: str | None = None


@router.get("/albums")
def list_albums() -> list[AlbumSummary]:
    """Curated album shelf. Empty until the data model lands (Milestone 2)."""
    return []
