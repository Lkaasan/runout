from fastapi import APIRouter, HTTPException, Query

from app.deps import SessionDep
from app.schemas import ArtistDetail, ArtistSummary, SearchResults
from app.services import browse

router = APIRouter()


@router.get("/search")
def search(
    session: SessionDep, q: str = Query("", max_length=100), limit: int = Query(8, ge=1, le=50)
) -> SearchResults:
    """Artists and albums in the library matching a name. An empty query returns nothing."""
    return browse.search(session, q, limit)


@router.get("/artists")
def list_artists(session: SessionDep) -> list[ArtistSummary]:
    """Every artist with at least one album, A to Z."""
    return browse.list_artists(session)


@router.get("/artists/{slug}")
def get_artist(slug: str, session: SessionDep) -> ArtistDetail:
    """An artist with all their albums (newest first) and approved claims about them."""
    artist = browse.get_artist(session, slug)
    if artist is None:
        raise HTTPException(404, f"No artist '{slug}'")
    return artist
